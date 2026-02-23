import discord
from discord.ui import View, Button, Select, Modal, TextInput
from discord import ButtonStyle, SelectOption
from database import db

class SettingsView(View):
    def __init__(self, user_id, player_data):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.player_data = player_data
        self.build_ui()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("🛑 هذه الإعدادات خاصة باللاعب المستدعي فقط!", ephemeral=True)
            return False
        return True

    def build_ui(self):
        self.clear_items()
        
        # 1. زر تحديث الحالة 🎭
        status_map = {"active": "نشط 🔥", "sick": "مريض 🩹", "traveling": "مسافر ✈️", "excuse": "عذر شرعي ✨"}
        current_status = status_map.get(self.player_data.get('status', 'active'), "نشط 🔥")
        status_btn = Button(label=f"حالتـي: {current_status}", style=ButtonStyle.secondary, emoji="🎭", row=0)
        status_btn.callback = self.change_status_callback
        self.add_item(status_btn)

        # 2. زر الجوانب المفعلة 🎯
        aspect_btn = Button(label="الجوانب المفعلة", style=ButtonStyle.primary, emoji="🎯", row=0)
        aspect_btn.callback = self.toggle_aspects_callback
        self.add_item(aspect_btn)

        # 3. زر الإشعارات 🔕
        notif_enabled = self.player_data.get('notifications_enabled', True)
        notif_status = "مفعلة ✅" if notif_enabled else "معطلة 🔕"
        notif_style = ButtonStyle.success if notif_enabled else ButtonStyle.danger
        notif_btn = Button(label=f"الإشعارات: {notif_status}", style=notif_style, row=1)
        notif_btn.callback = self.toggle_notifications_callback
        self.add_item(notif_btn)
        
        # 4. زر تحديد العمر 👴
        age_map = {"young": "شاب ⚡", "senior": "كبير سن 👴"}
        current_age = age_map.get(self.player_data.get('age_group', 'young'), "شاب ⚡")
        age_btn = Button(label=f"الفئة: {current_age}", style=ButtonStyle.secondary, emoji="⏳", row=1)
        age_btn.callback = self.change_age_callback
        self.add_item(age_btn)

        # 5. زر أيام الإجازة 🏖️
        off_days_btn = Button(label="تحديد أيام الإجازة", style=ButtonStyle.secondary, emoji="🏖️", row=2)
        off_days_btn.callback = self.change_off_days_callback
        self.add_item(off_days_btn)
        
        # 6. زر العملة 💰
        curr = self.player_data.get('currency', 'USD')
        curr_btn = Button(label=f"العملة: {curr}", style=ButtonStyle.secondary, emoji="💰", row=2)
        curr_btn.callback = self.change_currency_callback
        self.add_item(curr_btn)

    async def update_view(self, interaction: discord.Interaction, content: str = None):
        new_data = await db.get_player(str(self.user_id))
        if new_data: self.player_data = new_data
        self.build_ui()
        if interaction.response.is_done():
            await interaction.edit_original_response(content=content, view=self)
        else:
            await interaction.response.edit_message(content=content, view=self)

    # --- Callbacks ---

    async def change_status_callback(self, interaction: discord.Interaction):
        view = StatusSelectionView(self.user_id, self.player_data, self)
        await interaction.response.send_message("🎭 اختر حالتك الحالية لتكييف مهام اليوم:", view=view, ephemeral=True)

    async def toggle_notifications_callback(self, interaction: discord.Interaction):
        current = self.player_data.get('notifications_enabled', True)
        await db.update_player(str(self.user_id), {'notifications_enabled': not current})
        await self.update_view(interaction)

    async def toggle_aspects_callback(self, interaction: discord.Interaction):
        view = AspectToggleView(self.user_id, self.player_data, self)
        await interaction.response.send_message("🎯 اختر الجوانب التي تلتزم بها اليوم:", view=view, ephemeral=True)

    async def change_age_callback(self, interaction: discord.Interaction):
        """تعديل الفئة العمرية"""
        view = AgeSelectionView(self.user_id, self.player_data, self)
        await interaction.response.send_message("⏳ اختر فئتك العمرية لتعديل صعوبة المهام:", view=view, ephemeral=True)

    async def change_off_days_callback(self, interaction: discord.Interaction):
        """تعديل أيام الإجازة"""
        view = OffDaysView(self.user_id, self.player_data, self)
        await interaction.response.send_message("🏖️ اختر أيام إجازتك الأسبوعية (سيتم تخطي مهام العمل فيها):", view=view, ephemeral=True)
        
    async def change_currency_callback(self, interaction: discord.Interaction):
        view = CurrencySelectionView(self.user_id, self.player_data, self)
        await interaction.response.send_message("💱 اختر عملة العقوبات والتبرع:", view=view, ephemeral=True)

# --- View فرعي: اختيار الحالة ---
class StatusSelectionView(View):
    def __init__(self, user_id, player_data, parent_view):
        super().__init__(timeout=300)
        self.user_id, self.parent_view = user_id, parent_view
        options = [
            SelectOption(label="نشط", value="active", emoji="🔥"),
            SelectOption(label="مريض", value="sick", emoji="🩹"),
            SelectOption(label="مسافر", value="traveling", emoji="✈️"),
        ]
        if player_data.get('gender') == 'female' and player_data.get('faith_type') == 'muslim':
            options.append(SelectOption(label="عذر شرعي", value="excuse", emoji="✨"))
        select = Select(placeholder="اختر حالتك...", options=options)
        select.callback = self.callback
        self.add_item(select)

    async def callback(self, interaction: discord.Interaction):
        val = interaction.data['values'][0]
        await db.update_player(str(self.user_id), {'status': val})
        await interaction.response.send_message(f"✅ تم تحديث الحالة إلى: **{val}**", ephemeral=True)
        await self.parent_view.update_view(interaction)

# --- View فرعي: اختيار العمر (جديد ✅) ---
class AgeSelectionView(View):
    def __init__(self, user_id, player_data, parent_view):
        super().__init__(timeout=300)
        self.user_id, self.parent_view = user_id, parent_view
        options = [
            SelectOption(label="شاب (مهام كاملة)", value="young", emoji="⚡"),
            SelectOption(label="كبير سن (مهام مخففة)", value="senior", emoji="👴")
        ]
        select = Select(placeholder="اختر الفئة العمرية...", options=options)
        select.callback = self.callback
        self.add_item(select)

    async def callback(self, interaction: discord.Interaction):
        val = interaction.data['values'][0]
        await db.update_player(str(self.user_id), {'age_group': val})
        await interaction.response.send_message(f"✅ تم تحديث الفئة العمرية إلى: **{val}**", ephemeral=True)
        await self.parent_view.update_view(interaction)

# --- View فرعي: أيام الإجازة (جديد ✅) ---
class OffDaysView(View):
    def __init__(self, user_id, player_data, parent_view):
        super().__init__(timeout=300)
        self.user_id, self.parent_view = user_id, parent_view
        days = [
            ("الأثنين", "0"), ("الثلاثاء", "1"), ("الأربعاء", "2"), 
            ("الخميس", "3"), ("الجمعة", "4"), ("السبت", "5"), ("الأحد", "6")
        ]
        options = [SelectOption(label=name, value=val) for name, val in days]
        
        # استرجاع القيم الحالية لتكون Default
        current_off = player_data.get('off_days', [])
        for opt in options:
            if int(opt.value) in current_off: opt.default = True

        select = Select(
            placeholder="اختر أيام الإجازة...", 
            options=options, 
            min_values=0, 
            max_values=7
        )
        select.callback = self.callback
        self.add_item(select)

    async def callback(self, interaction: discord.Interaction):
        selected_days = [int(v) for v in interaction.data['values']]
        await db.update_player(str(self.user_id), {'off_days': selected_days})
        await interaction.response.send_message(f"✅ تم تحديث أيام الإجازة بنجاح.", ephemeral=True)
        await self.parent_view.update_view(interaction)

# --- View فرعي: تفعيل الجوانب ---
class AspectToggleView(View):
    def __init__(self, user_id, player_data, parent_view):
        super().__init__(timeout=300)
        self.user_id, self.player_data, self.parent_view = user_id, player_data, parent_view
        options = [
            SelectOption(label="القوة البدنية", value="strength", emoji="💪"),
            SelectOption(label="الذكاء والمعرفة", value="intelligence", emoji="🧠"),
            SelectOption(label="الصحة والعافية", value="vitality", emoji="❤️"),
            SelectOption(label="المهارات الاجتماعية", value="agility", emoji="🤝"),
            SelectOption(label="الحرية المالية", value="freedom", emoji="💸"),
        ]
        if player_data.get('faith_type') == 'muslim':
            options.append(SelectOption(label="الجانب الديني", value="perception", emoji="🕌"))

        for opt in options:
            if player_data.get(f"{opt.value}_intensity", 0) > 0: opt.default = True

        select = Select(placeholder="حدد الجوانب النشطة...", options=options, min_values=1, max_values=len(options))
        select.callback = self.callback
        self.add_item(select)

    async def callback(self, interaction: discord.Interaction):
        selected = interaction.data['values']
        update_data = {}
        for asp in ['strength', 'intelligence', 'vitality', 'agility', 'freedom', 'perception']:
            key = f"{asp}_intensity"
            if asp in selected:
                if self.player_data.get(key, 0) == 0: update_data[key] = 5
            else: update_data[key] = 0
        
        await db.update_player(str(self.user_id), update_data)
        await interaction.response.send_message("✅ تم تحديث جوانب التطوير.", ephemeral=True)
        await self.parent_view.update_view(interaction)
        
        
class CurrencySelectionView(View):
    def __init__(self, user_id, player_data, parent_view):
        super().__init__(timeout=300)
        self.user_id, self.parent_view = user_id, parent_view
        
        currencies = [
            ("ريال سعودي", "SAR"), ("جنيه مصري", "EGP"), ("درهم إماراتي", "AED"),
            ("دينار كويتي", "KWD"), ("ريال قطري", "QAR"), ("دينار بحريني", "BHD"),
            ("ريال عماني", "OMR"), ("دينار أردني", "JOD"), ("دولار أمريكي", "USD"),
            ("يورو", "EUR")
        ]
        
        options = [SelectOption(label=name, value=code) for name, code in currencies]
        select = Select(placeholder="اختر عملتك المحلية...", options=options)
        
        async def cb(interaction):
            val = select.values[0]
            await db.update_player(str(self.user_id), {'currency': val})
            await interaction.response.send_message(f"✅ تم تحديث العملة إلى: **{val}**", ephemeral=True)
            await self.parent_view.update_view(interaction)
            
        select.callback = cb
        self.add_item(select)