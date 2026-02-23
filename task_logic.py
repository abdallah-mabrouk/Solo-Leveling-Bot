# task_logic.py
from datetime import datetime
from hijri_converter import Gregorian # ✅ التعديل الأول: استيراد Gregorian بدلاً من Hijri
from tasks_library import ALL_TASKS



def get_daily_tasks_for_player(player_data):
    """
    الفلتر المطور الشامل: يقرر مهام اليوم بناءً على:
    (الجنس، العمر، الرتبة، أيام الإجازة، الحالة الصحية، التاريخ الميلادي والهجري)
    """
    # 1. إعداد التواريخ
    now = datetime.now()
    today_num = now.weekday() # 0=الأثنين ... 4=الجمعة
    day_of_month = now.day
    
    # التحويل للهجري
     # ✅ التعديل الثاني: الطريقة الصحيحة للتحويل باستخدام المكتبة
    hijri_obj = Gregorian(now.year, now.month, now.day).to_hijri()
    hijri_day = hijri_obj.day
    hijri_month = hijri_obj.month

    # 2. استخراج بيانات اللاعب
    player_status = player_data.get('status', 'active')
    player_gender = player_data.get('gender', 'male')
    player_age = player_data.get('age_group', 'young')
    player_rank = player_data.get('rank', 'E')
    
    raw_off_days = player_data.get('off_days', []) or []
    player_off_days = [int(d) for d in raw_off_days]
    
    assigned_tasks = {}

    # ترتيب الرتب للمقارنة (E هو الأضعف، SS هو الأقوى)
    ranks_order = ["E", "D", "C", "B", "A", "S", "SS"]

    for tid, original_info in ALL_TASKS.items():
        # نستخدم نسخة من المعلومات لعدم تعديل الأصل عند تغيير التوقعات
        info = original_info.copy()

        # ---------------------------------------------------------
        # 1. الفلاتر الأساسية (الجنس، العمل، الجدولة الميلادية)
        # ---------------------------------------------------------
        if "gender" in info and info["gender"] != player_gender:
            continue
            
        if info.get("is_work") and today_num in player_off_days:
            continue

        if info.get("schedule") == "friday" and today_num != 4:
            continue
        if info.get("schedule") == "first_of_month" and day_of_month != 1:
            continue

        # ---------------------------------------------------------
        # 2. فلترة المهام الاجتماعية (أيام الإجازة فقط)
        # ---------------------------------------------------------
        if info.get("is_off_day_only") and today_num not in player_off_days:
            continue

        # ---------------------------------------------------------
        # 3. فلترة العمر (كبار السن)
        # ---------------------------------------------------------
        if player_age == "senior":
            if info.get("frequency_senior") == "weekly":
                if info.get("schedule_senior") == "friday" and today_num != 4:
                    continue
            # تعديل التوقع لكبار السن (مثلاً غسيل الأسنان مرة واحدة)
            if "expect_senior" in info:
                info["target_label"] = info["expect_senior"] # مجرد وسم للعرض لاحقاً

        # ---------------------------------------------------------
        # 4. فلترة الحالات (مريض / عذر شرعي)
        # ---------------------------------------------------------
        if player_status == "sick":
            if info.get("exertion") in ["medium", "high"]:
                continue

        if player_status == "excuse":
            # تخطي المهام الدينية (إلا المستثناة مثل الأذكار) والمهام الشاقة
            if info.get("exertion") in ["medium", "high"]:
                continue
            if info.get("is_religious"):
                # السماح ببعض العبادات الخفيفة حتى مع العذر
                allowed_in_excuse = ["adhkar", "istighfar", "charity", "bad_words"]
                if not any(x in tid for x in allowed_in_excuse):
                    continue

        # ---------------------------------------------------------
        # 5. الفلاتر الدينية (الهجري) 🕌
        # ---------------------------------------------------------
        if "hijri_month" in info and info["hijri_month"] != hijri_month:
            continue
        if "hijri_day" in info and info["hijri_day"] != hijri_day:
            continue
        if "hijri_days" in info and hijri_day not in info["hijri_days"]:
            continue
        if "exclude_months" in info and hijri_month in info["exclude_months"]:
            continue
        if "weekdays" in info and today_num not in info["weekdays"]:
            continue

        # فلترة الرتبة للمهام الدينية (مثل قيام الليل)
        if "min_rank" in info:
            p_idx = ranks_order.index(player_rank)
            req_idx = ranks_order.index(info["min_rank"])
            if p_idx < req_idx: continue

        # ---------------------------------------------------------
        # 6. منطق القوة الخاص (Strength Logic) 💪
        # ---------------------------------------------------------
        if tid == "str_gym_session":
            if player_rank in ["SS", "S", "A"]:
                if today_num == 4: continue 
            elif player_rank in ["B", "C"]:
                if today_num not in [5, 0, 2]: continue 
            else:
                continue 

        if tid == "str_home_workout":
            if player_gender == "male" and player_rank not in ["E", "D"]:
                continue

        # ---------------------------------------------------------
        # 7. تعديل التوقعات حسب الرتبة (Scaling) 📈
        # ---------------------------------------------------------
        # مهام القراءة (الذكاء)
        if tid == "int_reading":
            targets = info.get("targets_by_rank", {})
            base_target = targets.get(player_rank, 15)
            # تخفيف لكبار السن
            if player_age == "senior": base_target = max(10, base_target // 2)
            info["targets"] = {"young": base_target, "senior": base_target}

        # مهام القرآن (الإدراك)
        if tid == "rel_quran":
            targets = info.get("targets_by_rank", {})
            base_target = targets.get(player_rank, 2)
            info["targets"] = {"young": base_target, "senior": base_target}

        # ✅ اعتماد المهمة
        assigned_tasks[tid] = info

    return assigned_tasks
def calculate_caffeine(coffee: float, tea: float):
    """منطق الـ 2:1 للكافيين مع التعامل مع الكسور"""
    try:
        total_units = (float(coffee) * 2) + (float(tea) * 1)
        if total_units <= 4: 
            return 1.0, None # نجاح كامل
        if total_units <= 6: 
            return 0.5, None # نجاح جزئي
        return 0.0, "caffeine_insomnia" # فشل وعقوبة سلبية
    except:
        return 0.0, None

def draw_progress_bar(current, total, length=12, completed_char="■", remaining_char="□"):
    """رسم شريط تقدم نصي احترافي"""
    try:
        if total <= 0: return remaining_char * length
        percent = current / total
        percent = min(1.0, max(0.0, percent))
        filled_length = int(length * percent)
        return completed_char * filled_length + remaining_char * (length - filled_length)
    except:
        return remaining_char * length