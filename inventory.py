import discord
from discord.ui import View, Button, Select
from discord import ButtonStyle, SelectOption
from database import db
import math
import random
from inventory_gen import InventoryGenerator
from datetime import datetime, timedelta

class InventoryView(View):
    def __init__(self, user_id, player_data, bot):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.player_data = player_data
        self.bot = bot
        
        self.current_page = 0
        self.items_per_page = 5
        self.current_filter = "all" 
        self.inventory_items = []
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("🛑 هذه الحقيبة خاصة باللاعب!", ephemeral=True)
            return False
        return True

    async def load_inventory(self):
        """جلب عناصر المخزن"""
        response = await db._execute_async(
            lambda: db.client.table('player_inventory')
            .select('*, item:system_shop_items(*)')
            .eq('player_id', self.player_data['id'])
            .execute()
        )
        self.inventory_items = response.data

    async def update_view(self, interaction: discord.Interaction):
        self.clear_items()
        
        # 1. فلترة وتجهيز العناصر
        filtered_items = self.inventory_items
        if self.current_filter == "equipped":
            filtered_items = [i for i in self.inventory_items if i['is_equipped']]
        elif self.current_filter != "all":
            filtered_items = [i for i in self.inventory_items if i['item']['type'] == self.current_filter]

        # 2. تقسيم الصفحات (24 عنصر في الصفحة الواحدة)
        ITEMS_PER_PAGE = 24
        total_pages = math.ceil(len(filtered_items) / ITEMS_PER_PAGE)
        self.current_page = max(0, min(self.current_page, total_pages - 1))
        
        start_idx = self.current_page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        current_page_items = filtered_items[start_idx:end_idx]

        # 3. توليد الصورة الكبيرة
        from inventory_gen import InventoryGenerator
        generator = InventoryGenerator()
        image_buffer = await generator.generate(
            items=current_page_items,
            title="حقيبة الصياد",
            page=self.current_page + 1,
            total_pages=total_pages
        )
        file = discord.File(fp=image_buffer, filename="inventory.png")
        embed = discord.Embed(color=discord.Color.blue())
        embed.set_image(url="attachment://inventory.png")

        # 4. إضافة عناصر التحكم (UI)
        
        # أ) قائمة الفلترة (الصف 0)
        self.add_filter_select()

        # ب) قائمة اختيار العنصر للتفاعل (الصف 1)
        if current_page_items:
            item_options = []
            for item in current_page_items:
                # نستخدم ID العنصر في المخزن كقيمة
                label = f"{item['item']['name'][:20]}" # تقصير الاسم
                desc = f"{item['item']['rarity']}-Rank"
                if item['is_equipped']: label = f"🟢 {label}"
                
                item_options.append(SelectOption(label=label, value=item['id'], description=desc))
            
            # قائمة منسدلة لاختيار العنصر
            item_select = Select(placeholder="اختر عنصراً لارتدائه/استخدامه...", options=item_options, row=1)
            item_select.callback = self.item_action_callback
            self.add_item(item_select)
        
        # ج) أزرار التنقل (الصف 2)
        if total_pages > 1:
            prev = Button(label="السابق", disabled=(self.current_page == 0), row=2)
            nxt = Button(label="التالي", disabled=(self.current_page >= total_pages-1), row=2)
            prev.callback = self.prev_page
            nxt.callback = self.next_page
            self.add_item(prev)
            self.add_item(nxt)

        # الإرسال
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self, attachments=[file])
        else:
            await interaction.response.edit_message(embed=embed, view=self, attachments=[file])

    # --- Callback جديد للتفاعل مع العنصر المختار ---
    async def item_action_callback(self, interaction: discord.Interaction):
        selected_id = interaction.data['values'][0]
        
        # البحث عن العنصر في القائمة الحالية
        selected_item = next((i for i in self.inventory_items if i['id'] == selected_id), None)
        if not selected_item:
            await interaction.response.send_message("❌ العنصر غير موجود.", ephemeral=True)
            return

        item_details = selected_item['item']
        
        # عرض خيارات التفاعل (كزر مؤقت)
        view = View(timeout=60)
        
        if item_details['type'] == 'consumable':
            btn = Button(label="استخدام ✨", style=ButtonStyle.primary)
            btn.callback = self.create_use_callback(selected_item, item_details)
            view.add_item(btn)
        else:
            label = "خلع" if selected_item['is_equipped'] else "ارتداء"
            style = ButtonStyle.danger if selected_item['is_equipped'] else ButtonStyle.success
            btn = Button(label=label, style=style)
            btn.callback = self.create_equip_callback(selected_item, item_details)
            view.add_item(btn)

        await interaction.response.send_message(f"ماذا تريد أن تفعل بـ **{item_details['name']}**؟", view=view, ephemeral=True)
        
    # ============ المنطق (Callbacks) ============

    def add_filter_select(self):
        options = [
            SelectOption(label="الكل", value="all"),
            SelectOption(label="المجهز حالياً", value="equipped", emoji="🟢"),
            SelectOption(label="الأسلحة", value="weapon", emoji="⚔️"),
            SelectOption(label="الدروع", value="armor", emoji="🛡️"),
            SelectOption(label="الأدوات", value="tool", emoji="🛠️"),
            SelectOption(label="الاستهلاكيات", value="consumable", emoji="🧪"),
        ]
        sel = Select(placeholder="تصفية الحقيبة...", options=options, row=0)
        sel.callback = self.filter_callback
        self.add_item(sel)

    def create_equip_callback(self, inv_item, item_details):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            
            if inv_item['is_equipped']:
                # خلع
                await db._execute_async(lambda: db.client.table('player_inventory').update({'is_equipped': False, 'equipped_slot': None}).eq('id', inv_item['id']).execute())
                await interaction.followup.send(f"✅ تم خلع **{item_details['name']}**.", ephemeral=True)
            else:
                # ارتداء
                req_level = item_details.get('min_level', 1)
                if self.player_data['total_level'] < req_level:
                    await interaction.followup.send(f"❌ مستواك منخفض! تحتاج مستوى {req_level}.", ephemeral=True)
                    return

                slot_type = item_details['type']
                # إلغاء ارتداء القديم في نفس المكان
                await db._execute_async(lambda: db.client.table('player_inventory').update({'is_equipped': False, 'equipped_slot': None}).eq('player_id', self.player_data['id']).eq('equipped_slot', slot_type).execute())
                # ارتداء الجديد
                await db._execute_async(lambda: db.client.table('player_inventory').update({'is_equipped': True, 'equipped_slot': slot_type}).eq('id', inv_item['id']).execute())
                await interaction.followup.send(f"⚔️ تم تجهيز **{item_details['name']}** بنجاح!", ephemeral=True)

            await self.load_inventory()
            await self.update_view(interaction)
        return callback

    def create_use_callback(self, inv_item, item_details):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            stats = item_details.get('stats', {})
            effect = stats.get('effect')
            xp_boost = stats.get('xp_boost')
            
            # --- 🗝️ 1. فتح بوابة خاصة ---
            if effect == 'open_portal':
                target_level = stats.get('target_level')
                tier = stats.get('tier', 'E')
                if target_level == "random":
                    target_level = random.choice([20, 50, 80])
                
                portal_cog = self.bot.get_cog("PortalSystem")
                if portal_cog:
                    await db._execute_async(lambda: db.client.table('player_inventory').delete().eq('id', inv_item['id']).execute())
                    await portal_cog.create_private_portal(interaction, target_level, tier)
                    return 
                else:
                    await interaction.followup.send("❌ نظام البوابات غير نشط حالياً.", ephemeral=True)
                    return

            # --- 🛠️ 2. إصلاح المعدات المرتدية ---
            elif effect == 'repair':
                amount = stats.get('amount', 50)
                equipped = [i for i in self.inventory_items if i['is_equipped'] and i['item']['type'] != 'consumable']
                repaired = 0
                for item in equipped:
                    curr = item['current_durability']
                    max_d = item['item']['stats'].get('max_durability', 100)
                    if curr < max_d:
                        new_dur = min(max_d, curr + amount)
                        await db._execute_async(lambda: db.client.table('player_inventory').update({'current_durability': new_dur}).eq('id', item['id']).execute())
                        repaired += 1
                
                msg = f"✅ تم إصلاح {repaired} قطعة!" if repaired else "⚠️ معداتك سليمة تماماً."
                await db._execute_async(lambda: db.client.table('player_inventory').delete().eq('id', inv_item['id']).execute())
                await interaction.followup.send(msg, ephemeral=True)

            # --- ⚡ 3. استعادة الطاقة ---
            elif effect == 'restore_energy':
                curr_en = self.player_data.get('current_energy', 100)
                max_en = self.player_data.get('max_energy', 100)
                amount = stats.get('amount', 20)
                if curr_en >= max_en:
                    await interaction.followup.send("⚡ طاقتك ممتلئة بالفعل!", ephemeral=True)
                    return 
                new_en = min(max_en, curr_en + amount)
                await db._execute_async(lambda: db.client.table('players').update({'current_energy': new_en}).eq('id', self.player_data['id']).execute())
                await db._execute_async(lambda: db.client.table('player_inventory').delete().eq('id', inv_item['id']).execute())
                await interaction.followup.send(f"✅ تم شحن الطاقة: {curr_en} ➔ {new_en} ⚡", ephemeral=True)

            # --- 🧪 4. تفعيل مضاعف الخبرة (XP Boost) ---
            elif xp_boost is not None:
                duration = stats.get('duration_hours', 24)
                category = stats.get('category', 'all')
                expiry = (datetime.now() + timedelta(hours=duration)).isoformat()
                
                buff_data = {
                    "player_id": self.player_data['id'],
                    "buff_name": item_details['name'],
                    "buff_type": f"xp_boost_{category}",
                    "value": xp_boost,
                    "expires_at": expiry
                }
                await db._execute_async(lambda: db.client.table('player_buffs').insert(buff_data).execute())
                await db._execute_async(lambda: db.client.table('player_inventory').delete().eq('id', inv_item['id']).execute())
                await interaction.followup.send(f"🧪 تفعيل مؤقت: حصلت على زيادة {int(xp_boost*100)}% XP لمدة {duration} ساعة!", ephemeral=True)

            # --- ❄️ 5. حماية الستريك (Streak Freeze) ---
            elif effect == 'streak_freeze':
                expiry = (datetime.now() + timedelta(hours=24)).isoformat()
                buff_data = {
                    "player_id": self.player_data['id'],
                    "buff_name": "حماية الستريك ❄️",
                    "buff_type": "streak_protection",
                    "value": 1,
                    "expires_at": expiry
                }
                await db._execute_async(lambda: db.client.table('player_buffs').insert(buff_data).execute())
                await db._execute_async(lambda: db.client.table('player_inventory').delete().eq('id', inv_item['id']).execute())
                await interaction.followup.send(f"❄️ تم تفعيل الحماية! ستريكك محمي من الفشل لمدة 24 ساعة.", ephemeral=True)

            # --- 📜 6. إزالة عقوبة مالية (صك الغفران) ---
            elif effect == 'remove_financial_penalty':
                # جلب أقدم عقوبة مالية معلقة
                penalties = await db._execute_async(lambda: db.client.table('penalties')
                    .select('*').eq('player_id', self.player_data['id'])
                    .eq('status', 'pending').order('created_at').limit(1).execute())
                
                if penalties.data:
                    await db._execute_async(lambda: db.client.table('penalties')
                        .update({'status': 'forgiven', 'forgiven_reason': 'استخدام صك الغفران'})
                        .eq('id', penalties.data[0]['id']).execute())
                    await db._execute_async(lambda: db.client.table('player_inventory').delete().eq('id', inv_item['id']).execute())
                    await interaction.followup.send(f"📜 تم مسح عقوبة بقيمة **{penalties.data[0]['amount']}** بنجاح!", ephemeral=True)
                else:
                    await interaction.followup.send("⚠️ ليس لديك عقوبات مالية معلقة حالياً.", ephemeral=True)
                    return

            else:
                await interaction.followup.send("✅ تم استخدام العنصر بنجاح.", ephemeral=True)

            await self.load_inventory()
            await self.update_view(interaction)
        return callback

    # --- دوال التنقل ---
    async def filter_callback(self, i): self.current_filter = i.data['values'][0]; self.current_page = 0; await i.response.defer(); await self.update_view(i)
    async def prev_page(self, i): self.current_page -= 1; await i.response.defer(); await self.update_view(i)
    async def next_page(self, i): self.current_page += 1; await i.response.defer(); await self.update_view(i)