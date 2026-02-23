from PIL import Image, ImageDraw, ImageFont
import aiohttp
from io import BytesIO
import arabic_reshaper
from bidi.algorithm import get_display
import os

class ProfileGenerator:
    def __init__(self):
        self.bg_path = "assets/bg.png"
        self.font_path = "assets/font.ttf"
        
        self.C_BG = (10, 15, 25, 255)
        self.C_PANEL = (0, 0, 0, 180)
        self.C_TEXT = (255, 255, 255, 255)
        self.C_ACCENT = (0, 180, 255, 255) 
        self.C_RANK_S = (255, 215, 0, 255)
        self.C_GOLD = (255, 215, 0, 255)
        self.C_GEM = (0, 220, 255, 255)
        
        self.RANK_COLORS = {
            "E": (200, 200, 200), "D": (0, 200, 50), 
            "C": (0, 100, 255), "B": (150, 0, 200),
            "A": (255, 50, 50), "S": (255, 215, 0), "SS": (100, 0, 150)
        }

    async def load_image(self, url):
        try:
            if not url: return None
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return Image.open(BytesIO(await resp.read())).convert("RGBA")
        except: return None

    def draw_text(self, draw, text, x, y, size=20, color=None, align="right", stroke=True):
        if not color: color = self.C_TEXT
        reshaped = arabic_reshaper.reshape(str(text))
        bidi_text = get_display(reshaped)
        try: font = ImageFont.truetype(self.font_path, size)
        except: font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), bidi_text, font=font)
        text_width = bbox[2] - bbox[0]
        
        draw_x = x
        if align == "right": draw_x = x - text_width
        elif align == "center": draw_x = x - (text_width / 2)
            
        stroke_width = 2 if stroke else 0
        stroke_thickness = 1 if size < 20 else 2
        draw.text((draw_x, y), bidi_text, font=font, fill=color, stroke_width=stroke_thickness, stroke_fill=(0,0,0) if stroke else None)

    def draw_bar(self, draw, x, y, w, h, current, total, color):
        draw.rectangle([x, y, x+w, y+h], fill=(30, 30, 30, 200), outline=(100,100,100), width=1)
        if total > 0:
            pct = min(1.0, max(0.0, current / total))
            fill_w = int(w * pct)
            draw.rectangle([x, y, x+fill_w, y+h], fill=color)

    async def generate(self, player, avatar_url, gear):
        # 1. إعداد الخلفية
        if os.path.exists(self.bg_path):
            base = Image.open(self.bg_path).convert("RGBA").resize((900, 600))
        else:
            base = Image.new("RGBA", (900, 600), self.C_BG)
            
        # 2. رسم الشخصية
        if avatar_url:
            char = await self.load_image(avatar_url)
            if char:
                target_height = 580
                aspect_ratio = char.width / char.height
                target_width = int(target_height * aspect_ratio)
                char = char.resize((target_width, target_height), Image.Resampling.LANCZOS)
                x_pos = (900 - target_width) // 2
                y_pos = 10 
                base.paste(char, (x_pos, y_pos), char)

        # 3. الطبقات الشفافة
        overlay = Image.new("RGBA", base.size, (0,0,0,0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle([20, 20, 280, 580], fill=self.C_PANEL, outline=self.C_ACCENT, width=2)
        draw.rectangle([620, 20, 880, 580], fill=self.C_PANEL, outline=self.C_ACCENT, width=2)
        
        base = Image.alpha_composite(base, overlay)
        draw = ImageDraw.Draw(base)

        # ==========================
        # 4. تعبئة البيانات (يسار)
        # ==========================
        self.draw_text(draw, player['username'], 150, 35, 26, self.C_ACCENT, "center")
        self.draw_text(draw, f"[{player.get('active_title', 'مبتدئ')}]", 150, 70, 20, (200, 200, 200), "center")
        
        rank = player['rank']
        rank_color = self.RANK_COLORS.get(rank, self.C_TEXT)
        self.draw_text(draw, f"Rank: {rank}", 150, 100, 30, rank_color, "center")
        
        # المستوى
        self.draw_text(draw, f"Level {player['total_level']}", 40, 145, 18, align="left")
        self.draw_bar(draw, 40, 170, 220, 8, player['total_level'] % 10, 10, self.C_GOLD)
        
        # الطاقة (تم التصحيح هنا) ✅
        curr_en = player.get('current_energy', 100)
        max_en = player.get('max_energy', 100)
        self.draw_text(draw, f"Energy {curr_en}/{max_en}", 40, 185, 18, align="left")
        self.draw_bar(draw, 40, 210, 220, 8, curr_en, max_en, (0, 100, 255))
        
        # الستريك
        streak = player.get('streak_days', 0)
        self.draw_text(draw, "Streak:", 40, 230, 20, self.C_ACCENT, align="left")
        self.draw_text(draw, f"{streak} Days 🔥", 260, 230, 20, align="right")

        # العملات
        coins = f"{player.get('coins', 0):,}"
        gems = f"{player.get('gems', 0):,}"
        self.draw_text(draw, f"{coins} GOLD", 260, 270, 20, self.C_GOLD, align="right")
        self.draw_text(draw, f"{gems} GEMS", 260, 300, 20, self.C_GEM, align="right")

        # القدرات
        stats_map = [("STR", "strength_level"), ("INT", "intelligence_level"), ("VIT", "vitality_level"), ("AGI", "agility_level"), ("PER", "perception_level"), ("FRE", "freedom_level")]
        y_st = 350
        for label, key in stats_map:
            val = player.get(key, 0)
            self.draw_text(draw, f"{label}", 40, y_st, 20, self.C_ACCENT, "left")
            self.draw_text(draw, f"{val}", 260, y_st, 20, self.C_TEXT, "right")
            draw.line([40, y_st+28, 260, y_st+28], fill=(80,80,80), width=1)
            y_st += 35

        # ==========================
        # 5. تعبئة المعدات (يمين)
        # ==========================
        self.draw_text(draw, "Equipment", 750, 40, 28, self.C_ACCENT, "center")
        
        slot_y = 90
        for i in range(4):
            # خلفية العنصر
            draw.rectangle([640, slot_y, 860, slot_y+90], fill=(255,255,255,10), outline=(100,100,100))
            
            if i < len(gear):
                item = gear[i]['item']
                rarity = item.get('rarity', 'E')
                color = self.RANK_COLORS.get(rarity, self.C_TEXT)
                
                # 1. رسم الأيقونة
                item_icon_url = item.get('image_url')
                if item_icon_url:
                    icon_img = await self.load_image(item_icon_url)
                    if icon_img:
                        icon_img = icon_img.resize((80, 80))
                        base.paste(icon_img, (645, slot_y + 5), icon_img)
                else:
                    # إذا لم توجد صورة، نكتب أول حرفين كبديل مؤقت
                    self.draw_text(draw, item['name'][:2], 685, slot_y+45, 30, (80,80,80), "center")

                # 2. النصوص
                draw.rectangle([855, slot_y+10, 860, slot_y+30], fill=color)
                
                # الاسم
                self.draw_text(draw, item['name'][:12], 850, slot_y+10, 18, color, "right")
                
                # استخراج التأثير بشكل ذكي
                stats = item.get('stats', {})
                effect_text = "Special"
                
                if 'xp_boost' in stats: 
                    cat = stats.get('category', '')
                    cat_map = {"strength":"STR", "intelligence":"INT", "vitality":"VIT", "agility":"AGI", "freedom":"FRE", "perception":"PER"}
                    short_cat = cat_map.get(cat, "")
                    effect_text = f"+{int(stats['xp_boost']*100)}% {short_cat}"
                    
                elif 'effect' in stats:
                    if stats['effect'] == 'open_portal': effect_text = f"Key Lv.{stats.get('target_level')}"
                    elif stats['effect'] == 'repair': effect_text = "Repair Tool"
                    
                elif 'penalty_reduction_money' in stats:
                    effect_text = "Protect Money"

                # رسم التأثير
                self.draw_text(draw, effect_text, 850, slot_y+40, 14, (200,200,200), "right")
                
                # المتانة
                dur = gear[i]['current_durability']
                self.draw_text(draw, f"Dur: {dur}%", 850, slot_y+65, 12, (150,150,150), "right")
                
            else:
                self.draw_text(draw, "فارغ", 750, slot_y+35, 18, (100,100,100), "center")
            
            slot_y += 110

        buffer = BytesIO()
        base.save(buffer, "PNG")
        buffer.seek(0)
        return buffer