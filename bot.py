import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View, Button, Modal, TextInput
import os
from dotenv import load_dotenv
from database import db
import logging
from datetime import datetime, timedelta
import asyncio
from aiohttp import web
import secrets 
import string

# ============ استيراد ملفات المشروع ============
from questions import get_all_assessment_questions, calculate_level_progressive, MAX_LEVEL
from shop import ShopView
from inventory import InventoryView
from settings import SettingsView
from titles import check_new_titles
from image_gen import ProfileGenerator
from tasks_library import VITALITY_TASKS, FREEDOM_TASKS, ALL_TASKS
import task_logic
from task_logic import draw_progress_bar

# تحميل إعدادات البيئة
load_dotenv()

# ============ 1. إعداد التسجيل (Logging) - يجب أن يكون في البداية ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============ 2. إعدادات البوت (Intents) ============
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# ============ 3. دوال الـ API (Mobile App) ============

async def health_check(request):
    return web.Response(text="S.O.L.O System is Online 🟢", content_type='text/plain')

def generate_otp(length=6):
    chars = string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

async def handle_login_request(request):
    try:
        data = await request.json()
        discord_id = data.get('discord_id')
        
        if not discord_id:
            return web.json_response({'error': 'Missing discord_id'}, status=400)

        player = await db.get_player(str(discord_id))
        if not player:
            return web.json_response({'error': 'User not found. Please register via Bot first.'}, status=404)

        otp = generate_otp()
        expiry = (datetime.now() + timedelta(minutes=5)).isoformat()

        await db._execute_async(lambda: db.client.table('app_auth_sessions').upsert({
            'discord_id': str(discord_id),
            'otp_code': otp,
            'expires_at': expiry
        }).execute())

        try:
            user = await bot.fetch_user(int(discord_id))
            embed = discord.Embed(title="🔐 رمز الدخول للتطبيق", description=f"رمز التحقق الخاص بك هو: **`{otp}`**\nصلاحية الرمز 5 دقائق.", color=discord.Color.green())
            embed.set_footer(text="لا تشارك هذا الرمز مع أحد.")
            await user.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send DM: {e}")
            return web.json_response({'error': 'Could not send DM. Open your DMs.'}, status=500)

        return web.json_response({'status': 'success', 'message': 'OTP sent to Discord'})

    except Exception as e:
        logger.error(f"API Error: {e}")
        return web.json_response({'error': 'Internal Server Error'}, status=500)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_post('/api/login', handle_login_request)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()



class SoloLevelingBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
    
    async def setup_hook(self):
        logger.info("🔄 جاري إعداد النظام...")
        
        # --- 1. تشغيل سيرفر الويب (لأجل CasaOS) ---
        await start_web_server()
        logger.info("🌍 تم تشغيل سيرفر الويب للمراقبة على المنفذ 8080")
        
        # --- 2. تحميل الإضافات (Extensions) ---
        try:
            await self.load_extension("portals")
            await self.load_extension("quest_engine")
            logger.info("✅ تم تحميل نظام البوابات ومحرك المهام")
        except Exception as e:
            logger.error(f"❌ فشل تحميل الإضافات: {e}")

        # --- 3. استعادة البوابات النشطة (Portals Persistence) ---
        try:
            from portals import PortalJoinView, PortalActiveView, PrivatePortalView
            
            active_portals = await db._execute_async(
                lambda: db.client.table('portal_history')
                .select('*, quest:system_portal_quests(*)')
                .in_('status', ['recruiting', 'active'])
                .execute()
            )
            
            for p in active_portals.data:
                quest = p['quest']
                h_id = p['id']
                participants = p.get('participants_ids', [])
                
                if p['status'] == 'recruiting':
                    if p.get('is_private'):
                        view = PrivatePortalView(quest, h_id, p.get('owner_id'))
                    else:
                        view = PortalJoinView(quest, h_id)
                else: # status == active
                    view = PortalActiveView(quest, h_id, participants)
                
                self.add_view(view)
            
            logger.info(f"✅ تم استعادة {len(active_portals.data)} بوابة نشطة")
        except Exception as e:
            logger.error(f"❌ خطأ في استعادة البوابات: {e}")

        # --- 4. استعادة لوحات المهام اليومية (Dashboards Persistence) ---
        try:
            from quest_engine import QuestDashboard
            import task_logic
            
            # جلب جميع اللاعبين غير المعطلين (نشط، مريض، مسافر...)
            active_players = await db._execute_async(
                lambda: db.client.table('players')
                .select('*')
                .neq('status', 'inactive')
                .execute()
            )
            
            restored_count = 0
            for p in active_players.data:
                # إعادة حساب المهام لنعرف شكل اللوحة الخاصة به
                assigned_tasks = task_logic.get_daily_tasks_for_player(p)
                if assigned_tasks:
                    # ✅ النسخة الصحيحة: تمرير discord_id
                    view = QuestDashboard(p['id'], p['discord_id'], assigned_tasks)
                    self.add_view(view)
                    restored_count += 1
            
            logger.info(f"✅ تم استعادة لوحات المهام لـ {restored_count} صياد")
            
        except Exception as e:
            logger.error(f"❌ خطأ في استعادة لوحات المهام: {e}")

        # --- 5. مزامنة الأوامر (مرة واحدة فقط) ---
        # ملاحظة: يفضل تعطيل هذا الجزء واستخدام !sync يدوياً لتجنب Rate Limit
        # لكن سأتركه لك كما طلبت (نسخة واحدة فقط)
        try:
            guild_id = os.getenv("DISCORD_GUILD_ID")
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                self.tree.clear_commands(guild=guild)
                await self.tree.sync(guild=guild)
            
            await self.tree.sync()
            logger.info("✅ تم مزامنة الأوامر عالمياً")
                
        except Exception as e:
            logger.error(f"❌ فشل المزامنة: {e}")

bot = SoloLevelingBot()


# ============ دوال مساعدة (Helpers) ============


async def send_notification_to_channel(title: str, description: str, rank: str = "E", player_name: str = "Unknown"):
    """إرسال إشعار عام لقناة السيرفر"""
    try:
        channel_id = os.getenv("NOTIFICATION_CHANNEL_ID")
        if not channel_id: return

        channel = bot.get_channel(int(channel_id))
        if not channel: return

        rank_colors = {
            "E": 0x95a5a6, "D": 0x3498db, "C": 0x2ecc71, 
            "B": 0xe67e22, "A": 0xe74c3c, "S": 0xf1c40f, "SS": 0x9b59b6
        }
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=rank_colors.get(rank, 0x95a5a6)
        )
        
        if rank in ["S", "SS"]:
            embed.set_thumbnail(url="https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExajRsMzRmemN3bDhnbmR6dHo0MGZpbDQydnYwdnI4YTNmZzB6NjQ5ZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/IvoysZG4Zn5a4cWBZA/giphy.gif")
            embed.set_footer(text="⚠️ تحذير: طاقة هائلة تم رصدها!")
        else:
            embed.set_footer(text="نظام Solo Leveling")

        await channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Notification Error: {e}")

# ============ 1. نظام التسجيل (Registration Classes) ============

class PenaltyModal(Modal, title="إعداد العقوبات"):
    def __init__(self, registration_data):
        super().__init__()
        self.registration_data = registration_data
        self.penalty_amount = TextInput(
            label="قيمة العقوبة (عملة حقيقية)",
            placeholder="أدخل رقماً (10-10000)",
            default="100",
            required=True,
            max_length=5
        )
        self.add_item(self.penalty_amount)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.penalty_amount.value)
            if amount < 10 or amount > 10000:
                await interaction.response.send_message("❌ القيمة يجب أن تكون بين 10 و 10000", ephemeral=True)
                return
            
            self.registration_data["penalty_amount"] = amount
            self.registration_data["user_id"] = interaction.user.id
            self.registration_data["username"] = interaction.user.name
            
            view = AspectsSelectionView(self.registration_data)
            embed = discord.Embed(title="🎯 اختيار الجوانب", description="اختر الجوانب التي تريد الالتزام بتطويرها. (الجوانب التي لا تختارها لن تظهر لك مهامها)", color=discord.Color.blue())
            if self.registration_data["faith"] != "muslim":
                embed.add_field(name="⚠️ تنبيه", value="الجانب الديني معطل لغير المسلمين", inline=False)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ يجب إدخال رقم صحيح", ephemeral=True)

class RegistrationView(View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.data = {"gender": None, "faith": None, "enable_religious": "no"}
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("🛑 هذا الأمر ليس لك!", ephemeral=True)
            return False
        return True

    @discord.ui.select(placeholder="اختر جنسك...", options=[discord.SelectOption(label="ذكر", value="male", emoji="👨"), discord.SelectOption(label="أنثى", value="female", emoji="👩")], row=0)
    async def select_gender(self, interaction: discord.Interaction, select: Select):
        self.data["gender"] = select.values[0]
        await interaction.response.defer()

    @discord.ui.select(placeholder="اختر دينك...", options=[discord.SelectOption(label="مسلم", value="muslim", emoji="🕌"), discord.SelectOption(label="غير مسلم", value="non_muslim", emoji="🌍")], row=1)
    async def select_faith(self, interaction: discord.Interaction, select: Select):
        self.data["faith"] = select.values[0]
        if select.values[0] == "muslim": self.data["enable_religious"] = "yes"
        await interaction.response.defer()

    @discord.ui.button(label="متابعة", style=discord.ButtonStyle.green, row=2)
    async def submit_btn(self, interaction: discord.Interaction, button: Button):
        if not self.data["gender"] or not self.data["faith"]:
            await interaction.response.send_message("❌ يرجى الاختيار أولاً", ephemeral=True)
            return
        await interaction.response.send_modal(PenaltyModal(self.data))

class AspectsSelectionView(View):
    def __init__(self, registration_data: dict):
        super().__init__(timeout=600)
        self.registration_data = registration_data
        self.selected_aspects = []
        # لاحظ: حذفنا aspects_interest لأننا لن نسأل عن القيمة 1-10
        self.all_aspects = {
            "strength": {"name": "💪 القوة البدنية", "emoji": "💪"},
            "intelligence": {"name": "🧠 الذكاء والمعرفة", "emoji": "🧠"},
            "vitality": {"name": "❤️ الصحة والعافية", "emoji": "❤️"},
            "agility": {"name": "🤝 المهارات الاجتماعية", "emoji": "🤝"},
            "perception": {"name": "🕌 الجانب الديني", "emoji": "🕌", "disabled": registration_data.get("faith") != "muslim"},
            "freedom": {"name": "💸 الحرية المالية", "emoji": "💸"}
        }
        self.build_initial_view()
    
    def build_initial_view(self):
        self.clear_items()
        for i, (aspect_id, info) in enumerate(self.all_aspects.items()):
            if info.get("disabled"): continue
            style = discord.ButtonStyle.green if aspect_id in self.selected_aspects else discord.ButtonStyle.gray
            btn = Button(label=info["name"], style=style, custom_id=f"asp_{aspect_id}", row=i//3)
            btn.callback = self.create_aspect_callback(aspect_id)
            self.add_item(btn)
        
        # التعديل: الزر الآن ينهي التسجيل مباشرة
        finish_btn = Button(label="إنهاء التسجيل وبدء الرحلة 🔥", style=discord.ButtonStyle.blurple, row=2, disabled=len(self.selected_aspects) == 0)
        finish_btn.callback = self.finish_registration
        self.add_item(finish_btn)

    def create_aspect_callback(self, aspect_id):
        async def callback(interaction: discord.Interaction):
            if aspect_id in self.selected_aspects: self.selected_aspects.remove(aspect_id)
            else: self.selected_aspects.append(aspect_id)
            self.build_initial_view()
            await interaction.response.edit_message(view=self)
        return callback

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != int(self.registration_data["user_id"]):
            await interaction.response.send_message("🛑 هذا ليس لك!", ephemeral=True)
            return False
        return True

    async def finish_registration(self, interaction: discord.Interaction):
        """الدالة النهائية التي تحفظ اللاعب في قاعدة البيانات"""
        await interaction.response.defer(ephemeral=True)
        
        # تجهيز البيانات الأساسية
        player_data = {
            "discord_id": str(self.registration_data["user_id"]),
            "username": self.registration_data["username"],
            "gender": self.registration_data["gender"],
            "faith_type": self.registration_data["faith"],
            "base_penalty": self.registration_data.get("penalty_amount", 100),
            "coins": 100, "gems": 10, "total_level": 1, "rank": "E",
            "created_at": "now()", "updated_at": "now()"
        }

        # منطق الحفظ الجديد:
        # الجوانب المختارة تأخذ شدة 5 (افتراضي) والجوانب غير المختارة تأخذ 0
        all_aspect_keys = ["strength", "intelligence", "vitality", "agility", "perception", "freedom"]
        for aspect in all_aspect_keys:
            if aspect in self.selected_aspects:
                player_data[f"{aspect}_intensity"] = 5  # قيمة افتراضية متوسطة
                player_data[f"{aspect}_level"] = 1
                player_data[f"{aspect}_xp"] = 0
            else:
                player_data[f"{aspect}_intensity"] = 0 # معطل تماماً

        try:
            result = await db.create_player(player_data)
            if result:
                # منح رتبة الصياد إذا كان المعرف موجوداً
                try:
                    role_id = os.getenv("HUNTER_ROLE_ID")
                    if role_id:
                        role = interaction.guild.get_role(int(role_id))
                        if role: await interaction.user.add_roles(role)
                except: pass

                embed = discord.Embed(
                    title="🎉 تم التسجيل بنجاح!", 
                    description=f"أهلاً بك يا **{player_data['username']}** في النظام.\nتم تفعيل الجوانب التي اخترتها بنجاح.\n\nاستخدم `/assessment` الآن لبدء اختبار القدرات وتحديد رتبتك!", 
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ حدث خطأ أثناء الحفظ، ربما أنت مسجل بالفعل.", ephemeral=True)
        except Exception as e:
            logger.error(f"Save Error: {e}")
            await interaction.followup.send("❌ فشل الاتصال بقاعدة البيانات أثناء الحفظ.", ephemeral=True)

# ملاحظة: تم حذف كلاس InterestSelectionView وكلاس InterestModal تماماً


# ============ 2. نظام الاختبار (Assessment System) ============

class AssessmentView(View):
    def __init__(self, player_data, questions, interaction, user_id):
        super().__init__(timeout=600)
        self.player_data = player_data
        self.questions = questions
        self.current_question = 0
        self.answers = {}
        self.interaction = interaction
        self.user_id = user_id
        self.message = None
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("🛑 هذا الاختبار خاص!", ephemeral=True)
            return False
        return True
    
    async def start(self):
        await self.show_question()
    
    async def show_question(self):
        try:
            if self.current_question >= len(self.questions):
                await self.finish_assessment()
                return
            
            question = self.questions[self.current_question]
            progress = int(((self.current_question + 1) / len(self.questions)) * 100)
            
            embed = discord.Embed(
                title=f"📝 سؤال {self.current_question + 1} ({progress}%)",
                description=f"**{question.question}**",
                color=discord.Color.blue()
            )
            
            self.clear_items()
            for i, option in enumerate(question.options):
                btn = Button(
                    label=f"{option['text']}",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"ans_{i}"
                )
                btn.callback = self.create_callback(option['points'], question.category)
                self.add_item(btn)
            
            if self.message:
                await self.message.edit(embed=embed, view=self)
            else:
                self.message = await self.interaction.followup.send(embed=embed, view=self, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Show Q Error: {e}")

    def create_callback(self, points, category):
        async def callback(interaction: discord.Interaction):
            self.answers[category] = self.answers.get(category, 0) + points
            await interaction.response.defer()
            self.current_question += 1
            await self.show_question()
        return callback
    
    async def finish_assessment(self):
        try:
            assessment_results = {}
            total_xp_sum = 0
            total_levels_sum = 0
            
            categories = ['strength', 'intelligence', 'vitality', 'agility', 'perception', 'freedom']
            
            # الرقم الموزون: 3500 للوصول لرتبة S
            ASSESSMENT_MULTIPLIER = 3500 
            
            # جلب الألقاب المكتسبة حالياً
            unlocked_titles = self.player_data.get('unlocked_titles', []) or ["مبتدئ"]

            for category in categories:
                score = self.answers.get(category, 0)
                xp = score * ASSESSMENT_MULTIPLIER
                
                level, current_xp, xp_needed = calculate_level_progressive(xp)
                
                assessment_results[f"{category}_level"] = level
                assessment_results[f"{category}_xp"] = xp
                
                total_xp_sum += xp
                total_levels_sum += level
                
                # فحص الألقاب للجانب
                new_cat_titles = check_new_titles(level, category, unlocked_titles)
                unlocked_titles.extend(new_cat_titles)
            
            avg_level = max(1, total_levels_sum // 6)
            rank = await self.calculate_rank(avg_level)
            
            # فحص ألقاب المستوى الكلي
            new_total_titles = check_new_titles(avg_level, "total", unlocked_titles)
            unlocked_titles.extend(new_total_titles)
            unlocked_titles = list(set(unlocked_titles))

            update_data = {
                **assessment_results,
                "assessment_done": True,
                "total_level": avg_level,
                "total_xp": total_xp_sum,
                "rank": rank,
                "unlocked_titles": unlocked_titles,
                "updated_at": "now()"
            }
            
            await db.update_player(self.player_data["discord_id"], update_data)
            
            # عرض النتيجة
            embed = discord.Embed(
                title="🎉 اكتمل التحليل!",
                description=f"**تقرير النظام:**\n🏆 الرتبة: **{rank}-Rank**\n📊 المستوى: **{avg_level}**",
                color=discord.Color.green()
            )
            
            if len(unlocked_titles) > 1:
                recent_titles = [t for t in unlocked_titles if t != "مبتدئ"][-3:]
                embed.add_field(name="🔓 ألقاب تم فتحها!", value=f"`{', '.join(recent_titles)}`", inline=False)
            
            try: await self.message.edit(embed=embed, view=None)
            except: await self.interaction.followup.send(embed=embed, ephemeral=True)
            
            try:
                await send_notification_to_channel(
                    title=f"🚨 صياد جديد انضم للنقابة!",
                    description=f"رحبوا بالصياد **{self.player_data['username']}**\n\n📊 الرتبة: **{rank}** | Lv.**{avg_level}**",
                    rank=rank,
                    player_name=self.player_data['username']
                )
            except: pass

        except Exception as e:
            logger.error(f"Finish Error: {e}")

    async def calculate_rank(self, level: int) -> str:
        if level >= 100: return "SS"
        elif level >= 80: return "S"
        elif level >= 60: return "A"
        elif level >= 40: return "B"
        elif level >= 20: return "C"
        elif level >= 10: return "D"
        else: return "E"

class StartAssessmentButton(View):
    def __init__(self, av):
        super().__init__(timeout=60)
        self.av = av
    
    @discord.ui.button(label="بدء الاختبار", style=discord.ButtonStyle.primary, emoji="🚀")
    async def start(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        await self.av.start()

# ============ 3. الأوامر الأساسية ============

@bot.tree.command(name="start", description="بدء رحلة التطوير الذاتي")
async def start_command(interaction: discord.Interaction):
    """بدء عملية التسجيل للاعب الجديد"""
    try:
        discord_id = str(interaction.user.id)
        player = await db.get_player(discord_id)
        
        if player:
            await interaction.response.send_message("✅ أنت مسجل بالفعل في النظام أيها الصياد!", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="👋 مرحباً بك في نظام S.O.L.O",
            description="للبدء في رحلة تطوير ذاتك، يرجى تحديد بياناتك الأساسية بدقة:",
            color=discord.Color.gold()
        )
        embed.set_footer(text="نظام Solo Leveling • التطور لا يتوقف")
        
        await interaction.response.send_message(
            embed=embed, 
            view=RegistrationView(interaction.user.id), 
            ephemeral=True
        )
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await interaction.response.send_message("❌ حدث خطأ تقني، يرجى المحاولة لاحقاً.", ephemeral=True)

@bot.tree.command(name="assessment", description="بدء اختبار القدرات الأولي لتحديد رتبتك (Rank)")
async def assessment_command(interaction: discord.Interaction):
    """تحليل مستوى اللاعب بناءً على الجوانب التي فعلها عند التسجيل"""
    await interaction.response.defer(ephemeral=True)
    
    discord_id = str(interaction.user.id)
    player = await db.get_player(discord_id)
    
    if not player:
        await interaction.followup.send("❌ لم يتم العثور على سجلاتك. يرجى البدء باستخدام `/start` أولاً.", ephemeral=True)
        return
    
    if player.get("assessment_done"):
        await interaction.followup.send("✅ لقد أجريت اختبار القدرات مسبقاً وتم تحديد رتبتك بالفعل.", ephemeral=True)
        return
    
    # جلب كافة الأسئلة المتوفرة في النظام
    all_questions = get_all_assessment_questions()
    filtered_questions = []
    
    # فلترة الأسئلة: نظهر فقط أسئلة الجوانب التي فعلها اللاعب (intensity > 0)
    for q in all_questions:
        # استثناء الجانب الديني لغير المسلمين حتى لو تم اختياره بالخطأ
        if q.category == 'perception' and player.get('faith_type') != 'muslim':
            continue
        
        # التحقق من أن الجانب مفعل (قيمة الشدة أكبر من صفر)
        intensity_key = f"{q.category}_intensity"
        user_intensity = player.get(intensity_key, 0)
        
        if user_intensity > 0:
            filtered_questions.append(q)
            
    if not filtered_questions:
        await interaction.followup.send("⚠️ لم تقم بتفعيل أي جوانب للاختبار. يرجى مراجعة إعداداتك.", ephemeral=True)
        return
    
    # إنشاء واجهة الاختبار
    view = StartAssessmentButton(AssessmentView(player, filtered_questions, interaction, interaction.user.id))
    
    embed = discord.Embed(
        title="📝 تحليل القدرات (Assessment)",
        description=(
            f"سيتم الآن تحليل مستواك بناءً على إجاباتك.\n"
            f"عدد الأسئلة المخصصة لك: **{len(filtered_questions)}**\n\n"
            "⚠️ **تنبيه:** الإجابة بصدق تضمن دقة النتائج ورتبتك النهائية."
        ),
        color=discord.Color.blue()
    )
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="profile", description="عرض بطاقة الصياد الشاملة (الإحصائيات والمعدات)")
async def profile_command(interaction: discord.Interaction):
    """توليد وعرض الصورة الشخصية للصياد"""
    await interaction.response.defer()
    discord_id = str(interaction.user.id)
    
    try:
        # 1. جلب بيانات اللاعب الكاملة
        player = await db.get_player(discord_id)
        if not player:
            await interaction.followup.send("❌ سجل أولاً باستخدام `/start` لتتمكن من رؤية ملفك الشخصي.", ephemeral=True)
            return
        
        # 2. جلب صورة الرتبة المخصصة (بناءً على الرتبة والجنس)
        avatar_query = await db._execute_async(
            lambda: db.client.table('system_rank_images')
            .select('image_url')
            .eq('rank_name', player['rank'])
            .eq('gender', player['gender'])
            .execute()
        )
        
        # 3. جلب المعدات النشطة حالياً (Equipped Items) مع بياناتها الكاملة
        equipment_query = await db._execute_async(
            lambda: db.client.table('player_inventory')
            .select('*, item:system_shop_items(name, rarity, type, image_url, stats)')
            .eq('player_id', player['id'])
            .eq('is_equipped', True)
            .execute()
        )

        # 4. استدعاء محرك توليد الصور
        from image_gen import ProfileGenerator
        gen = ProfileGenerator()
        
        avatar_url = avatar_query.data[0]['image_url'] if avatar_query.data else None
        gear_data = equipment_query.data if equipment_query.data else []

        # توليد الصورة في الذاكرة
        image_buffer = await gen.generate(player, avatar_url, gear_data)
        
        # 5. إرسال الصورة كملف مرفق
        file = discord.File(fp=image_buffer, filename=f"hunter_{player['username']}_profile.png")
        await interaction.followup.send(file=file)

    except Exception as e:
        logger.error(f"Profile Generation Error: {e}")
        await interaction.followup.send("❌ حدث خطأ فني أثناء استخراج بطاقة الصياد. يرجى المحاولة لاحقاً.", ephemeral=True)

@bot.tree.command(name="active_buffs", description="عرض التأثيرات والمضاعفات النشطة حالياً ومدتها")
async def active_buffs_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    player = await db.get_player(str(interaction.user.id))
    if not player:
        await interaction.followup.send("❌ سجل أولاً عبر `/start`!", ephemeral=True)
        return

    # 1. جلب الوقت الحالي بتوقيت مصر (Naive)
    now = datetime.now()
    now_iso = now.isoformat()

    # 2. استعلام لجلب البفات التي لم تنتهِ بعد
    # نستخدم التحقق البرمجي لاحقاً لضمان الدقة القصوى مع التوقيت
    res = await db._execute_async(lambda: db.client.table('player_buffs')
        .select('*')
        .eq('player_id', player['id'])
        .execute())

    if not res.data:
        await interaction.followup.send("🧊 لا توجد تأثيرات نشطة حالياً. استخدم بعض الجرعات من حقيبتك!", ephemeral=True)
        return

    embed = discord.Embed(title="✨ التأثيرات والمضاعفات النشطة", color=discord.Color.gold())
    active_count = 0

    for buff in res.data:
        try:
            raw_expiry = buff['expires_at'].replace('Z', '+00:00')
            if '.' in raw_expiry:
                main_part, remainder = raw_expiry.split('.')
                tz_sign = '+' if '+' in remainder else '-' if '-' in remainder else None
                if tz_sign:
                    ms_part, tz_part = remainder.split(tz_sign, 1)
                    ms_part = (ms_part + "000000")[:6]
                    raw_expiry = f"{main_part}.{ms_part}{tz_sign}{tz_part}"
                else:
                    ms_part = (remainder + "000000")[:6]
                    raw_expiry = f"{main_part}.{ms_part}"

            expiry_aware = datetime.fromisoformat(raw_expiry)
            expiry_naive = expiry_aware.astimezone().replace(tzinfo=None)

            # حساب الوقت المتبقي
            remaining = expiry_naive - now
            
            # عرض فقط التأثيرات التي لم تنتهِ فعلياً
            if remaining.total_seconds() > 0:
                active_count += 1
                hours, remainder_secs = divmod(int(remaining.total_seconds()), 3600)
                minutes, _ = divmod(remainder_secs, 60)
                
                time_text = f"{hours} ساعة و {minutes} دقيقة" if hours > 0 else f"{minutes} دقيقة"
                
                embed.add_field(
                    name=f"🔹 {buff['buff_name']}",
                    value=f"⏳ المتبقي: **{time_text}**\n📊 النوع: `{buff['buff_type']}`",
                    inline=False
                )
        except Exception as e:
            print(f"⚠️ خطأ في معالجة بف {buff['id']}: {e}")
            continue

    if active_count == 0:
        await interaction.followup.send("🧊 جميع التأثيرات انتهت صلاحيتها.", ephemeral=True)
        return

    embed.set_footer(text="نظام S.O.L.O • المؤثرات الزمنية")
    await interaction.followup.send(embed=embed, ephemeral=True)
    
# ============ 4. أوامر الاقتصاد والمخزن ============

@bot.tree.command(name="shop", description="فتح متجر النظام لشراء المعدات والمواد الاستهلاكية")
async def shop_command(interaction: discord.Interaction):
    """فتح واجهة المتجر التفاعلية"""
    discord_id = str(interaction.user.id)
    player = await db.get_player(discord_id)
    
    if not player:
        await interaction.response.send_message("❌ لم يتم العثور على حسابك. يرجى التسجيل أولاً عبر `/start`.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # تهيئة واجهة المتجر مع رصيد اللاعب الحالي
    # تمرير player['id'] وهو الـ UUID الخاص بقاعدة البيانات
    view = ShopView(
        user_id=interaction.user.id, 
        player_uuid=player['id'], # ✅ السطر الجديد
        user_coins=player.get('coins', 0), 
        user_gems=player.get('gems', 0)
    )
    
    await view.load_items() # جلب العناصر المتاحة من قاعدة البيانات
    await view.update_view(interaction) # توليد الصورة وعرض المتجر

@bot.tree.command(name="inventory", description="فتح الحقيبة لإدارة المعدات واستخدام العناصر")
async def inventory_command(interaction: discord.Interaction):
    """عرض حقيبة اللاعب وإدارة التجهيزات"""
    discord_id = str(interaction.user.id)
    player = await db.get_player(discord_id)
    
    if not player:
        await interaction.response.send_message("❌ يجب أن تملك حساباً لتتمكن من الوصول للحقيبة. استخدم `/start`.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    
    # ✅ نمرر كائن الـ bot هنا لأن واجهة الحقيبة تحتاج للوصول للـ Cogs لتشغيل البوابات الخاصة
    view = InventoryView(interaction.user.id, player, bot)
    
    await view.load_inventory() # جلب ممتلكات اللاعب
    await view.update_view(interaction) # توليد صورة الحقيبة والعرض
    
    
# ============ 5. أوامر التحكم والإعدادات ============

@bot.tree.command(name="settings", description="فتح قائمة الإعدادات (الجوانب، الإشعارات، والحالة)")
async def settings_command(interaction: discord.Interaction):
    """عرض واجهة الإعدادات لتخصيص تجربة اللاعب"""
    await interaction.response.defer(ephemeral=True)
    
    player = await db.get_player(str(interaction.user.id))
    if not player:
        await interaction.followup.send("❌ لم يتم العثور على حسابك. يرجى التسجيل أولاً.", ephemeral=True)
        return
        
    embed = discord.Embed(
        title="⚙️ مركز تحكم الصياد", 
        description="من هنا يمكنك تخصيص إعدادات النظام وتحديث حالتك الحالية.", 
        color=discord.Color.light_grey()
    )
    
    # استدعاء SettingsView من ملف settings.py
    view = SettingsView(interaction.user.id, player)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="set_title", description="اختيار اللقب النشط الذي يظهر في بطاقتك")
async def set_title_command(interaction: discord.Interaction):
    """تغيير لقب اللاعب من قائمة الألقاب التي قام بفتحها"""
    player = await db.get_player(str(interaction.user.id))
    if not player:
        await interaction.response.send_message("❌ سجل أولاً لتتمكن من الحصول على ألقاب.", ephemeral=True)
        return
    
    # جلب الألقاب المفتوحة أو وضع لقب "مبتدئ" كافتراضي
    titles = player.get('unlocked_titles', [])
    if not titles:
        titles = ["مبتدئ"]
    
    # ديسكورد يسمح بـ 25 خياراً بحد أقصى في القائمة المنسدلة
    options = [discord.SelectOption(label=str(t), value=str(t)) for t in titles[:25]]
    
    view = View()
    select = Select(placeholder="اختر اللقب الذي تريده...", options=options)
    
    async def title_callback(i: discord.Interaction):
        if i.user.id != interaction.user.id: 
            await i.response.send_message("🛑 هذه القائمة ليست لك!", ephemeral=True)
            return
            
        selected_title = select.values[0]
        await db.update_player(str(i.user.id), {'active_title': selected_title})
        await i.response.send_message(f"✅ تم تحديث لقبك بنجاح إلى: **{selected_title}**", ephemeral=True)
        
    select.callback = title_callback
    view.add_item(select)
    await interaction.response.send_message("📜 قائمة ألقابك المتاحة:", view=view, ephemeral=True)

@bot.tree.command(name="give", description="[إدارة] منح موارد أو نقاط خبرة للاعب محدد")
@app_commands.choices(resource=[
    app_commands.Choice(name="Gold Coins 🪙", value="coins"),
    app_commands.Choice(name="Gems 💎", value="gems"),
    app_commands.Choice(name="Energy ⚡", value="energy"),
    app_commands.Choice(name="Strength XP 💪", value="strength_xp"),
    app_commands.Choice(name="Intelligence XP 🧠", value="intelligence_xp"),
    app_commands.Choice(name="Vitality XP ❤️", value="vitality_xp"),
    app_commands.Choice(name="Agility XP 🤝", value="agility_xp"),
    app_commands.Choice(name="Perception XP 🕌", value="perception_xp"),
    app_commands.Choice(name="Freedom XP 💸", value="freedom_xp")
])
async def give_command(interaction: discord.Interaction, player: discord.Member, resource: app_commands.Choice[str], amount: int):
    """أمر إداري لزيادة موارد اللاعبين (للأدمن فقط)"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔ عذراً، هذا الأمر مخصص لقادة النقابة (Administrators) فقط.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    
    # تحويل اسم المورد إلى اسم العمود الصحيح في قاعدة البيانات
    db_column = "current_energy" if resource.value == "energy" else resource.value
    
    target_player = await db.get_player(str(player.id))
    if target_player:
        current_val = target_player.get(db_column, 0)
        # التأكد من أن القيمة لا تصبح سالبة (في حال كان الـ amount سالباً)
        new_val = max(0, current_val + amount)
        
        await db.update_player(str(player.id), {db_column: new_val})
        await interaction.followup.send(f"✅ تم تعديل **{resource.name}** لـ {player.mention}. القيمة الجديدة: **{new_val:,}**")
        
        # إرسال تنبيه للاعب في الخاص (اختياري)
        try:
            await player.send(f"🎁 تم منحك **{amount}** من **{resource.name}** بواسطة الإدارة!")
        except: pass
    else:
        await interaction.followup.send(f"❌ اللاعب {player.display_name} غير مسجل في النظام.", ephemeral=True)
        
# ============ 6. أوامر المعلومات (Information) ============

@bot.tree.command(name="leaderboard", description="عرض لوحة الشرف لأقوى الصيادين")
async def leaderboard_command(interaction: discord.Interaction):
    """عرض قائمة المتصدرين بناءً على المستوى والخبرة الكلية"""
    await interaction.response.defer()
    
    # استعلام لجلب أفضل 10 لاعبين مرتبين حسب المستوى ثم الخبرة
    res = await db._execute_async(
        lambda: db.client.table('players')
        .select('username, rank, active_title, total_level, total_xp')
        .order('total_level', desc=True)
        .order('total_xp', desc=True)
        .limit(10).execute()
    )
    
    if not res.data:
        await interaction.followup.send("📭 قائمة المتصدرين فارغة حالياً.", ephemeral=True)
        return
        
    embed = discord.Embed(title="🏆 قائمة أقوى الصيادين (Top 10)", color=discord.Color.gold())
    txt = ""
    for i, p in enumerate(res.data, 1):
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"#{i}"
        title = p.get('active_title', 'مبتدئ')
        txt += f"{medal} │ **[{title}]** {p['username']} (Rank {p['rank']} • Lv.{p['total_level']})\n"
    
    embed.description = txt
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="help", description="عرض دليل الصياد والأوامر المتاحة في النظام")
async def help_command(interaction: discord.Interaction):
    """عرض المساعدة التفصيلية المصنفة حسب الوظائف"""
    
    # التحقق من الصلاحيات بشكل آمن
    is_admin = False
    if interaction.guild:
        is_admin = interaction.user.guild_permissions.administrator
    
    embed = discord.Embed(
        title="📘 **دليل نظام S.O.L.O - النسخة الماستر**",
        description="مرحباً بك أيها الصياد. إليك قائمة بالأدوات المتاحة لتطوير قدراتك والارتقاء برتبتك.",
        color=discord.Color.gold()
    )
    
    # 1. قسم البداية والملف الشخصي
    embed.add_field(
        name="👤 **بيانات الصياد الأساسية**",
        value=(
            "▸ `/start`: إنشاء ملفك الشخصي وبدء الرحلة.\n"
            "▸ `/assessment`: اختبار القدرات الأولي لتحديد رتبتك.\n"
            "▸ `/profile`: عرض بطاقتك الشخصية الشاملة.\n"
            "▸ `/career`: عرض سجل إنجازاتك ومسيرتك التاريخية."
        ),
        inline=False
    )
    
    # 2. قسم البوابات والغارات
    embed.add_field(
        name="⚔️ **نظام البوابات (Dungeons)**",
        value=(
            "▸ `/my_gates`: عرض البوابات النشطة التي تشارك فيها.\n"
            "▸ `/invite [player]`: دعوة صياد آخر لبوابتك الخاصة.\n"
            "▸ `/portal_history`: سجل آخر 10 بوابات تم رصدها."
        ),
        inline=False
    )

    # 3. قسم رادار التدريب (أوامر الـ XP الستة)
    embed.add_field(
        name="🏋️ **رادار جوانب القوة (Aspects)**",
        value=(
            "▸ `/strength` | `/intelligence` | `/vitality` \n"
            "▸ `/agility` | `/perception` | `/freedom` \n"
            "*عرض مستوى كل جانب بدقة مع شريط التقدم واللقب.*"
        ),
        inline=False
    )
    
    # 4. قسم الاقتصاد والتأثيرات
    embed.add_field(
        name="🛒 **المعدات والمؤثرات**",
        value=(
            "▸ `/shop`: فتح المتجر لشراء العتاد والجرعات.\n"
            "▸ `/inventory`: إدارة حقيبتك، ارتداء المعدات، واستخدام العناصر.\n"
            "▸ `/active_buffs`: عرض التأثيرات والمضاعفات النشطة حالياً.\n"
            "▸ `/my_penalties`: التحقق من العقوبات المالية المعلقة."
        ),
        inline=False
    )

    # 5. قسم المعلومات العامة والإعدادات
    embed.add_field(
        name="⚙️ **النظام والمعلومات العامة**",
        value=(
            "▸ `/settings`: تخصيص حسابك (الحالة، الجوانب، الإشعارات).\n"
            "▸ `/set_title`: اختيار اللقب النشط الذي يظهر للعامة.\n"
            "▸ `/leaderboard`: قائمة أقوى 10 صيادين في السيرفر.\n"
            "▸ `/levels_info`: شرح نظام الرتب والمستويات التصاعدي.\n"
            "▸ `/stats`: إحصائيات عامة عن عدد الصيادين المسجلين."
        ),
        inline=False
    )
    
    # 6. قسم الآدمن (يظهر فقط للمشرفين)
    if is_admin:
        embed.add_field(
            name="🛡️ **أدوات الإدارة (Admin Only)**",
            value=(
                "▸ `/give [player] [resource] [amount]`: منح موارد للاعب.\n"
                "▸ `/schedule_portal`: جدولة بوابة عامة يدوياً.\n"
                "▸ `/reset_me`: حذف الحساب للتجربة."
            ),
            inline=False
        )
    
    embed.set_footer(text="System V1.2 • نظام Solo Leveling المطور")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
@bot.tree.command(name="levels_info", description="شرح شامل لنظام المستويات والرتب")
async def levels_info_command(interaction: discord.Interaction):
    """عرض معلومات نظام المستويات والرتب"""
    
    # تعريف الرتب بناءً على المنطق البرمجي (E<10, D<20, C<40, B<60, A<80, S<100, SS>=100)
    embed = discord.Embed(
        title="📊 **دليل النظام: المستويات والرتب**",
        description=(
            "يعتمد النظام على **معادلة تصاعدية (Exponential)** تحاكي تطور الإنسان الحقيقي.\n"
            "الوصول للمستويات الأولى سهل وسريع، ولكن القمة تتطلب سنوات من الالتزام."
        ),
        color=discord.Color.blue()
    )

    # 1. الهيكلية الأساسية
    embed.add_field(
        name="🎯 **هيكلية النظام**",
        value=(
            "**• الحد الأقصى:** المستوى 120 (Max Level)\n"
            "**• المدى الزمني:** صُمم ليتم ختمه في **10 سنوات**.\n"
            "**• الصعوبة:** كلما زاد مستواك، زاد الـ XP المطلوب للمستوى التالي."
        ),
        inline=False
    )

    # 2. سلم الرتب (Rank Thresholds)
    embed.add_field(
        name="🏆 **سلم الرتب (Rank Thresholds)**",
        value=(
            "⚪ **E-Rank:** Lv. 1 ➔ 9 (مبتدئ)\n"
            "🟢 **D-Rank:** Lv. 10 ➔ 19\n"
            "🔵 **C-Rank:** Lv. 20 ➔ 39\n"
            "🟣 **B-Rank:** Lv. 40 ➔ 59 (محترف)\n"
            "🔴 **A-Rank:** Lv. 60 ➔ 79\n"
            "🟡 **S-Rank:** Lv. 80 ➔ 99 (القمة البشرية)\n"
            "👑 **SS-Rank:** Lv. 100+ (عاهل الظلال)"
        ),
        inline=False
    )

    # 3. مصادر الخبرة
    embed.add_field(
        name="💡 **كيف تزيد مستواك؟**",
        value=(
            "1️⃣ **المهام اليومية:** المصدر الأساسي للنمو.\n"
            "2️⃣ **البوابات (Dungeons):** تحديات كبرى لقفزات XP هائلة.\n"
            "3️⃣ **المعدات:** استخدام عناصر تزيد نسبة كسب الخبرة (XP Boost)."
        ),
        inline=False
    )

    # 4. وتيرة التقدم
    embed.add_field(
        name="⏳ **وتيرة التقدم المتوقعة**",
        value=(
            "• **أول شهر:** الوصول لـ Lv.20\n"
            "• **أول سنة:** الوصول لـ Lv.50\n"
            "• **المستويات 100+:** تتطلب التزاماً أسطورياً."
        ),
        inline=False
    )

    embed.set_footer(text="System V1.0 • Solo Leveling Bot")
    
    # إرسال الرسالة
    await interaction.response.send_message(embed=embed)

# ============ تابع 6. أوامر المعلومات والتحكم ============

@bot.tree.command(name="stats", description="إحصائيات السيرفر العامة")
async def stats_command(interaction: discord.Interaction):
    """عرض إحصائيات سريعة عن عدد اللاعبين المسجلين"""
    await interaction.response.defer()
    count = await db.get_player_count()
    await interaction.followup.send(f"📊 عدد الصيادين الذين انضموا للنظام حتى الآن: **{count}**")

@bot.tree.command(name="my_penalties", description="عرض قائمة العقوبات المعلقة الخاصة بك")
async def my_penalties_command(interaction: discord.Interaction):
    """التحقق من وجود أي عقوبات لم يتم سدادها"""
    await interaction.response.defer(ephemeral=True)
    player = await db.get_player(str(interaction.user.id))
    if not player: 
        await interaction.followup.send("❌ يرجى التسجيل أولاً.", ephemeral=True)
        return
    
    # جلب العقوبات التي حالتها "معلقة"
    penalties = await db._execute_async(
        lambda: db.client.table('penalties')
        .select('*')
        .eq('player_id', player['id'])
        .eq('status', 'pending')
        .execute()
    )
    
    if not penalties.data:
        await interaction.followup.send("✅ سجلك نظيف تماماً، لا توجد عقوبات معلقة!", ephemeral=True)
    else:
        await interaction.followup.send(f"⚠️ تحذير: لديك **{len(penalties.data)}** عقوبات معلقة يجب التعامل معها.", ephemeral=True)

@bot.tree.command(name="penalty_test", description="[تطوير] تجربة نظام العقوبات")
async def penalty_test_command(interaction: discord.Interaction):
    """أمر مخصص للمطورين لاختبار ظهور العقوبات"""
    await interaction.response.send_message("⚠️ هذا الأمر مخصص لأغراض التطوير فقط ولا يقوم بتنفيذ عمليات حالياً.", ephemeral=True)

@bot.tree.command(name="reset_me", description="حذف حسابك الحالي بالكامل من النظام")
async def reset_me_command(interaction: discord.Interaction):
    """حذف بيانات اللاعب مع طلب تأكيد لضمان عدم الحذف بالخطأ"""
    class Confirm(View):
        def __init__(self): 
            super().__init__(timeout=60)
            
        @discord.ui.button(label="تأكيد حذف الحساب نهائياً", style=discord.ButtonStyle.danger)
        async def confirm(self, i: discord.Interaction, b: discord.ui.Button):
            if i.user.id != interaction.user.id: 
                return
            await db.client.table('players').delete().eq('discord_id', str(i.user.id)).execute()
            await i.response.send_message("✅ تم مسح جميع بياناتك من السجلات. يمكنك البدء من جديد عبر `/start`.", ephemeral=True)
            
    await interaction.response.send_message("⚠️ **تحذير:** هل أنت متأكد من رغبتك في حذف حسابك؟ لا يمكن التراجع عن هذا الإجراء.", view=Confirm(), ephemeral=True)

@bot.tree.command(name="career", description="عرض السجل التاريخي وإحصائيات المسيرة المهنية للصياد")
async def career_command(interaction: discord.Interaction):
    """عرض إحصائيات مفصلة عن إنجازات اللاعب منذ انضمامه"""
    await interaction.response.defer()
    
    discord_id = str(interaction.user.id)
    player = await db.get_player(discord_id)
    
    if not player:
        await interaction.followup.send("❌ لم يتم العثor على بياناتك، سجل أولاً!", ephemeral=True)
        return

    # --- معالجة التاريخ لضمان التوافق ومنع أخطاء Naive/Aware ---
    try:
        # تنظيف صيغة التاريخ القادمة من Supabase
        created_str = player['created_at'].replace('Z', '').split('.')[0]
        created_dt = datetime.fromisoformat(created_str)
        
        # إزالة المنطقة الزمنية للمقارنة مع utcnow
        if created_dt.tzinfo is not None:
            created_dt = created_dt.replace(tzinfo=None)
        
        days_joined = (datetime.utcnow() - created_dt).days
        join_date = created_dt.strftime("%Y-%m-%d")
        
    except Exception as e:
        logger.error(f"Career Date Calculation Error: {e}")
        days_joined = 0
        join_date = "غير متوفر"
    
    # بناء البطاقة الإحصائية
    embed = discord.Embed(title=f"📜 مسيرة الصياد: {player['username']}", color=discord.Color.gold())
    embed.add_field(name="📅 تاريخ الانضمام", value=f"{join_date} (منذ {days_joined} يوم)", inline=True)
    
    # إحصائيات المهام اليومية
    q_total = player.get('quests_total', 0)
    q_done = player.get('quests_completed', 0)
    q_rate = int((q_done / q_total * 100)) if q_total > 0 else 0
    embed.add_field(name="📝 سجل المهام اليومية", value=f"✅ منجز: **{q_done}**\n📥 إجمالي: **{q_total}**\n📊 نسبة الالتزام: **{q_rate}%**", inline=False)
    
    # إحصائيات البوابات (Dungeons)
    priv_total = player.get('private_portals_opened', 0)
    priv_done = player.get('private_portals_cleared', 0)
    embed.add_field(name="🔑 البوابات الخاصة", value=f"مفتوحة: **{priv_total}**\nناجحة: **{priv_done}**", inline=True)

    pub_total = player.get('public_portals_joined', 0)
    pub_done = player.get('public_portals_cleared', 0)
    embed.add_field(name="⚔️ الغارات العامة", value=f"مشاركة: **{pub_total}**\nناجحة: **{pub_done}**", inline=True)
    
    embed.set_footer(text=f"معرف النظام: {discord_id}")
    await interaction.followup.send(embed=embed)   
    
# ============ دالة عرض حالة الجانب (Aspect Analyzer) ============

async def show_aspect_status(interaction: discord.Interaction, category: str):
    """دالة مصلحة لعرض حالة الجانب بدقة رياضية"""
    await interaction.response.defer()
    
    player = await db.get_player(str(interaction.user.id))
    if not player:
        await interaction.followup.send("❌ لم يتم العثور على سجلاتك.")
        return

    # 1. جلب إجمالي الخبرة من قاعدة البيانات
    total_xp = player.get(f"{category}_xp", 0)
    
    # 2. حساب المستوى والتقدم (xp_needed هنا هي القيمة الإجمالية للمستوى الحالي)
    current_level, xp_in_level, xp_needed = calculate_level_progressive(total_xp)
    
    # 3. جلب الـ Buffs النشطة
    now = datetime.now()
    buffs_res = await db._execute_async(lambda: db.client.table('player_buffs')
        .select('*')
        .eq('player_id', player['id'])
        .gt('expires_at', now.isoformat())
        .execute())
    
    active_boost = 0
    boost_text = ""
    for buff in buffs_res.data:
        if category in buff['buff_type'] or "all" in buff['buff_type']:
            active_boost += int(buff['value'] * 100)
    
    if active_boost > 0:
        boost_text = f"\n🧪 **تأثير نشط:** زيادة `+{active_boost}%` XP"

    # 4. إعدادات العرض
    cats_info = {
        "strength": ("القوة البدنية", "💪", discord.Color.red()),
        "intelligence": ("الذكاء والمعرفة", "🧠", discord.Color.blue()),
        "vitality": ("الصحة والعافية", "❤️", discord.Color.green()),
        "agility": ("المهارات الاجتماعية", "🤝", discord.Color.orange()),
        "perception": ("الجانب الديني", "🕌", discord.Color.purple()),
        "freedom": ("الحرية المالية", "💸", discord.Color.gold())
    }
    cat_name, emoji, color = cats_info[category]

    embed = discord.Embed(title=f"{emoji} تحليل الجانب: {cat_name}", color=color)
    embed.set_author(name=f"الصياد: {player['username']}", icon_url=interaction.user.display_avatar.url)
    
    # ✅ التصحيح الرياضي هنا: نستخدم xp_needed مباشرة كـ "مقـام"
    progress_bar = draw_progress_bar(xp_in_level, xp_needed)
    
    embed.add_field(name="📊 المستوى الحالي", value=f"**Level {current_level}**", inline=True)
    embed.add_field(name="📜 اللقب المكتسب", value=f"`{player.get('active_title', 'مبتدئ')}`", inline=True)
    
    # ✅ التصحيح هنا أيضاً في نص الـ XP
    xp_display = f"`{xp_in_level:,} / {xp_needed:,} XP`"
    if xp_needed == 0: xp_display = "`MAX LEVEL REACHED`"
        
    embed.add_field(name="📈 شريط التقدم", value=f"{progress_bar}\n{xp_display}{boost_text}", inline=False)
    embed.set_footer(text=f"نظام S.O.L.O • {cat_name}")

    await interaction.followup.send(embed=embed)

# ============ الأوامر الستة (The 6 Aspect Commands) ============

@bot.tree.command(name="strength", description="عرض مستوى القوة البدنية والتقدم")
async def strength_cmd(interaction: discord.Interaction):
    await show_aspect_status(interaction, "strength")

@bot.tree.command(name="intelligence", description="عرض مستوى الذكاء والمعرفة والتقدم")
async def intelligence_cmd(interaction: discord.Interaction):
    await show_aspect_status(interaction, "intelligence")

@bot.tree.command(name="vitality", description="عرض مستوى الصحة والنشاط الحيوي والتقدم")
async def vitality_cmd(interaction: discord.Interaction):
    await show_aspect_status(interaction, "vitality")

@bot.tree.command(name="agility", description="عرض مستوى المهارات الاجتماعية والمرونة")
async def agility_cmd(interaction: discord.Interaction):
    await show_aspect_status(interaction, "agility")

@bot.tree.command(name="perception", description="عرض مستوى الجانب الديني والتفكر")
async def perception_cmd(interaction: discord.Interaction):
    await show_aspect_status(interaction, "perception")

@bot.tree.command(name="freedom", description="عرض مستوى الحرية المالية والنمو المادي")
async def freedom_cmd(interaction: discord.Interaction):
    await show_aspect_status(interaction, "freedom")
    
# ============ أوامر الصيانة (Admin & Owner Only) ============
# ملاحظة: الأوامر ببادئة "!" تعمل حتى لو فشلت أوامر السلاش (Slash Commands)

@bot.command(name="clear_guild")
@commands.is_owner() # متاح فقط لصاحب البوت المسجل في Developer Portal
async def clear_guild_commands(ctx):
    """حذف أوامر السيرفر الحالي المخصصة (لإزالة تكرار الأوامر)"""
    bot.tree.clear_commands(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send("✅ **تم تنظيف قاعدة بيانات أوامر السيرفر!**\nالآن ستظهر الأوامر العالمية فقط. (قد يتطلب الأمر إعادة تشغيل تطبيق الديسكورد لرؤية التغيير).")

@bot.tree.command(name="sync_admin", description="[إدارة] مزامنة أوامر البوت يدوياً مع خوادم ديسكورد")
async def sync_admin(interaction: discord.Interaction):
    """أمر سلاش للمزامنة العالمية السريعة للأوامر"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔ هذا الأمر مخصص لمدراء السيرفر فقط.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(f"✅ تمت مزامنة **{len(synced)}** أمر سلاش عالمياً بنجاح!")
    except Exception as e:
        logger.error(f"Sync Error: {e}")
        await interaction.followup.send("❌ فشلت عملية المزامنة. راجع سجلات البوت (Logs).")

@bot.command(name="sync")
@commands.is_owner()
async def sync_prefix_command(ctx):
    """أمر ببادئة ! للمزامنة الشاملة (للمالك فقط)"""
    await ctx.send("🔄 جاري بدء المزامنة العالمية الشاملة...")
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"✅ تمت عملية المزامنة بنجاح! إجمالي الأوامر النشطة: **{len(synced)}**")
    except Exception as e:
        await ctx.send(f"❌ حدث خطأ أثناء المزامنة: {e}")
    
# ============ أحداث التشغيل (Events) ============

@bot.event
async def on_ready():
    """يتم استدعاؤها عندما يصبح البوت متصلاً بالإنترنت وجاهزاً للاستخدام"""
    logger.info(f"🚀 تم تشغيل النظام بنجاح!")
    logger.info(f"🤖 اسم البوت: {bot.user.name}")
    logger.info(f"🆔 معرف البوت: {bot.user.id}")
    logger.info(f"📅 الوقت الحالي: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # تحديث الحالة (Presence)
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, 
            name="تطور الصيادين ⚔️"
        )
    )

# ============ تشغيل المحرك (Main Block) ============

if __name__ == "__main__":
    # استخراج توكن البوت من ملف البيئة .env
    token = os.getenv("DISCORD_TOKEN")
    
    if not token:
        logger.critical("❌ خطأ فادح: لم يتم العثور على DISCORD_TOKEN في ملف .env!")
        exit(1)
        
    try:
        bot.run(token)
    except discord.errors.LoginFailure:
        logger.critical("❌ خطأ: توكن البوت غير صحيح!")
    except Exception as e:
        logger.critical(f"❌ حدث خطأ غير متوقع أثناء التشغيل: {e}")