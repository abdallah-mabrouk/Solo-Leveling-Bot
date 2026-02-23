from PIL import Image, ImageDraw, ImageFont
import aiohttp
from io import BytesIO
import arabic_reshaper
from bidi.algorithm import get_display
import os
import math
import asyncio

# مخزن مؤقت (Cache) بسيط في الذاكرة للأيقونات
ICON_CACHE = {}

class InventoryGenerator:
    def __init__(self):
        self.bg_path = "assets/inventory_bg.jpeg" 
        self.font_path = "assets/font.ttf"
        
        self.IMG_W, self.IMG_H = 1200, 850   
        self.GRID_COLS = 8
        self.GRID_ROWS = 3
        self.SLOT_SIZE = 100 
        self.GAP_X = 15      
        self.GAP_Y = 90      
        
        total_grid_width = (self.GRID_COLS * self.SLOT_SIZE) + ((self.GRID_COLS - 1) * self.GAP_X)
        self.START_X = (self.IMG_W - total_grid_width) // 2
        self.START_Y = 220 
        
        self.C_TEXT = (255, 255, 255, 255)
        self.C_GOLD = (255, 215, 0, 255)
        self.C_PRICE = (0, 255, 200, 255)
        self.C_TITLE_BG = (20, 20, 30, 230)
        self.C_SLOT_BG = (0, 0, 0, 100)     
        
        self.RANK_COLORS = {
            "E": (200, 200, 200), "D": (50, 200, 50), 
            "C": (0, 150, 255), "B": (150, 50, 255),
            "A": (255, 50, 50), "S": (255, 215, 0), "SS": (180, 0, 255)
        }
        
        # تحميل الأصول الثابتة مرة واحدة عند البدء (Pre-load)
        self.font = None
        self.base_bg = None
        self._load_static_assets()

    def _load_static_assets(self):
        """تحميل الخط والخلفية في الذاكرة لتجنب قراءتهم كل مرة"""
        try:
            self.font = ImageFont.truetype(self.font_path, 15)
        except:
            self.font = ImageFont.load_default()
            
        if os.path.exists(self.bg_path):
            self.base_bg = Image.open(self.bg_path).convert("RGBA").resize((self.IMG_W, self.IMG_H))
        else:
            self.base_bg = Image.new("RGBA", (self.IMG_W, self.IMG_H), (20, 20, 35, 255))

    async def load_image(self, url):
        """تحميل صورة مع التخزين المؤقت (Caching)"""
        if not url: return None
        
        # 1. هل الصورة موجودة في الكاش؟
        if url in ICON_CACHE:
            return ICON_CACHE[url].copy() # نرسل نسخة لعدم تعديل الأصل

        # 2. تحميل من النت
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
                        img = Image.open(BytesIO(img_data)).convert("RGBA")
                        
                        # تصغيرها وحفظها في الكاش لتوفير الذاكرة
                        icon_size = self.SLOT_SIZE - 10
                        img.thumbnail((icon_size, icon_size), Image.Resampling.LANCZOS)
                        
                        ICON_CACHE[url] = img
                        return img
        except: return None

    def draw_text(self, draw, text, x, y, size=15, color=None, align="center"):
        if not color: color = self.C_TEXT
        
        # معالجة بسيطة (استخدام الخط المحمل مسبقاً إذا الحجم مطابق، وإلا تحميل جديد)
        font = self.font
        if size != 15:
             try: font = ImageFont.truetype(self.font_path, size)
             except: font = ImageFont.load_default()

        is_arabic = any('\u0600' <= char <= '\u06FF' for char in str(text))
        text_content = get_display(arabic_reshaper.reshape(str(text))) if is_arabic else str(text)

        bbox = draw.textbbox((0, 0), text_content, font=font)
        w = bbox[2] - bbox[0]
        draw_x = x - (w / 2) if align == "center" else x
        draw.text((draw_x, y), text_content, font=font, fill=color)

    async def generate(self, items, title="INVENTORY", page=1, total_pages=1):
        # استخدام نسخة من الخلفية المحملة مسبقاً
        base = self.base_bg.copy()
        draw = ImageDraw.Draw(base)

        # رسم العنوان
        display_title = "SYSTEM SHOP" if ("SHOP" in title.upper() or "متجر" in title) else "HUNTER INVENTORY"
        draw.rectangle([0, 80, self.IMG_W, 180], fill=self.C_TITLE_BG)
        draw.rectangle([0, 80, self.IMG_W, 85], fill=self.C_GOLD)
        draw.rectangle([0, 175, self.IMG_W, 180], fill=self.C_GOLD)
        self.draw_text(draw, display_title, self.IMG_W // 2, 110, 50, self.C_GOLD, "center")

        # === 🚀 التحميل المتوازي للصور ===
        # نجهز قائمة مهام التحميل
        tasks = []
        for item_data in items:
            details = item_data['item'] if 'item' in item_data else item_data
            url = details.get('image_url')
            tasks.append(self.load_image(url))
            
        # تنفيذ التحميل للكل في وقت واحد
        loaded_icons = await asyncio.gather(*tasks)

        # رسم العناصر
        for idx, item_data in enumerate(items):
            col = idx % self.GRID_COLS
            row = idx // self.GRID_COLS
            if row >= self.GRID_ROWS: break

            x = self.START_X + (col * (self.SLOT_SIZE + self.GAP_X))
            y = self.START_Y + (row * (self.SLOT_SIZE + self.GAP_Y))
            
            if 'item' in item_data: 
                details = item_data['item']
                is_equipped = item_data.get('is_equipped', False)
                durability = item_data.get('current_durability', 100)
                bottom_text = f"{durability}%"
                bottom_color = (200, 200, 200)
            else: 
                details = item_data
                is_equipped = False
                price = details.get('price', 0)
                currency = "G" if details.get('currency') == 'coins' else "💎"
                bottom_text = f"{price}{currency}"
                bottom_color = self.C_PRICE

            rarity = details.get('rarity', 'E')
            rank_color = self.RANK_COLORS.get(rarity, (200,200,200))
            
            # 1. الخلفية والإطار
            draw.rectangle([x, y, x+self.SLOT_SIZE, y+self.SLOT_SIZE], fill=self.C_SLOT_BG)
            draw.rectangle([x, y, x+self.SLOT_SIZE, y+self.SLOT_SIZE], outline=rank_color, width=2)
            
            # 2. الصورة (نأخذها من القائمة المحملة مسبقاً)
            icon = loaded_icons[idx]
            if icon:
                # توسيط الأيقونة
                icon_x = x + (self.SLOT_SIZE - icon.width) // 2
                icon_y = y + (self.SLOT_SIZE - icon.height) // 2
                base.paste(icon, (icon_x, icon_y), icon)

            # 3. المجهز
            if is_equipped:
                draw.rectangle([x, y, x+self.SLOT_SIZE, y+self.SLOT_SIZE], outline=(0,255,0), width=3)
                self.draw_text(draw, "E", x+self.SLOT_SIZE-15, y+5, 14, (0,255,0))

            # 4. الرانك
            draw.rectangle([x, y, x+25, y+25], fill=rank_color)
            self.draw_text(draw, rarity, x+12, y+2, 14, (0,0,0))

            # 5. النصوص
            text_center_x = x + (self.SLOT_SIZE // 2)
            
            name = details['name']
            if len(name) > 18: name = name[:16] + ".."
            self.draw_text(draw, name, text_center_x, y + self.SLOT_SIZE + 10, 11, rank_color, "center")

            stats = details.get('stats', {})
            stat_text = ""
            if 'xp_boost' in stats: stat_text = f"+{int(stats['xp_boost']*100)}% XP"
            elif 'effect' in stats: 
                eff = stats['effect']
                if eff == 'open_portal': stat_text = f"Lv.{stats.get('target_level')}"
                elif eff == 'repair': stat_text = "Repair"
                elif eff == 'restore_energy': stat_text = "+Energy"
            
            if stat_text:
                self.draw_text(draw, stat_text, text_center_x, y + self.SLOT_SIZE + 28, 10, (180, 180, 180), "center")

            self.draw_text(draw, bottom_text, text_center_x, y + self.SLOT_SIZE + 45, 14, bottom_color, "center")

        # رقم الصفحة
        self.draw_text(draw, f"PAGE {page} / {total_pages}", self.IMG_W // 2, 810, 20, self.C_TEXT, "center")

        buffer = BytesIO()
        base.save(buffer, "PNG")
        buffer.seek(0)
        return buffer