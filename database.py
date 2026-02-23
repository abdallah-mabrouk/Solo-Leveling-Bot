import os
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
from typing import Dict, Any, List
import asyncio
from datetime import datetime # ✅ إضافة ضرورية للتعامل مع أوقات انتهاء البفات

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_KEY") 
        
        if not self.url or not self.key:
            raise ValueError("❌ مطلوب SUPABASE_URL و SUPABASE_SERVICE_KEY")
        
        try:
            self.client: Client = create_client(self.url, self.key)
            logger.info("✅ تم تهيئة عميل Supabase بنجاح")
        except Exception as e:
            logger.error(f"❌ فشل تهيئة Supabase: {e}")
            raise

    # ✅ نقلنا هذه الدالة للأعلى لأنها "المحرك" لكل الدوال التالية
    async def _execute_async(self, query_func):
        """الدالة السحرية لتنفيذ استعلامات سوبابيس في خيط منفصل لمنع تجميد البوت"""
        return await asyncio.to_thread(query_func)

    # ============ 1. دوال المهام اليومية (Daily Quests) ============

    async def get_player_daily_logs(self, player_id: str, log_date: str):
        """جلب قائمة المهام المسجلة للاعب في تاريخ معين"""
        def query():
            return self.client.table('player_daily_quests').select('*').eq('player_id', player_id).eq('log_date', log_date).execute()
        res = await self._execute_async(query)
        return res.data

    async def upsert_daily_quest(self, data: dict):
        """إضافة أو تحديث سجل مهمة يومية مع معالجة التكرار"""
        def query():
            # ✅ إضافة on_conflict لتحديد الأعمدة الفريدة
            return self.client.table('player_daily_quests').upsert(
                data, 
                on_conflict='player_id, task_id, log_date'
            ).execute()
        return await self._execute_async(query)

    # ============ 2. دوال التأثيرات النشطة (Active Buffs) - جديد ✅ ============

    async def get_active_buffs(self, player_id: str):
        """جلب التأثيرات (مثل حماية الستريك) التي لم تنتهِ صلاحيتها بعد"""
        now = datetime.now().isoformat()
        def query():
            return self.client.table('player_buffs')\
                .select('*')\
                .eq('player_id', player_id)\
                .gt('expires_at', now)\
                .execute()
        res = await self._execute_async(query)
        return res.data

    async def add_player_buff(self, buff_data: dict):
        """تسجيل تأثير جديد (يستدعى عند استهلاك عنصر من الحقيبة)"""
        def query():
            return self.client.table('player_buffs').insert(buff_data).execute()
        return await self._execute_async(query)       
        
    # الدالة السحرية لمنع التهنيج
    async def _execute_async(self, query_func):
        return await asyncio.to_thread(query_func)

    # ============ دوال اللاعبين ============
    async def get_player(self, discord_id: str):
        def query():
            response = self.client.table('players').select('*').eq('discord_id', discord_id).execute()
            return response.data[0] if response.data else None
        return await self._execute_async(query)
    
    async def create_player(self, data: dict):
        def query():
            return self.client.table('players').insert(data).execute()
        
        try:
            response = await self._execute_async(query)
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating player: {e}")
            return None

    async def update_player(self, discord_id: str, data: dict):
        def query():
            return self.client.table('players').update(data).eq('discord_id', discord_id).execute()
        return await self._execute_async(query)

    async def get_player_count(self):
        def query():
            return self.client.table('players').select('id', count='exact').execute()
        response = await self._execute_async(query)
        return response.count

    async def get_top_players(self, limit=10):
        def query():
            return self.client.table('players')\
                .select('username, total_level, rank, total_xp')\
                .order('total_level', desc=True)\
                .order('total_xp', desc=True)\
                .limit(limit)\
                .execute()
        response = await self._execute_async(query)
        return response.data
    
    # ============ نظام العقوبات (تم تحويله لـ Async) ============
    
    async def apply_penalty(self, player_id: str, task_data: dict) -> Dict[str, Any]:
        """تطبيق عقوبة على لاعب"""
        def query():
            try:
                from questions import PenaltySystem
                penalty_system = PenaltySystem()
                
                # توليد العقوبة
                penalty = penalty_system.generate_penalty(
                    task_level=task_data.get("task_level", 1),
                    task_type=task_data.get("task_type", "general"),
                    player_level=task_data.get("player_level", 1)
                )
                
                # تجهيز البيانات
                penalty_record = {
                    "player_id": player_id,
                    "penalty_type": penalty["type"],
                    "description": penalty["description"],
                    "amount": penalty["amount"],
                    "currency": penalty["currency"],
                    "category": penalty.get("category"),
                    "task_data": task_data,
                    "status": "pending",
                    "requires_proof": penalty.get("requires_proof", False),
                    "created_at": "now()"
                }
                
                response = self.client.table('penalties').insert(penalty_record).execute()
                
                if response.data:
                    penalty["id"] = response.data[0]["id"]
                    logger.info(f"✅ تم تطبيق عقوبة: {penalty['type']}")
                    return penalty
                return None
            except Exception as e:
                logger.error(f"خطأ في تطبيق العقوبة: {e}")
                return None

        return await self._execute_async(query)

    # ============ دوال إضافية (تم تحويلها لـ Async) ============

    async def log_activity(self, player_id: str, activity_data: dict):
        def query():
            try:
                activity_data["player_id"] = player_id
                activity_data["created_at"] = "now()"
                response = self.client.table('activities').insert(activity_data).execute()
                return response.data[0] if response.data else None
            except Exception as e:
                logger.error(f"خطأ في تسجيل النشاط: {e}")
                return None
        return await self._execute_async(query)

    async def get_active_portals(self, guild_id: str = None):
        def query():
            try:
                query_builder = self.client.table('portals').select('*').eq('status', 'active')
                if guild_id:
                    query_builder = query_builder.eq('discord_guild_id', guild_id)
                response = query_builder.execute()
                return response.data
            except Exception as e:
                logger.error(f"خطأ في جلب البوابات: {e}")
                return []
        return await self._execute_async(query)

    # ============ دوال البوابات (جديد) ============
    
    async def get_portal(self, portal_id: str):
        """جلب بيانات بوابة محددة"""
        def query():
            response = self.client.table('portal_history')\
                .select('*')\
                .eq('id', portal_id)\
                .execute()
            return response.data[0] if response.data else None
        return await self._execute_async(query)

    async def update_portal_participants(self, portal_id: str, participants: list):
        """تحديث قائمة المشاركين في البوابة"""
        def query():
            return self.client.table('portal_history')\
                .update({'participants_ids': participants})\
                .eq('id', portal_id)\
                .execute()
        return await self._execute_async(query)
    

    async def apply_global_penalty(self, category: str, amount: int):
        """تنفيذ عقوبة جماعية لجميع اللاعبين عبر RPC"""
        def query():
            return self.client.rpc('apply_global_xp_penalty', {
                'penalty_category': category, 
                'penalty_amount': amount
            }).execute()
        return await self._execute_async(query)
        
    async def get_system_config(self, key: str):
        """جلب إعداد معين (مثل الفاصل الزمني)"""
        def query():
            res = self.client.table('system_config').select('value').eq('key', key).execute()
            return res.data[0]['value'] if res.data else None
        return await self._execute_async(query)

    async def get_last_portal_time(self):
        """معرفة متى فُتحت آخر بوابة لحساب الفاصل الزمني"""
        def query():
            # نجلب آخر بوابة تم إنشاؤها
            res = self.client.table('portal_history').select('created_at').order('created_at', desc=True).limit(1).execute()
            return res.data[0]['created_at'] if res.data else None
        return await self._execute_async(query)

    async def get_random_quest(self):
        """جلب مهمة عشوائية (ليست موسمية)"""
        # ملاحظة: سوبابيس لا تدعم order by random مباشرة بسهولة، لذا سنجلب الكل ونختار بالكود
        # بما أن العدد 42 فقط، هذا خفيف جداً
        def query():
            return self.client.table('system_portal_quests').select('*').eq('is_seasonal', False).execute()
        res = await self._execute_async(query)
        if res.data:
            import random
            return random.choice(res.data)
        return None

    async def get_seasonal_quest(self, hijri_date_str: str):
        """البحث عن بوابة موسمية لهذا اليوم (مثل 10-1 للعيد)"""
        def query():
            return self.client.table('system_portal_quests')\
                .select('*')\
                .eq('is_seasonal', True)\
                .eq('seasonal_hijri_date', hijri_date_str)\
                .execute()
        res = await self._execute_async(query)
        return res.data[0] if res.data else None    
        
        
    async def count_capable_players(self, min_level: int):
        """حساب عدد اللاعبين النشطين الذين يتجاوز مستواهم الحد المطلوب"""
        def query():
            # نعد اللاعبين النشطين (active) ومستواهم >= المطلوب
            return self.client.table('players')\
                .select('id', count='exact')\
                .eq('status', 'active')\
                .gte('total_level', min_level)\
                .execute()
        
        res = await self._execute_async(query)
        return res.count
        
    async def set_system_config(self, key: str, value: str):
        """تحديث إعداد نظام (مثل تاريخ آخر توزيع)"""
        def query():
            return self.client.table('system_config').upsert({'key': key, 'value': value}).execute()
        return await self._execute_async(query)

      
    # أضفها في database.py
    async def recalculate_player_stats(self, player_id: str):
        """إعادة حساب المستوى الكلي والرتبة بناءً على مجموع خبرة الجوانب"""
        try:
            # 1. جلب بيانات اللاعب الحالية
            p = await self.get_player_by_uuid(player_id) # سنحتاج دالة تجلب بالـ UUID او نستخدم الموجودة
            # للتبسيط سنفترض أننا نملك البيانات أو نجلبها
            # هنا سأكتب المنطق المباشر للتحديث
            
            def query():
                # نجلب اللاعب
                data = self.client.table('players').select('*').eq('id', player_id).execute()
                if not data.data: return None
                player = data.data[0]
                
                # 2. حساب المجموع الكلي للخبرة
                total_xp = (
                    player.get('strength_xp', 0) + 
                    player.get('intelligence_xp', 0) + 
                    player.get('vitality_xp', 0) + 
                    player.get('agility_xp', 0) + 
                    player.get('perception_xp', 0) + 
                    player.get('freedom_xp', 0)
                )
                
                # 3. حساب المستوى والرتبة (نستورد الدوال الحسابية هنا لتجنب التداخل)
                from questions import calculate_level_progressive
                level, _, _ = calculate_level_progressive(total_xp)
                
                # حساب الرتبة
                rank = "E"
                if level >= 100: rank = "SS"
                elif level >= 80: rank = "S"
                elif level >= 60: rank = "A"
                elif level >= 40: rank = "B"
                elif level >= 20: rank = "C"
                elif level >= 10: rank = "D"
                
                # 4. التحديث
                return self.client.table('players').update({
                    'total_level': level,
                    'total_xp': total_xp,
                    'rank': rank
                }).eq('id', player_id).execute()

            await self._execute_async(query)
            logger.info(f"🔄 تم تحديث مستوى اللاعب {player_id} تلقائياً.")
        except Exception as e:
            logger.error(f"Stats Recalc Error: {e}")
        
# إنشاء نسخة وحيدة من قاعدة البيانات
db = Database()