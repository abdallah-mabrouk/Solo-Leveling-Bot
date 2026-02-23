import discord
from discord.ui import View, Button, Select
from discord import ButtonStyle, SelectOption
from database import db
import math
from inventory_gen import InventoryGenerator # تأكد أن هذا الملف موجود

class ShopView(View):
    def __init__(self, user_id, player_uuid, user_coins, user_gems):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.player_uuid = player_uuid # ✅ حفظناه هنا لنستخدمه مباشرة
        self.user_coins = user_coins
        self.user_gems = user_gems
        
        self.current_page = 0
        self.items_per_page = 24 # العرض الشبكي الكامل
        self.current_filter = "all" 
        self.items = []
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("🛑 هذا المتجر خاص باللاعب الذي استدعاه!", ephemeral=True)
            return False
        return True

    async def load_items(self):
        """جلب العناصر من قاعدة البيانات"""
        # 1. جلب كل العناصر المتاحة
        query = db.client.table('system_shop_items').select('*').eq('is_available', True)
            
        # 2. تطبيق فلتر النوع
        if self.current_filter != "all":
            query = query.eq('type', self.current_filter)
            
        response = await db._execute_async(lambda: query.execute())
        all_items = response.data

        # 3. فلترة المخزون يدوياً (لأن Supabase لا يدعم OR بسهولة في التصفية المباشرة مع NULL)
        # نقبل العنصر إذا كان مخزونه (None = لا نهائي) أو (أكبر من 0)
        self.items = [
            item for item in all_items 
            if item.get('stock') is None or item.get('stock') > 0
        ]
        
        # ترتيب العناصر: الرانك E أولاً ثم السعر
        rank_order = {"E": 1, "D": 2, "C": 3, "B": 4, "A": 5, "S": 6, "SS": 7}
        self.items.sort(key=lambda x: (rank_order.get(x.get('rarity', 'E'), 1), x['price']))

    async def update_view(self, interaction: discord.Interaction):
        """تحديث الواجهة بالصورة والقوائم"""
        self.clear_items()
        
        # 1. حساب الصفحات
        total_pages = math.ceil(len(self.items) / self.items_per_page)
        self.current_page = max(0, min(self.current_page, total_pages - 1))
        
        # 2. جلب عناصر الصفحة
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        current_items = self.items[start_idx:end_idx]
        
        # 3. توليد الصورة
        gen = InventoryGenerator()
        image_buffer = await gen.generate(
            items=current_items,
            title="متجر النظام | SHOP",
            page=self.current_page + 1,
            total_pages=total_pages
        )
        
        file = discord.File(fp=image_buffer, filename="shop.png")
        embed = discord.Embed(
            title="", 
            description=f"**الرصيد:** 🪙 {self.user_coins:,} | 💎 {self.user_gems:,}",
            color=discord.Color.gold()
        )
        embed.set_image(url="attachment://shop.png")

        # 4. عناصر التحكم
        self.add_filter_select()

        # ب) قائمة الشراء (مع التفاصيل الذكية)
        if current_items:
            buy_options = []
            for item in current_items:
                # السعر
                price = f"{item['price']}G" if item['currency']=='coins' else f"{item['price']}💎"
                label = f"{item['name'][:20]} ({price})"
                
                # --- صياغة الوصف (التأثيرات) ---
                stats = item.get('stats', {})
                desc_parts = []
                
                if 'xp_boost' in stats:
                    cat = stats.get('category', 'All')[:3].upper()
                    desc_parts.append(f"+{int(stats['xp_boost']*100)}% XP {cat}")
                    
                if 'effect' in stats:
                    if stats['effect'] == 'open_portal':
                        desc_parts.append(f"يفتح بوابة Lv.{stats.get('target_level')}")
                    elif stats['effect'] == 'repair':
                        desc_parts.append(f"إصلاح {stats.get('amount', 0)}%")
                    elif stats['effect'] == 'restore_energy':
                        desc_parts.append("مشروب طاقة")
                        
                if 'penalty_reduction_money' in stats:
                     desc_parts.append(f"-{int(stats['penalty_reduction_money']*100)}% عقوبة")

                # تجميع الوصف
                full_desc = " | ".join(desc_parts) if desc_parts else item.get('description', '')[:50]
                
                buy_options.append(SelectOption(
                    label=label, 
                    value=item['id'], 
                    description=full_desc[:100] # ديسكورد يقبل 100 حرف كحد أقصى للوصف
                ))
            
            buy_select = Select(placeholder="اختر عنصراً لمعرفة التفاصيل والشراء...", options=buy_options, row=1)
            
            async def buy_select_callback(inter):
                selected_id = inter.data['values'][0]
                item_to_buy = next((i for i in self.items if i['id'] == selected_id), None)
                if item_to_buy:
                    await self.confirm_buy(inter, item_to_buy)
            
            buy_select.callback = buy_select_callback
            self.add_item(buy_select)

        # ج) أزرار التنقل
        if total_pages > 1:
            prev_btn = Button(label="السابق", style=ButtonStyle.secondary, disabled=(self.current_page == 0), row=2)
            next_btn = Button(label="التالي", style=ButtonStyle.secondary, disabled=(self.current_page >= total_pages - 1), row=2)
            prev_btn.callback = self.prev_page
            next_btn.callback = self.next_page
            self.add_item(prev_btn)
            self.add_item(next_btn)
            
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self, attachments=[file])
        else:
            await interaction.response.edit_message(embed=embed, view=self, attachments=[file])

    # ============ منطق الشراء ============

    async def confirm_buy(self, interaction: discord.Interaction, item):
        """إرسال رسالة تأكيد بشراء العنصر"""
        view = View(timeout=60)
        
        # زر التأكيد
        confirm_btn = Button(label="تأكيد الشراء ✅", style=ButtonStyle.success)
        confirm_btn.callback = self.create_buy_callback(item)
        
        # زر الإلغاء
        cancel_btn = Button(label="إلغاء", style=ButtonStyle.secondary)
        async def cancel_cb(inter):
            await inter.response.edit_message(content="❌ تم إلغاء العملية.", view=None)
        cancel_btn.callback = cancel_cb

        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        
        cost_text = f"{item['price']} {'Gold' if item['currency']=='coins' else 'Gems'}"
        await interaction.response.send_message(
            f"هل أنت متأكد من شراء **{item['name']}** بسعر **{cost_text}**؟", 
            view=view, 
            ephemeral=True
        )

    def create_buy_callback(self, item):
        """إنشاء دالة الشراء الفعلية"""
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            
            # 1. التحقق من الرصيد
            cost = item['price']
            currency = item['currency']
            user_balance = self.user_coins if currency == 'coins' else self.user_gems
            
            if user_balance < cost:
                await interaction.followup.send(f"❌ ليس لديك رصيد كافٍ! تحتاج {cost} {currency}.", ephemeral=True)
                return

            try:
                # 2. خصم الرصيد
                new_balance = user_balance - cost
                update_field = {'coins': new_balance} if currency == 'coins' else {'gems': new_balance}
                
                await db.update_player(str(self.user_id), update_field)
                
                # 3. إضافة للمخزن (نستخدم self.player_uuid مباشرة) ✅
                inventory_item = {
                    "player_id": self.player_uuid, 
                    "item_id": item['id'],
                    "current_durability": item.get('stats', {}).get('max_durability', 100),
                    "is_equipped": False
                }
                
                await db._execute_async(lambda: db.client.table('player_inventory').insert(inventory_item).execute())
                
                # 4. تحديث المخزون (Stock)
                if item['stock'] is not None:
                    new_stock = max(0, item['stock'] - 1)
                    await db._execute_async(
                        lambda: db.client.table('system_shop_items')
                        .update({'stock': new_stock})
                        .eq('id', item['id']).execute()
                    )
                
                # تحديث الرصيد المحلي في الكلاس
                if currency == 'coins': self.user_coins = new_balance
                else: self.user_gems = new_balance
                
                await interaction.followup.send(f"✅ تم شراء **{item['name']}** بنجاح!", ephemeral=True)
                
                # تحديث واجهة المتجر (لتحديث الرصيد والمخزون)
                await self.load_items()
                # ملاحظة: لا يمكننا تحديث الرسالة الأصلية بسهولة من هنا لأننا في رسالة ephemeral
                # لكن عند الضغط على التالي/السابق أو الفلترة ستتحدث البيانات
                
            except Exception as e:
                print(f"Buy Error: {e}")
                await interaction.followup.send("❌ حدث خطأ أثناء الشراء.", ephemeral=True)
                
        return callback

    # ============ دوال مساعدة ============

    def add_filter_select(self):
        options = [
            SelectOption(label="الكل", value="all", emoji="🌐"),
            SelectOption(label="الأسلحة", value="weapon", emoji="⚔️"),
            SelectOption(label="الدروع", value="armor", emoji="🛡️"),
            SelectOption(label="الأدوات", value="tool", emoji="🛠️"),
            SelectOption(label="إكسسوارات", value="accessory", emoji="💍"),
            SelectOption(label="استهلاكيات", value="consumable", emoji="🧪"),
        ]
        # تحديد الخيار الحالي
        for opt in options:
            if opt.value == self.current_filter:
                opt.default = True
                
        select = Select(placeholder="تصفية حسب النوع...", options=options, row=0)
        select.callback = self.filter_callback
        self.add_item(select)

    async def filter_callback(self, interaction: discord.Interaction):
        self.current_filter = interaction.data['values'][0]
        self.current_page = 0
        await interaction.response.defer()
        await self.load_items()
        await self.update_view(interaction)

    async def prev_page(self, interaction: discord.Interaction):
        self.current_page -= 1
        await interaction.response.defer()
        await self.update_view(interaction)

    async def next_page(self, interaction: discord.Interaction):
        self.current_page += 1
        await interaction.response.defer()
        await self.update_view(interaction)

    async def get_player_uuid(self, discord_id):
        p = await db.get_player(discord_id)
        return p['id']