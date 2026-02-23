import discord
from discord import app_commands
from discord.ext import tasks, commands
from discord.ui import View, Button, Modal, TextInput, Select
from discord import ButtonStyle
import os
import random
import asyncio
import logging
from datetime import datetime, timedelta
from hijri_converter import Gregorian

# ============ استيراد ملفات المشروع الداخلية ============
from database import db
import task_logic
from task_logic import draw_progress_bar
from tasks_library import ALL_TASKS

# إعداد السجلات للمحرك
logger = logging.getLogger(__name__)

# ============ 1. النوافذ المنبثقة (Modals) ============
# ملاحظة: تم وضعها في البداية ليتمكن كلاس اللوحة من استدعائها

# ============ 1. النوافذ المنبثقة (Modals) ============
# مكانها الصحيح: في بداية الملف قبل QuestDashboard

class CaffeineModal(Modal, title="☕ سجل استهلاك الكافيين"):
    coffee = TextInput(label="عدد أكواب القهوة ☕", placeholder="0", default="0", min_length=1, max_length=3)
    tea = TextInput(label="عدد أكواب الشاي 🍵", placeholder="0", default="0", min_length=1, max_length=3)

    def __init__(self, task_id, task_info, dashboard_view):
        super().__init__()
        self.task_id, self.task_info, self.dashboard_view = task_id, task_info, dashboard_view

    async def on_submit(self, interaction: discord.Interaction):
        # 1. التمهل (Defer)
        await interaction.response.defer(ephemeral=True)
        try:
            c_val, t_val = float(self.coffee.value), float(self.tea.value)
            score_pct, _ = task_logic.calculate_caffeine(c_val, t_val)
            
            xp_gained = int(self.task_info.get('xp_reward', 0) * score_pct)
            
            await db.upsert_daily_quest({
                "player_id": self.dashboard_view.player_id, "task_id": self.task_id,
                "performed_data": {"coffee": c_val, "tea": t_val}, "xp_gained": xp_gained,
                "is_completed": score_pct == 1.0, "log_date": datetime.now().date().isoformat()
            })
            
            # ✅ تحديث المستوى فوراً
            await db.recalculate_player_stats(self.dashboard_view.player_id)

            msg = f"✅ تم التسجيل. الخبرة: +{xp_gained}"
            if score_pct < 1.0: msg += "\n⚠️ تنبيه: تجاوزت الحد!"
            
            await interaction.followup.send(msg, ephemeral=True)
            await self.dashboard_view.back_to_main(interaction)
        except ValueError:
            await interaction.followup.send("❌ أدخل أرقاماً فقط.", ephemeral=True)

class NumericTaskModal(Modal):
    def __init__(self, task_id, task_info, dashboard_view):
        super().__init__(title=task_info['title'])
        self.task_id, self.task_info, self.dashboard_view = task_id, task_info, dashboard_view
        self.value_input = TextInput(label=f"الكمية ({task_info.get('unit', 'وحدة')})", placeholder="أدخل الرقم...")
        self.add_item(self.value_input)

    async def on_submit(self, interaction: discord.Interaction):
        # 1. التمهل (Defer)
        await interaction.response.defer(ephemeral=True)
        try:
            val = float(self.value_input.value)
            p = await db.get_player(str(interaction.user.id))
            target = float(self.task_info.get('targets', {}).get(p.get('age_group', 'young'), 1.0))
            if target <= 0: target = 1.0
            
            progress = min(1.0, val / target)
            xp = int(self.task_info.get('xp_reward', 0) * progress)

            await db.upsert_daily_quest({
                "player_id": self.dashboard_view.player_id, "task_id": self.task_id,
                "performed_data": {"value": val, "expected": target}, "xp_gained": xp,
                "is_completed": progress >= 1.0, "log_date": datetime.now().date().isoformat()
            })
            
            # ✅ تحديث المستوى فوراً
            await db.recalculate_player_stats(self.dashboard_view.player_id)

            await interaction.followup.send(f"✅ تم التسجيل ({int(progress*100)}%)", ephemeral=True)
            await self.dashboard_view.back_to_main(interaction)
        except:
            await interaction.followup.send("❌ أدخل رقماً صحيحاً.", ephemeral=True)
            
class QuestDashboard(View):
    """
    لوحة التحكم الشاملة (نظام الملاحة - Single Message Navigation)
    """
    def __init__(self, player_id, discord_snowflake_id, task_list):
        super().__init__(timeout=None)
        self.player_id = player_id
        self.discord_snowflake_id = int(discord_snowflake_id)
        self.task_list = task_list
        # نبدأ ببناء الواجهة الرئيسية فوراً
        self.build_main_ui()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.discord_snowflake_id:
            await interaction.response.send_message("🛑 هذه اللوحة مخصصة لصياد آخر!", ephemeral=True)
            return False
        return True

    # =================================================
    # 1. الواجهة الرئيسية (Main Menu)
    # =================================================
    def build_main_ui(self):
        self.clear_items()
        
        aspect_options = [
            discord.SelectOption(label="القوة البدنية 💪", value="strength", emoji="💪"),
            discord.SelectOption(label="الذكاء والمعرفة 🧠", value="intelligence", emoji="🧠"),
            discord.SelectOption(label="الصحة والعافية ❤️", value="vitality", emoji="❤️"),
            discord.SelectOption(label="الجانب الاجتماعي 🤝", value="agility", emoji="🤝"),
            discord.SelectOption(label="الجانب الديني 🕌", value="perception", emoji="🕌"),
            discord.SelectOption(label="الحرية المالية والعمل 💸", value="freedom", emoji="💸"),
        ]
        
        select = Select(placeholder="اختر قسماً لعرض مهامه...", options=aspect_options, custom_id=f"main_sel_{self.player_id}")
        select.callback = self.aspect_callback
        self.add_item(select)

    async def aspect_callback(self, interaction: discord.Interaction):
        # الانتقال لقائمة مهام القسم
        selected_aspect = interaction.data['values'][0]
        await self.show_tasks_list(interaction, selected_aspect)

    # =================================================
    # 2. قائمة مهام القسم (Tasks List)
    # =================================================
    async def show_tasks_list(self, interaction: discord.Interaction, category):
        self.clear_items()
        
        # دمج العمل مع المال
        target_cats = [category]
        if category == "freedom": target_cats.append("work")
        
        filtered = {tid: info for tid, info in self.task_list.items() if info.get('category') in target_cats}
        
        if not filtered:
            await interaction.response.send_message("لا توجد مهام نشطة هنا.", ephemeral=True)
            # إعادة رسم الرئيسية
            self.build_main_ui()
            await self.update_dashboard_embed(interaction)
            return

        # قائمة المهام
        options = [discord.SelectOption(label=info['title'], value=tid) for tid, info in filtered.items()]
        select = Select(placeholder=f"اختر مهمة من {category}...", options=options, custom_id=f"task_sel_{self.player_id}")
        
        async def task_cb(i):
            await self.show_task_details(i, select.values[0])
            
        select.callback = task_cb
        self.add_item(select)
        
        # زر رجوع
        back = Button(label="رجوع للرئيسية", style=ButtonStyle.secondary, row=1)
        back.callback = self.back_to_main
        self.add_item(back)
        
        # تحديث الرسالة (بدون تغيير الـ Embed، فقط الأزرار)
        await interaction.response.edit_message(view=self)

    # =================================================
    # 3. تفاصيل المهمة (Task Details & Action)
    # =================================================
    async def show_task_details(self, interaction: discord.Interaction, task_id):
        self.clear_items()
        task_info = self.task_list.get(task_id)
        
        # زر التنفيذ
        t_type = task_info.get('type')
        btn = Button(label="تسجيل الإنجاز ✍️", style=ButtonStyle.success)
        
        if t_type in ["modal_numeric", "modal_dual"]:
            btn.callback = lambda i: self.open_modal_handler(i, task_id, task_info)
        elif t_type == "confirm":
            btn.callback = lambda i: self.process_simple_confirm(i, task_id, task_info)
        elif t_type in ["select", "buttons"]:
            btn.label = "عرض الخيارات"
            btn.callback = lambda i: self.show_options_ui(i, task_id, task_info)
            
        self.add_item(btn)
        
        # زر رجوع
        back = Button(label="رجوع للقائمة", style=ButtonStyle.secondary)
        back.callback = lambda i: self.show_tasks_list(i, task_info.get('category'))
        self.add_item(back)
        
        # تحديث الـ Embed ليشرح المهمة
        embed = interaction.message.embeds[0]
        embed.title = f"🎯 {task_info['title']}"
        embed.description = f"{task_info['description']}\n\n*اضغط الزر أدناه للتسجيل.*"
        embed.color = discord.Color.gold()
        embed.clear_fields()
        
        await interaction.response.edit_message(embed=embed, view=self)

    # =================================================
    # 4. دوال المعالجة (Handlers)
    # =================================================
    
    async def back_to_main(self, interaction):
        self.build_main_ui()
        await self.update_dashboard_embed(interaction)

    async def open_modal_handler(self, interaction, task_id, task_info):
        if task_info['type'] == "modal_dual":
            await interaction.response.send_modal(CaffeineModal(task_id, task_info, self))
        else:
            await interaction.response.send_modal(NumericTaskModal(task_id, task_info, self))

    async def process_simple_confirm(self, interaction, task_id, task_info):
        await interaction.response.defer(ephemeral=True)
        await db.upsert_daily_quest({
            "player_id": self.player_id, "task_id": task_id,
            "performed_data": {"status": "done"}, "xp_gained": task_info.get('xp_reward', 0),
            "is_completed": True, "log_date": datetime.now().date().isoformat()
        })
        await db.recalculate_player_stats(self.player_id)
        await interaction.followup.send(f"✅ تم إنجاز: **{task_info['title']}**", ephemeral=True)
        # العودة للرئيسية وتحديثها
        await self.back_to_main(interaction)

    async def show_options_ui(self, interaction, task_id, task_info):
        """عرض الخيارات (مثل الصلوات) في نفس الرسالة"""
        self.clear_items()
        options = [discord.SelectOption(label=o['label'], value=o['value']) for o in task_info['options']]
        select = Select(placeholder="اختر الإجابة...", options=options)
        
        async def cb(i):
            await i.response.defer(ephemeral=True)
            opt = next((o for o in task_info['options'] if o['value'] == select.values[0]), None)
            xp = int(task_info.get('xp_reward', 0) * opt['xp_pct'])
            
            await db.upsert_daily_quest({
                "player_id": self.player_id, "task_id": task_id,
                "performed_data": {"selected": select.values[0], "label": opt['label']},
                "xp_gained": xp, "is_completed": opt['xp_pct'] >= 0.8,
                "log_date": datetime.now().date().isoformat()
            })
            await db.recalculate_player_stats(self.player_id)
            await i.followup.send(f"✅ تم تسجيل: **{opt['label']}**", ephemeral=True)
            await self.back_to_main(i)

        select.callback = cb
        self.add_item(select)
        
        # زر رجوع
        back = Button(label="رجوع", style=ButtonStyle.secondary)
        back.callback = lambda i: self.show_tasks_list(i, task_info.get('category'))
        self.add_item(back)
        
        await interaction.response.edit_message(view=self)

    # =================================================
    # 5. تحديث اللوحة الرئيسية (Embed Updater)
    # =================================================
    async def update_dashboard_embed(self, interaction: discord.Interaction):
        today = datetime.now().date().isoformat()
        p_data = await db.get_player(str(self.discord_snowflake_id))
        logs = await db.get_player_daily_logs(str(self.player_id), today)
        log_dict = {log['task_id']: log for log in logs}

        embed = discord.Embed(title="📊 ملخص إنجازات اليوم", color=discord.Color.blue())
        embed.set_author(name=f"الصياد: {p_data['username']}", icon_url=interaction.user.display_avatar.url)

        categories = {
            "strength": ("القوة", "💪"), "intelligence": ("الذكاء", "🧠"),
            "vitality": ("الصحة", "❤️"), "agility": ("الاجتماعي", "🤝"),
            "perception": ("الديني", "🕌"), "freedom": ("المال والعمل", "💸"),
        }

        total_tasks = len(self.task_list)
        total_done = 0

        for cat_id, (name, emoji) in categories.items():
            target_cats = [cat_id]
            if cat_id == "freedom": target_cats.append("work")
            
            cat_tasks = [tid for tid in self.task_list.keys() if self.task_list[tid].get('category') in target_cats]
            if not cat_tasks: continue
            
            done_in_cat = sum(1 for tid in cat_tasks if log_dict.get(tid, {}).get('is_completed'))
            total_done += done_in_cat
            
            bar = draw_progress_bar(done_in_cat, len(cat_tasks), length=8)
            embed.add_field(name=f"{emoji} {name}", value=f"{bar} ({done_in_cat}/{len(cat_tasks)})", inline=True)

        progress_pct = int((total_done / total_tasks * 100)) if total_tasks > 0 else 0
        main_bar = draw_progress_bar(total_done, total_tasks, length=15)
        
        thresholds = {"E": 40, "D": 50, "C": 65, "B": 80, "A": 100, "S": 100}
        required = thresholds.get(p_data['rank'], 40)
        status_safe = "آمن ✅" if progress_pct >= required else "في خطر 🚨"

        embed.add_field(name="🏁 التقدم الإجمالي", value=f"{main_bar} **{progress_pct}%**", inline=False)
        embed.add_field(name="⚖️ التقييم", value=f"وضعك: {status_safe} (المطلوب: {required}%)", inline=True)
        embed.set_footer(text="استخدم القائمة أعلاه لتسجيل المهام 👇")

        # استخدام edit_original_response إذا كان التفاعل قد تم الرد عليه (مثل الـ defer في Modals)
        # أو edit_message إذا كان تفاعلاً مباشراً (مثل الأزرار)
        try:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
        except:
            # محاولة أخيرة (في حالة الـ Modals أحياناً نحتاج لتعديل الرسالة عبر الـ webhook)
            await interaction.message.edit(embed=embed, view=self)
            
# ============ 3. المحرك الرئيسي (The Cog) ============

class QuestEngine(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_cycle.start()

    def cog_unload(self):
        self.daily_cycle.cancel()

    @tasks.loop(minutes=1)
    async def daily_cycle(self):
        """المراقب الزمني للمهام اليومية"""
        try:
            now = datetime.now()
            time_str = now.strftime("%H:%M")
            today_str = now.date().isoformat()
            
            # طباعة للتأكد من التوقيت كل ساعة
            if now.minute == 0:
                logger.info(f"🕒 توقيت البوت: {time_str} - التاريخ: {today_str}")

            # 1. دورة الفجر (توزيع المهام)
            if now.hour >= 5:
                last_run = await db.get_system_config('last_daily_quest_run')
                if last_run != today_str:
                    logger.info(f"⏰ بدء دورة توزيع المهام ليوم {today_str}...")
                    await db.set_system_config('last_daily_quest_run', today_str)
                    await self.launch_daily_quests()

            # 2. دورة منتصف الليل (ساعة الحساب)
            if now.hour == 23 and now.minute >= 50:
                last_judge = await db.get_system_config('last_judgment_run')
                if last_judge != today_str:
                    logger.info(f"⚖️ بدء دورة الحساب ليوم {today_str}...")
                    await db.set_system_config('last_judgment_run', today_str)
                    await self.apply_daily_judgment()

            # 3. تذكير الصيام (الساعة 8 مساءً)
            if now.hour == 20 and now.minute == 0:
                await self.send_fasting_reminders()
        except Exception as e:
            logger.error(f"❌ خطأ في الدورة الزمنية: {e}")

    async def send_fasting_reminders(self):
        """إرسال تذكير بالصيام قبل يوم"""
        try:
            from hijri_converter import Gregorian
            tomorrow = datetime.now() + timedelta(days=1)
            hijri_tom = Gregorian(tomorrow.year, tomorrow.month, tomorrow.day).to_hijri()
            
            msg = ""
            if hijri_tom.day in [13, 14, 15]: msg = "🌕 **تذكير:** غداً من الأيام البيض."
            elif tomorrow.weekday() in [0, 3]: msg = "📅 **تذكير:** غداً يوم صيام (إثنين/خميس)."
            elif hijri_tom.month == 1 and hijri_tom.day == 10: msg = "🕌 **تذكير هام:** غداً يوم عاشوراء."
            
            if msg:
                players = await db._execute_async(lambda: db.client.table('players').select('*').eq('faith_type', 'muslim').eq('status', 'active').execute())
                for p in players.data:
                    try:
                        u = await self.bot.fetch_user(int(p['discord_id']))
                        await u.send(f"🔔 {msg}")
                    except: pass
        except Exception as e:
            logger.error(f"Fasting Reminder Error: {e}")

    async def launch_daily_quests(self):
        """توليد وإرسال لوحات المهام"""
        players = await db._execute_async(lambda: db.client.table('players').select('*').neq('status', 'inactive').execute())
        
        logger.info(f"🚀 بدء توزيع المهام لـ {len(players.data)} صياد...")
        
        for i, p in enumerate(players.data):
            assigned_tasks = task_logic.get_daily_tasks_for_player(p)
            if not assigned_tasks: continue

            try:
                user = await self.bot.fetch_user(int(p['discord_id']))
                view = QuestDashboard(p['id'], p['discord_id'], assigned_tasks)
                
                status_titles = {
                    "active": "⚔️ نداء الواجب اليومي",
                    "sick": "🩹 بروتوكول التعافي",
                    "traveling": "✈️ مهام الرحالة",
                    "excuse": "✨ استراحة المحارب"
                }
                title = status_titles.get(p['status'], "⚔️ المهام اليومية")

                # حساب إحصائيات سريعة
                total_xp = sum(t.get('xp_reward', 0) for t in assigned_tasks.values())
                categories = set(t.get('category', 'عام') for t in assigned_tasks.values())
                cat_emojis = {"vitality": "❤️", "work": "💼", "freedom": "💸", "intelligence": "🧠", "agility": "🤝", "perception": "🕌", "strength": "💪"}
                cat_icons = " ".join([cat_emojis.get(c, "🔸") for c in categories])

                embed = discord.Embed(
                    title=title,
                    description=f"أهلاً بك يا **{p['username']}**. يوم جديد، فرصة جديدة للارتقاء!",
                    color=discord.Color.gold()
                )
                embed.add_field(name="🎯 عدد المهام", value=f"**{len(assigned_tasks)}** مهمة", inline=True)
                embed.add_field(name="✨ مجموع الخبرة", value=f"**{total_xp}** XP", inline=True)
                embed.add_field(name="🏷️ الجوانب", value=cat_icons, inline=False)
                embed.set_footer(text="اضغط على القائمة أدناه لبدء التنفيذ 👇")

                msg = await user.send(embed=embed, view=view)
                
                # ✅ حفظ آيدي الرسالة لتحديثها لاحقاً
                await db.update_player(p['discord_id'], {'last_dashboard_msg_id': str(msg.id)})
                
                if (i + 1) % 5 == 0: await asyncio.sleep(2)
                else: await asyncio.sleep(0.6)
                    
            except Exception as e:
                logger.warning(f"⚠️ تعذر الإرسال للصياد {p['username']}: {e}")

        logger.info("✅ اكتمل توزيع المهام.")

    async def apply_daily_judgment(self):
        """تحليل النتائج وتطبيق العقوبات (النسخة الموحدة)"""
        today = datetime.now().date().isoformat()
        players = await db._execute_async(lambda: db.client.table('players').select('*').neq('status', 'inactive').execute())
        
        logger.info(f"⚖️ بدء ساعة الحساب لـ {len(players.data)} صياد...")

        for i, p in enumerate(players.data):
            try:
                assigned_tasks = task_logic.get_daily_tasks_for_player(p)
                if not assigned_tasks: continue

                logs = await db.get_player_daily_logs(p['id'], today)
                log_dict = {log['task_id']: log for log in logs}

                category_xp = {}
                total_xp_gained = 0
                completed_count = 0
                failed_categories = []
                
                for tid, info in assigned_tasks.items():
                    log = log_dict.get(tid)
                    # دمج العمل مع المال في التقرير
                    raw_cat = info.get('category', 'general')
                    cat = 'freedom' if raw_cat == 'work' else raw_cat
                    
                    if log:
                        xp = log.get('xp_gained', 0)
                        total_xp_gained += xp
                        category_xp[cat] = category_xp.get(cat, 0) + xp
                        if log.get('is_completed'):
                            completed_count += 1
                        else:
                            failed_categories.append(cat)
                    else:
                        failed_categories.append(cat)
                        category_xp[cat] = category_xp.get(cat, 0) + 0

                failed_categories = list(set(failed_categories))
                total_assigned = len(assigned_tasks)
                progress_pct = (completed_count / total_assigned * 100) if total_assigned > 0 else 0
                
                thresholds = {"E": 40, "D": 50, "C": 65, "B": 80, "A": 100, "S": 100}
                required_pct = thresholds.get(p['rank'], 40)
                
                buffs = await db.get_active_buffs(p['id'])
                protection_buff = next((b for b in buffs if b['buff_type'] == 'streak_protection'), None)

                judgment_msg = ""
                penalty_applied = False
                
                if progress_pct >= required_pct:
                    judgment_msg = "✅ **تم اجتياز اختبار اليوم بنجاح!**"
                    await self.reward_player(p, total_xp_gained)
                elif protection_buff:
                    judgment_msg = "❄️ **تم تفعيل درع الحماية!** (الستريك لم ينكسر)"
                    await self.consume_protection(p, protection_buff['id'], total_xp_gained)
                else:
                    judgment_msg = "💀 **لقد فشلت في تحقيق الانضباط المطلوب!**"
                    penalty_applied = True
                    await self.penalize_player(p, progress_pct, failed_categories)

                # ✅ تحديث المستوى بعد الحساب النهائي
                await db.recalculate_player_stats(p['id'])

                # إرسال التقرير (تحديث الرسالة القديمة)
                await self.send_daily_report(p, judgment_msg, category_xp, completed_count, total_assigned, progress_pct, penalty_applied)

                if (i + 1) % 5 == 0: await asyncio.sleep(2)
                else: await asyncio.sleep(0.7)

            except Exception as e:
                logger.error(f"❌ خطأ في حساب نتائج {p['username']}: {e}")

    async def send_daily_report(self, player, judgment, cat_xp, done, total, pct, failed):
        """توليد وإرسال التقرير المرئي (تحديث الرسالة القديمة)"""
        try:
            user = await self.bot.fetch_user(int(player['discord_id']))
            color = discord.Color.red() if failed else discord.Color.green()
            
            embed = discord.Embed(title="📊 التقرير الختامي لليوم", description=judgment, color=color)
            
            cat_emojis = {"strength": "💪", "intelligence": "🧠", "vitality": "❤️", "agility": "🤝", "perception": "🕌", "freedom": "💸"}
            cat_names = {"strength": "القوة", "intelligence": "الذكاء", "vitality": "الصحة", "agility": "الاجتماعي", "perception": "الديني", "freedom": "المالي"}
            
            xp_details = ""
            for cat, xp in cat_xp.items():
                xp_details += f"{cat_emojis.get(cat, '✨')} {cat_names.get(cat, cat)}: `+{xp} XP` \n"
            
            embed.add_field(name="📈 تحليل النمو", value=xp_details or "لا يوجد بيانات", inline=False)
            
            bar = draw_progress_bar(done, total, length=15)
            embed.add_field(name="🎯 معدل الإنجاز", value=f"{bar} **{int(pct)}%**\n({done} من أصل {total} مهام)", inline=False)

            if failed:
                embed.set_footer(text="⚠️ انكسر الستريك الخاص بك وتم تطبيق العقوبة.")
            else:
                embed.set_footer(text=f"🔥 الستريك الحالي: {player.get('streak_days', 0) + 1} أيام")

            # ✅ محاولة تحديث الرسالة القديمة
            msg_id = player.get('last_dashboard_msg_id')
            if msg_id:
                try:
                    msg = await user.fetch_message(int(msg_id))
                    # إزالة الـ View (الأزرار) لأن اليوم انتهى
                    await msg.edit(embed=embed, view=None)
                    return
                except: pass # الرسالة حذفت، نرسل جديدة

            await user.send(embed=embed)
        except: pass

    async def penalize_player(self, player, progress_pct, failed_categories):
        """تطبيق العقوبة النسبية والديناميكية"""
        penalty_type = random.choice(["xp_loss", "coins_loss", "real_money"])
        base_penalty = player.get('base_penalty', 100)
        severity_multiplier = (1 - (progress_pct / 100)) 
        
        update_data = {"streak_days": 0}
        category_arabic = {"strength": "القوة", "intelligence": "الذكاء", "vitality": "الصحة", "agility": "الاجتماعي", "perception": "الديني", "freedom": "المالي"}

        msg_detail = ""

        if penalty_type == "xp_loss":
            loss = int(250 * severity_multiplier)
            update_data["total_xp"] = max(0, player['total_xp'] - loss)
            
            if failed_categories:
                loss_per_cat = loss // len(failed_categories)
                for cat in failed_categories:
                    col = f"{cat}_xp"
                    update_data[col] = max(0, player.get(col, 0) - loss_per_cat)
                
                cats_txt = ", ".join([category_arabic.get(c, c) for c in failed_categories])
                msg_detail = f"تم خصم الـ XP من: ({cats_txt})."
            else:
                msg_detail = "تم الخصم من إجمالي الخبرة الكلية."

            msg = f"📉 **فشل الذات:** انكسر الستريك! وتم خصم {loss} XP.\n💡 {msg_detail}"
            
        elif penalty_type == "coins_loss":
            loss = int(base_penalty * severity_multiplier)
            update_data["coins"] = max(0, player['coins'] - loss)
            msg = f"💸 **غرامة تقصير:** انكسر الستريك! وتم خصم {loss} عملة ذهبية."
            
        else: # real_money
            amount = max(5, int(50 * severity_multiplier))
            # ✅ استخدام العملة الديناميكية
            currency = player.get('currency', 'USD')
            
            await db._execute_async(lambda: db.client.table('penalties').insert({
                "player_id": player['id'], "penalty_type": "real_donation",
                "amount": amount, "currency": currency, "status": "pending", 
                "description": "عقوبة فشل المهام اليومية"
            }).execute())
            msg = f"🚨 **عقوبة واقعية:** انكسر الستريك! ويجب عليك التبرع بـ {amount} {currency} لجهة خيرية."

        await db.update_player(player['discord_id'], update_data)
        try:
            user = await self.bot.fetch_user(int(player['discord_id']))
            await user.send(f"💀 **ساعة الحساب:**\n{msg}")
        except: pass

    async def reward_player(self, player, xp):
        new_streak = player.get('streak_days', 0) + 1
        await db.update_player(player['discord_id'], {
            "total_xp": player['total_xp'] + xp,
            "streak_days": new_streak,
            "last_streak_date": datetime.now().date().isoformat()
        })
        try:
            user = await self.bot.fetch_user(int(player['discord_id']))
            await user.send(f"🔥 **إنجاز رائع!** تم الحفاظ على الستريك: **{new_streak} يوم**.\nحصلت على +{xp} XP.")
        except: pass

    async def consume_protection(self, player, buff_id, xp):
        await db._execute_async(lambda: db.client.table('player_buffs').delete().eq('id', buff_id).execute())
        await db.update_player(player['discord_id'], {
            "total_xp": player['total_xp'] + xp,
            "last_streak_date": datetime.now().date().isoformat()
        })
        try:
            user = await self.bot.fetch_user(int(player['discord_id']))
            await user.send(f"❄️ **تم تفعيل حماية الستريك!**\nلقد قصرت في مهامك اليوم، ولكن 'تذكرة تخطي يوم' أنقذت الستريك.")
        except: pass

    # ============ أوامر التحكم اليدوي ============
    
    @app_commands.command(name="force_launch", description="[Admin] إجبار النظام على إرسال المهام اليومية الآن")
    async def force_launch_cmd(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("⛔ هذا الأمر للمطورين فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("🔄 جاري تشغيل محرك التوزيع اليدوي...")
        await self.launch_daily_quests()
        await interaction.followup.send("✅ تم التوزيع.")

    @app_commands.command(name="force_judgment", description="[Admin] إجبار النظام على تنفيذ ساعة الحساب الآن")
    async def force_judgment_cmd(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("⛔ هذا الأمر للمطورين فقط.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("⚖️ جاري بدء ساعة الحساب يدوياً...")
        await self.apply_daily_judgment()
        await interaction.followup.send("✅ تم الحساب.")

async def setup(bot):
    await bot.add_cog(QuestEngine(bot))