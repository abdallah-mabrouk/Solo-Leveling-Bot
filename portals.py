import discord
from discord import app_commands
from discord.ext import tasks, commands
from discord.ui import View, Button
from database import db
from datetime import datetime, timedelta
import asyncio
import os
import random
import logging

from hijri_converter import Gregorian


logger = logging.getLogger(__name__) # ✅ أضف هذا السطر تحت الاستيرادات مباشرة

class PortalSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.portal_checker.start()

    def cog_unload(self):
        self.portal_checker.cancel()

    # ====================================================
    # 🕒 1. المراقب الزمني (The Scheduler Loop)
    # ====================================================
    @tasks.loop(minutes=1)
    async def portal_checker(self):
        try:
            # 1. الوقت الحالي بتوقيت القاهرة
            now = datetime.now() 
            
            # ==========================================
            # 🧹 الجزء الأول: تنظيف البوابات (الصرامة)
            # ==========================================
            
            # أ) كسر الختم للتوظيف المتأخر (أكثر من 45 دقيقة)
            expired_recruiting = await db._execute_async(
                lambda: db.client.table('portal_history')
                .select('*, quest:system_portal_quests(*)') # جلب كل التفاصيل للعقوبة
                .eq('status', 'recruiting')
                .execute()
            )
            for p in expired_recruiting.data:
                try:
                    created_at = self.parse_supabase_date(p['created_at'])
                    if now > (created_at + timedelta(minutes=45)):
                        await self.close_portal(p, "broken", "💀 **فشل في التجمع!** تأخر الصيادون عن دخول البوابة، فخرجت الوحوش للمدينة.")
                        await asyncio.sleep(0.8) # منع الحظر
                except Exception as e:
                    print(f"Error checking recruiting {p['id']}: {e}")

            # ب) إعلان فشل الغارات النشطة التي تجاوزت الوقت
            active_portals = await db._execute_async(
                lambda: db.client.table('portal_history')
                .select('*, quest:system_portal_quests(*)')
                .eq('status', 'active')
                .execute()
            )
            for p in active_portals.data:
                try:
                    started_at = self.parse_supabase_date(p['started_at'])
                    duration = p['quest']['duration_minutes']
                    
                    if now > (started_at + timedelta(minutes=duration)):
                        await self.close_portal(p, "broken", "💀 **DUNGEON BREAK!** انتهى الوقت المخصص ولم ينجح الفريق في تطهير البوابة.")
                        await asyncio.sleep(0.8)
                except Exception as e:
                    print(f"Error checking active {p['id']}: {e}")

            # ==========================================
            # 🌪️ الجزء الثاني: المولد الجديد (The Spawner)
            # ==========================================

            # 1. وضع النوم (Sleep Mode): لا بوابات بين 12 ليلاً و 8 صباحاً
            if 0 <= now.hour < 8:
                return

            # 2. التحقق من البوابات الموسمية (الأعياد) 🕌
            try:
                from hijri_converter import Gregorian
                hijri = Gregorian(now.year, now.month, now.day).to_hijri()
                hijri_key = f"{hijri.month}-{hijri.day}" # مثال: 10-1
                
                # البحث عن بوابة موسمية لهذا اليوم
                seasonal_quest = await db._execute_async(
                    lambda: db.client.table('system_portal_quests')
                    .select('*').eq('is_seasonal', True).eq('seasonal_hijri_date', hijri_key).execute()
                )
                
                if seasonal_quest.data:
                    # نتأكد أنها لم تطلق اليوم بالفعل
                    last_portal = await db._execute_async(
                        lambda: db.client.table('portal_history').select('created_at').order('created_at', desc=True).limit(1).execute()
                    )
                    
                    should_spawn_seasonal = True
                    if last_portal.data:
                        last_date = self.parse_supabase_date(last_portal.data[0]['created_at']).date()
                        if last_date == now.date():
                            should_spawn_seasonal = False # تم إطلاقها اليوم

                    if should_spawn_seasonal:
                        await self.launch_public_portal(seasonal_quest.data[0])
                        return # لا نطلق بوابات عشوائية في يوم العيد
            except Exception as e:
                print(f"Seasonal Check Error: {e}")

            # 3. التحقق من الفاصل الزمني للبوابات العشوائية 🎲
            
            # جلب إعداد الفاصل الزمني (الافتراضي ساعتين)
            config_res = await db._execute_async(
                lambda: db.client.table('system_config').select('value').eq('key', 'portal_interval_hours').execute()
            )
            interval_hours = int(config_res.data[0]['value']) if config_res.data else 2
            
            # جلب وقت آخر بوابة
            last_portal_res = await db._execute_async(
                lambda: db.client.table('portal_history').select('created_at').order('created_at', desc=True).limit(1).execute()
            )
            
            should_spawn = False
            if not last_portal_res.data:
                should_spawn = True # أول مرة يشتغل السيرفر
            else:
                last_time = self.parse_supabase_date(last_portal_res.data[0]['created_at'])
                # هل مر الوقت المحدد؟
                if now > (last_time + timedelta(hours=interval_hours)):
                    should_spawn = True
            
            if should_spawn:
                # 1. جلب كل البوابات غير الموسمية
                quests_res = await db._execute_async(
                    lambda: db.client.table('system_portal_quests')
                    .select('*').eq('is_seasonal', False).execute()
                )
                
                if quests_res.data:
                    all_quests = quests_res.data
                    # خلط البوابات لضمان العشوائية
                    random.shuffle(all_quests)
                    
                    selected_quest = None
                    
                    # 2. البحث عن بوابة مناسبة لقوة السيرفر الحالية
                    for quest in all_quests:
                        required_level = quest.get('min_aspect_level', 1)
                        required_party = quest.get('party_size', 1)
                        
                        # نسأل قاعدة البيانات: هل يوجد عدد كافٍ من الأقوياء؟
                        capable_count = await db.count_capable_players(required_level)
                        
                        if capable_count >= required_party:
                            selected_quest = quest
                            break # وجدنا بوابة مناسبة!
                        else:
                            # (اختياري) طباعة في اللوج للمراقبة
                            # print(f"Skipped {quest['title']}: Need {required_party} players lvl {required_level}, found {capable_count}")
                            pass

                    # 3. الإطلاق
                    if selected_quest:
                        # ✅ وجدنا بوابة مناسبة -> نطلقها
                        await self.launch_public_portal(selected_quest)
                    else:
                        # ❌ لم نجد أي بوابة مناسبة لقوة اللاعبين الحاليين
                        # الحل: نسجل "تخطي" في قاعدة البيانات لتحديث المؤقت ومنع التكرار الفوري
                        # نستخدم أول كويست في القائمة فقط لملء خانة الـ Foreign Key (لن يتم عرضه)
                        dummy_quest_id = all_quests[0]['id']
                        
                        await db._execute_async(
                            lambda: db.client.table('portal_history').insert({
                                'quest_id': dummy_quest_id,
                                'status': 'skipped', # حالة جديدة تعني "تم التخطي لعدم الجاهزية"
                                'participants_data': {'reason': 'no_capable_players'}
                            }).execute()
                        )
                        print(f"⚠️ Skipped spawning: No capable players found. Timer reset for {interval_hours} hours.")

        except Exception as e:
            print(f"Portal Loop Error: {e}")     
            
    def parse_supabase_date(self, date_str):
        """دالة احترافية لمعالجة كافة أشكال تواريخ سوبابيس (3، 4، 6 أرقام للكسور)"""
        import re
        # تنظيف حرف Z
        clean_str = date_str.replace('Z', '+00:00')
        
        # البحث عن أجزاء المايكروثانية باستخدام Regex وتوحيدها لـ 6 أرقام
        match = re.search(r'\.(\d+)', clean_str)
        if match:
            fraction = match.group(1)
            fixed_fraction = (fraction + "000000")[:6]
            clean_str = clean_str.replace(f".{fraction}", f".{fixed_fraction}")
            
        db_time_aware = datetime.fromisoformat(clean_str)
        return db_time_aware.astimezone().replace(tzinfo=None)
        
    @portal_checker.before_loop
    async def before_portal_checker(self): await self.bot.wait_until_ready()

    # --- دالة الإغلاق والعقوبات (مصححة) ---
    async def close_portal(self, portal_data, new_status, message):
        # 1. تحديث حالة البوابة في السجلات
        await db._execute_async(
            lambda: db.client.table('portal_history')
            .update({'status': new_status, 'ended_at': datetime.now().isoformat()})
            .eq('id', portal_data['id']).execute()
        )
        
# 2. تفصيل العقوبة الجماعية (إذا كانت broken وعامة)
        if new_status == 'broken' and not portal_data.get('is_private'):
            rank_penalties = {"E": 50, "D": 100, "C": 200, "B": 400, "A": 800, "S": 1500, "SS": 3000}
            
            # محاولة جلب البيانات من الـ Quest المرتبط
            quest_info = portal_data.get('quest')
            if not quest_info:
                # إذا لم يجدها (حالة نادرة)، نحاول جلبها من سجل البوابة نفسه
                p_rank = portal_data.get('portal_rank', 'E')
                p_category = portal_data.get('category', 'strength')
            else:
                p_rank = quest_info.get('difficulty_rank', 'E')
                p_category = quest_info.get('category', 'strength')
            
            penalty_val = rank_penalties.get(p_rank, 50)
            
            # تنفيذ العقوبة
            try:
                await db.apply_global_penalty(p_category, penalty_val)
                logger.info(f"✅ تم تطبيق عقوبة جماعية: -{penalty_val} XP في {p_category}")
            except Exception as e:
                print(f"❌ فشل تنفيذ العقوبة الجماعية: {e}")

            category_arabic = {
                "strength": "القوة", "intelligence": "الذكاء", "vitality": "الصحة", 
                "agility": "الاجتماعي", "perception": "الديني", "freedom": "المالي"
            }
            
            category_name = category_arabic.get(p_category, "القوة")
            message = (
                f"🚨 **DUNGEON BREAK!**\n"
                f"لقد فشل الصيادون في إغلاق البوابة في الوقت المحدد.\n\n"
                f"📉 **العقوبة الجماعية:** تم خصم **{penalty_val} XP** من جانب **{category_arabic.get(p_category, p_category)}** لجميع الصيادين!\n"
                f"⚠️ التخاذل يؤدي لانهيار الجميع.."
            )

        # 3. إرسال الإشعار وتعديل الرسالة القديمة (كما هي في الكود السابق)
        if portal_data.get('is_private'): return 
        try:
            channel_id = os.getenv("PORTAL_CHANNEL_ID")
            if not channel_id: return
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                embed = discord.Embed(title="🚨 كارثة رصدت!", description=message, color=discord.Color.red())
                embed.set_thumbnail(url="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExajRsMzRmemN3bDhnbmR6dHo0MGZpbDQydnYwdnI4YTNmZzB6NjQ5ZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/IvoysZG4Zn5a4cWBZA/giphy.gif")
                await channel.send(embed=embed)
                
                msg_id = portal_data.get('channel_message_id')
                if msg_id:
                    try:
                        old_msg = await channel.fetch_message(int(msg_id))
                        await old_msg.edit(view=None)
                    except: pass
        except: pass

    # ====================================================
    # 🚀 2. دوال الإطلاق
    # ====================================================
    
    async def launch_public_portal(self, quest):
        channel_id = os.getenv("PORTAL_CHANNEL_ID")
        role_id = os.getenv("HUNTER_ROLE_ID")
        channel = self.bot.get_channel(int(channel_id)) if channel_id else None
        if not channel: return

        history = await db._execute_async(lambda: db.client.table('portal_history').insert({'quest_id': quest['id'], 'status': 'recruiting', 'is_private': False}).execute())
        h_id = history.data[0]['id']

        end_time = datetime.now() + timedelta(minutes=quest['duration_minutes'])
        timestamp = int(end_time.timestamp())

        colors = {"E": 0x95a5a6, "D": 0x3498db, "C": 0x2ecc71, "B": 0xe67e22, "A": 0xe74c3c, "S": 0xf1c40f, "SS": 0x9b59b6}
        embed = discord.Embed(title=f"🚨 **GATE DETECTED!** | Rank {quest['difficulty_rank']}", description=f"**النوع:** {quest['category'].capitalize()}\n**المهمة:** {quest['description']}", color=colors.get(quest['difficulty_rank'], 0))
        embed.add_field(name="⏳ الوقت المتبقي", value=f"<t:{timestamp}:R>", inline=True)
        embed.add_field(name="👥 الفريق", value=f"0/{quest['party_size']}", inline=True)
        embed.add_field(name="⚠️ تحذير", value="فشل المهمة سيؤدي لعقوبة جماعية!", inline=False)
        embed.set_image(url="https://media1.tenor.com/m/jJfdc2lJcQAAAAAd/solo-leveling-dungeon.gif")
        
        mention = f"<@&{role_id}>" if role_id else "@here"
        view = PortalJoinView(quest, h_id, is_private=False)
        msg = await channel.send(content=f"{mention} ⚔️ استعدوا!", embed=embed, view=view)
        
        await db._execute_async(lambda: db.client.table('portal_history').update({'channel_message_id': str(msg.id)}).eq('id', h_id).execute())

    async def create_private_portal(self, interaction, level, tier="E"):
        quests = await db._execute_async(lambda: db.client.table('system_portal_quests').select('*').eq('min_aspect_level', level).execute())
        if not quests.data: 
            await interaction.followup.send("❌ لا توجد مهام متاحة لهذا المستوى حالياً.", ephemeral=True)
            return
            
        quest = random.choice(quests.data)
        u_id = str(interaction.user.id)
        
        # إنشاء السجل
        h_entry = await db._execute_async(
            lambda: db.client.table('portal_history')
            .insert({
                'quest_id': quest['id'], 
                'status': 'recruiting', 
                'owner_id': u_id, 
                'is_private': True, 
                'participants_ids': [u_id]
            }).execute()
        )
        h_id = h_entry.data[0]['id']
        
        # ✅ إصلاح العداد: زيادة عداد "البوابات الخاصة المفتوحة" لصاحب المفتاح
        p_db = await db.get_player(u_id)
        if p_db:
            await db.update_player(u_id, {'private_portals_opened': p_db.get('private_portals_opened', 0) + 1})
        
        end_time = datetime.now() + timedelta(minutes=quest['duration_minutes'])
        timestamp = int(end_time.timestamp())

        embed = discord.Embed(title=f"🌀 **بوابة خاصة رُصدت! (Rank {tier})**", description=f"المستدعي: {interaction.user.mention}\n**المهمة:** {quest['description']}", color=discord.Color.purple())
        embed.add_field(name="⏳ تنهار في", value=f"<t:{timestamp}:R>", inline=True)
        embed.add_field(name="👥 الفريق", value=f"1/{quest['party_size']}", inline=True)
        
        # تمرير h_id لضمان استمرارية الأزرار
        view = PrivatePortalView(quest, h_id, u_id)
        msg = await interaction.channel.send(embed=embed, view=view)
        
        await db._execute_async(lambda: db.client.table('portal_history').update({'channel_message_id': str(msg.id)}).eq('id', h_id).execute())
        await interaction.followup.send("✅ تم استخدام المفتاح وفتح البوابة بنجاح!", ephemeral=True)
        

    # ====================================================
    # 🔧 3. أوامر التحكم
    # ====================================================
    @app_commands.command(name="schedule_portal", description="[Admin] جدولة بوابة يدوياً")
    async def schedule_portal(self, interaction: discord.Interaction, hours: int, rank: str):
        if not interaction.user.guild_permissions.administrator: await interaction.response.send_message("⛔ آدمن فقط", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        quests = await db._execute_async(lambda: db.client.table('system_portal_quests').select('*').eq('difficulty_rank', rank).execute())
        if not quests.data: await interaction.followup.send("❌ لا توجد مهام."); return
        quest = random.choice(quests.data)
        await interaction.followup.send(f"✅ سأطلق بوابة {rank} بعد {hours} ساعات.")
        await asyncio.sleep(hours * 3600)
        await self.launch_public_portal(quest)

    @app_commands.command(name="invite", description="دعوة لاعب لبوابتك")
    async def invite_command(self, interaction: discord.Interaction, player: discord.Member):
        u_id = str(interaction.user.id)
        portal = await db._execute_async(lambda: db.client.table('portal_history').select('*').eq('owner_id', u_id).eq('status', 'recruiting').execute())
        if not portal.data: await interaction.response.send_message("❌ لا توجد بوابة نشطة.", ephemeral=True); return
        p_data = portal.data[0]
        current = p_data.get('participants_ids', [])
        if str(player.id) in current: await interaction.response.send_message("✅ مدعو بالفعل.", ephemeral=True); return
        current.append(str(player.id))
        await db.update_portal_participants(p_data['id'], current)
        await interaction.response.send_message(f"✅ تمت دعوة {player.mention}!", ephemeral=True)

    @app_commands.command(name="my_gates", description="عرض بواباتك النشطة")
    async def my_gates(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        u_id = str(interaction.user.id)
        portals = await db._execute_async(
            lambda: db.client.table('portal_history')
            .select('*, quest:system_portal_quests(*)') # ✅ إصلاح: جلب الاسم الصحيح
            .contains('participants_ids', [u_id])
            .in_('status', ['recruiting', 'active'])
            .execute()
        )
        if not portals.data: await interaction.followup.send("📭 لا يوجد.", ephemeral=True); return
        
        for p in portals.data:
            quest = p['quest']
            status_emoji = "🟢" if p['status'] == 'active' else "⏳"
            embed = discord.Embed(title=f"{status_emoji} {quest['title']} ({quest['difficulty_rank']})", description=f"**الحالة:** {p['status']}\n**المهمة:** {quest['description']}", color=discord.Color.blue())
            
            view = View()
            if p['status'] == 'active':
                complete_btn = Button(label="✅ إتمام المهمة", style=discord.ButtonStyle.success, custom_id=f"quick_comp_{p['id']}")
                async def complete_cb(inter):
                    view_mock = PortalActiveView(quest, p['id'], p['participants_ids'])
                    await view_mock.process_completion(inter)
                complete_btn.callback = complete_cb
                view.add_item(complete_btn)
            else: view.add_item(Button(label="في الانتظار...", disabled=True))
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="portal_history", description="سجل آخر 10 بوابات")
    async def portal_history(self, interaction: discord.Interaction):
        await interaction.response.defer()
        history = await db._execute_async(lambda: db.client.table('portal_history').select('*, quest:system_portal_quests(title, difficulty_rank)').order('created_at', desc=True).limit(10).execute())
        if not history.data: await interaction.followup.send("📭 السجل فارغ."); return
        embed = discord.Embed(title="📜 سجل البوابات الأخير", color=discord.Color.gold())
        for h in history.data:
            status_icon = "✅" if h['status'] == 'cleared' else "💔" if h['status'] == 'broken' else "⏳"
            date = h['created_at'][:10]
            embed.add_field(name=f"{status_icon} {h['quest']['title']} ({h['quest']['difficulty_rank']})", value=f"📅 {date} | {h['status']}", inline=False)
        await interaction.followup.send(embed=embed)
        
        
    @app_commands.command(name="set_portal_interval", description="[Admin] ضبط وتيرة ظهور البوابات العشوائية (بالساعات)")
    async def set_portal_interval(self, interaction: discord.Interaction, hours: int):
        """تعديل الفاصل الزمني لظهور البوابات في السيرفر"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("⛔ هذا الأمر لقادة النقابة فقط.", ephemeral=True)
            return
        
        if hours < 1:
            await interaction.response.send_message("❌ لا يمكن أن يكون الفاصل أقل من ساعة واحدة.", ephemeral=True)
            return

        # تحديث القيمة في جدول الإعدادات
        await db._execute_async(
            lambda: db.client.table('system_config')
            .upsert({'key': 'portal_interval_hours', 'value': hours})
            .execute()
        )
        
        await interaction.response.send_message(f"✅ **تم تحديث النظام:** ستظهر بوابة عشوائية جديدة كل **{hours}** ساعات (خارج أوقات النوم).", ephemeral=True)    

# ====================================================
# 🛡️ Views
# ====================================================

class PortalJoinView(View):
    def __init__(self, quest, h_id, is_private=False, owner_id=None):
        super().__init__(timeout=None)
        self.quest = quest
        self.h_id = h_id
        self.is_private = is_private
        self.owner_id = owner_id
        # ✅ هذا السطر يربط الزر بآيدي البوابة الفريد
        self.children[0].custom_id = f"join_portal_{h_id}"

    @discord.ui.button(label="⚔️ انضمام (20 طاقة)", style=discord.ButtonStyle.success, custom_id="join_btn_persistent")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        
        # 1. التحقق من البيانات
        pd = await db.get_portal(self.h_id)
        if not pd: return
        
        # التحقق من الجدول الحقيقي للمشاركين
        participant_check = await db._execute_async(
            lambda: db.client.table('portal_participants')
            .select('*').eq('portal_id', self.h_id).eq('player_id', db.get_player_uuid(uid)) # نحتاج دالة لجلب UUID
            .execute()
        )
        
        # (للتسهيل سنستخدم player_id المباشر إذا كان لديك، أو نجلب اللاعب أولاً)
        player = await db.get_player(uid)
        if not player:
            await interaction.response.send_message("❌ سجل أولاً!", ephemeral=True)
            return

        # التحقق من التكرار
        is_joined = await db._execute_async(
            lambda: db.client.table('portal_participants')
            .select('*').eq('portal_id', self.h_id).eq('player_id', player['id']).execute()
        )
        if is_joined.data:
            await interaction.response.send_message("✅ أنت منضم بالفعل.", ephemeral=True)
            return

        if player['current_energy'] < 20:
            await interaction.response.send_message("🔋 طاقتك لا تكفي.", ephemeral=True)
            return

        # 2. ✅ الإدراج الصحيح في جدول المشاركين (هذا هو الرابط المفقود)
        await db._execute_async(
            lambda: db.client.table('portal_participants').insert({
                'portal_id': self.h_id,
                'player_id': player['id'],
                'status': 'joined'
            }).execute()
        )

        # 3. تحديث مصفوفة العرض (لأجل العداد في الرسالة) والخصم
        current_participants = pd.get('participants_ids', []) or []
        current_participants.append(uid)
        
        update_data = {'current_energy': player['current_energy'] - 20}
        if not self.is_private:
            update_data['public_portals_joined'] = player.get('public_portals_joined', 0) + 1
            
        await db.update_portal_participants(self.h_id, current_participants)
        await db.update_player(uid, update_data)
        
        # تحديث الرسالة
        embed = interaction.message.embeds[0]
        new_embed = discord.Embed(title=embed.title, description=embed.description, color=embed.color)
        if embed.image: new_embed.set_image(url=embed.image.url)
        
        for f in embed.fields:
            if "الفريق" in f.name:
                new_embed.add_field(name="👥 الفريق", value=f"{len(current_participants)}/{self.quest['party_size']}", inline=True)
            else:
                new_embed.add_field(name=f.name, value=f.value, inline=f.inline)
        
        if not self.is_private and len(current_participants) >= self.quest['party_size']:
            await self.start_portal(interaction, new_embed, current_participants)
        else:
            await interaction.response.edit_message(embed=new_embed, view=self)

    async def start_portal(self, interaction, embed, participants):
        embed.title = "🟢 GATE ACTIVE"; embed.color = discord.Color.green()
        embed.description += "\n\n🚀 **انطلقوا! الوحوش بدأت بالظهور.**"
        await db._execute_async(lambda: db.client.table('portal_history').update({'status': 'active', 'started_at': 'now()'}).eq('id', self.h_id).execute())
        await interaction.response.edit_message(embed=embed, view=PortalActiveView(self.quest, self.h_id, participants))

class PrivatePortalView(View):
    def __init__(self, quest, h_id, owner_id):
        super().__init__(timeout=None)
        self.quest = quest; self.h_id = h_id; self.owner_id = owner_id
        # ✅ تخصيص المعرفات للأزرار
        self.children[0].custom_id = f"priv_join_{h_id}"
        self.children[1].custom_id = f"priv_start_{h_id}"

    @discord.ui.button(label="انضمام", style=discord.ButtonStyle.success, custom_id="priv_join_btn")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        pd = await db.get_portal(self.h_id)
        if not pd: return
        if str(interaction.user.id) in pd.get('participants_ids', []): 
            await interaction.response.send_message("✅ أنت في الفريق بالفعل.", ephemeral=True)
        else: 
            await interaction.response.send_message("⛔ لست مدعواً لهذه البوابة الخاصة.", ephemeral=True)

    @discord.ui.button(label="🚀 بدء الغارة", style=discord.ButtonStyle.danger, custom_id="priv_start_btn")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.owner_id: 
            await interaction.response.send_message("⛔ المالك فقط من يمكنه فتح الختم!", ephemeral=True)
            return
        
        pd = await db.get_portal(self.h_id)
        participants = pd.get('participants_ids', [])
        
        embed = interaction.message.embeds[0]
        new_embed = discord.Embed(title="🟢 GATE ACTIVE", description=embed.description + "\n\n🔥 **بدأت المهمة!**", color=discord.Color.green())
        for f in embed.fields: new_embed.add_field(name=f.name, value=f.value, inline=f.inline)
        
        await db._execute_async(lambda: db.client.table('portal_history').update({'status': 'active', 'started_at': 'now()'}).eq('id', self.h_id).execute())
        await interaction.response.edit_message(embed=new_embed, view=PortalActiveView(self.quest, self.h_id, participants))

class PortalActiveView(View):
    def __init__(self, quest, h_id, participants):
        super().__init__(timeout=None)
        self.quest = quest; self.h_id = h_id; self.participants = participants
        self.completed = [] # سيتم تحديثها من الداتابيز عند الضغط
        # ✅ تخصيص معرف زر الإتمام
        self.children[0].custom_id = f"complete_portal_{h_id}"

    async def process_completion(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        
        # 1. جلب بيانات اللاعب
        player = await db.get_player(uid)
        if not player:
            await interaction.response.send_message("❌ لم يتم العثور على حسابك في النظام.", ephemeral=True)
            return

        if uid not in self.participants: 
            await interaction.response.send_message("⛔ لست مسجلاً في قائمة المشاركين لهذه البوابة!", ephemeral=True)
            return
        
        # 2. فحص حالة الإتمام من قاعدة البيانات
        participant_check = await db._execute_async(
            lambda: db.client.table('portal_participants')
            .select('status')
            .eq('portal_id', self.h_id)
            .eq('player_id', player['id'])
            .execute()
        )
        
        if participant_check.data and participant_check.data[0]['status'] == 'completed':
            await interaction.response.send_message("✅ لقد سجلت إتمامك بالفعل، انتظر بقية الفريق.", ephemeral=True)
            return
        
        # 3. التحقق من الوقت المنقضي
        try:
            pd = await db.get_portal(self.h_id)
            if not pd or not pd.get('started_at'): 
                await interaction.response.send_message("❌ فشل في جلب بيانات توقيت البوابة.", ephemeral=True)
                return
            
            start_str = pd['started_at'].replace('Z', '').split('.')[0]
            db_start = datetime.fromisoformat(start_str)
            elapsed = (datetime.now() - db_start).total_seconds() / 60
            
            if elapsed < self.quest['min_duration']:
                rem = int(self.quest['min_duration'] - elapsed)
                await interaction.response.send_message(f"⏳ الوحوش لا تزال قوية! انتظر {rem} دقيقة أخرى قبل محاولة الإغلاق.", ephemeral=True)
                return
        except Exception as e: 
            print(f"Time Calculation Error: {e}")

        # 4. تحديث حالة اللاعب إلى 'completed'
        await db._execute_async(
            lambda: db.client.table('portal_participants')
            .update({'status': 'completed', 'completed_at': 'now()'})
            .eq('portal_id', self.h_id)
            .eq('player_id', player['id'])
            .execute()
        )

        # 5. توزيع الجوائز وتحديث العدادات
        xp_reward = self.quest['base_xp']
        coins_reward = random.randint(200, 500)
        
        is_private = pd.get('is_private', False)
        update_fields = {
            'total_xp': player['total_xp'] + xp_reward,
            f"{self.quest['category']}_xp": player.get(f"{self.quest['category']}_xp", 0) + xp_reward,
            'coins': player['coins'] + coins_reward,
        }
        
        if is_private:
            update_fields['private_portals_cleared'] = player.get('private_portals_cleared', 0) + 1
        else:
            update_fields['public_portals_cleared'] = player.get('public_portals_cleared', 0) + 1
        
        await db.update_player(uid, update_fields)

        # 6. إرسال تقرير مفصل في الخاص (DM)
        try:
            dm_embed = discord.Embed(title="🏰 تقرير تطهير البوابة", color=discord.Color.gold())
            dm_embed.description = f"أحسنت يا **{interaction.user.name}**! لقد ساهمت في إغلاق الختم."
            dm_embed.add_field(name="📜 المهمة", value=self.quest['title'], inline=False)
            dm_embed.add_field(name="📈 الخبرة المكتسبة", value=f"+{xp_reward} XP ({self.quest['category']})", inline=True)
            dm_embed.add_field(name="💰 الغنائم", value=f"+{coins_reward} عملة ذهبية", inline=True)
            await interaction.user.send(embed=dm_embed)
            await interaction.response.send_message("✅ تم تسجيل نجاحك وإرسال الغنائم لبريدك الخاص!", ephemeral=True)
        except:
            await interaction.response.send_message(f"✅ تم الإتمام! حصلت على {xp_reward} XP و {coins_reward} عملة.", ephemeral=True)

        # 7. الفحص النهائي لإغلاق البوابة وبناء قائمة الأبطال (تعديل جوهري ✅)
        participants_data = await db._execute_async(
            lambda: db.client.table('portal_participants')
            .select('status, player_id, players(discord_id, username)')
            .eq('portal_id', self.h_id)
            .execute()
        )
        
        completed_players = [p for p in participants_data.data if p['status'] == 'completed']
        total_team_count = len(participants_data.data)

        if len(completed_players) >= total_team_count:
            await db._execute_async(lambda: db.client.table('portal_history').update({'status': 'cleared', 'ended_at': 'now()'}).eq('id', self.h_id).execute())
            
            # بناء قائمة الشرف بشكل احترافي
            hall_of_fame = ""
            for p_rec in completed_players:
                # محاولة جلب الاسم من قاعدة البيانات بشكل آمن
                user_info = p_rec.get('players', {})
                # نستخدم اسم الديسكورد إذا كان متاحاً في السيرفر، وإلا نستخدم الاسم المسجل في القاعدة
                discord_uid = user_info.get('discord_id')
                member = interaction.guild.get_member(int(discord_uid)) if discord_uid else None
                name = member.display_name if member else user_info.get('username', 'صياد مجهول')
                
                hall_of_fame += f"🛡️ **{name}**\n"

            try:
                if interaction.message:
                    embed = interaction.message.embeds[0]
                    embed.title = "🏆 DUNGEON CLEARED!"
                    # تحديث الوصف ليشمل القائمة
                    embed.description = f"**تم تطهير البوابة وإغلاق الختم للأبد!**\n\n**قائمة الأبطال:**\n{hall_of_fame}"
                    embed.color = discord.Color.gold()
                    embed.clear_fields()
                    embed.set_image(url="https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExZ3dyNW5mZGY3aTZodWp0MXpwa212MnFvNDZwbTY1cWM4dW5mZ21qZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/BFEEsxhzZob8HjLHRM/giphy.gif")
                    
                    # حذف الأزرار نهائياً
                    await interaction.message.edit(embed=embed, view=None)
                
                await interaction.channel.send(f"🎉 **انتصار!** نجح الفريق بالكامل في تطهير بوابة **{self.quest['title']}**.")
            except Exception as e:
                print(f"Error updating message: {e}")

    @discord.ui.button(label="✅ إتمام المهمة", style=discord.ButtonStyle.primary, custom_id="complete_portal_btn_persistent")
    async def complete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # استدعاء دالة المعالجة التي أصلحناها سابقاً
        await self.process_completion(interaction)

async def setup(bot):
    await bot.add_cog(PortalSystem(bot))