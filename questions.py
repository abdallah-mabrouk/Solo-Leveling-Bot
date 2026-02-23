# questions.py
import random
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass
import math

@dataclass
class AssessmentQuestion:
    """سؤال اختبار القدرات"""
    question: str
    category: str
    options: List[Dict[str, Any]]

# ============ أسئلة اختبار القدرات الكامل ============

ASSESSMENT_QUESTIONS = [
    # 💪 القوة (3 أسئلة)
    AssessmentQuestion(
        question="ما هو مستوى نشاطك البدني الحالي؟",
        category="strength",
        options=[
            {"text": "مستقر (قليل الحركة)", "value": "1", "points": 1},
            {"text": "خفيف (مشي يومي)", "value": "2", "points": 3},
            {"text": "متوسط (تمارين 2-3 مرات أسبوعياً)", "value": "3", "points": 5},
            {"text": "نشيط (تمارين 4-5 مرات أسبوعياً)", "value": "4", "points": 7},
            {"text": "رياضي محترف/متدرب يومياً", "value": "5", "points": 10}
        ]
    ),
    AssessmentQuestion(
        question="ما هي مدة تمارينك في اليوم؟",
        category="strength",
        options=[
            {"text": "لا أتمرن", "value": "1", "points": 1},
            {"text": "15-30 دقيقة", "value": "2", "points": 3},
            {"text": "30-45 دقيقة", "value": "3", "points": 5},
            {"text": "45-60 دقيقة", "value": "4", "points": 7},
            {"text": "أكثر من ساعة", "value": "5", "points": 10}
        ]
    ),
    AssessmentQuestion(
        question="ما هو نوع تمارينك الأساسية؟",
        category="strength",
        options=[
            {"text": "لا أتمرن", "value": "1", "points": 1},
            {"text": "تمارين خفيفة (مشي، تمدد)", "value": "2", "points": 3},
            {"text": "تمارين متوسطة (أثقال خفيفة)", "value": "3", "points": 5},
            {"text": "تمارين شاقة (رفع أثقال)", "value": "4", "points": 7},
            {"text": "تمارين متخصصة (رياضة محددة)", "value": "5", "points": 10}
        ]
    ),
    
    # 🧠 الذكاء (3 أسئلة)
    AssessmentQuestion(
        question="كم كتاباً تقرأ شهرياً؟",
        category="intelligence",
        options=[
            {"text": "لا أقرأ", "value": "1", "points": 1},
            {"text": "كتاب واحد أو أقل", "value": "2", "points": 3},
            {"text": "2-3 كتب", "value": "3", "points": 5},
            {"text": "4-5 كتب", "value": "4", "points": 7},
            {"text": "أكثر من 5 كتب", "value": "5", "points": 10}
        ]
    ),
    AssessmentQuestion(
        question="ما هي مصادر التعلم الرئيسية لديك؟",
        category="intelligence",
        options=[
            {"text": "لا أتعلم بشكل منتظم", "value": "1", "points": 1},
            {"text": "وسائل التواصل الاجتماعي", "value": "2", "points": 3},
            {"text": "كورسات قصيرة ومقالات", "value": "3", "points": 5},
            {"text": "كتب وكورسات متخصصة", "value": "4", "points": 7},
            {"text": "دراسة أكاديمية متقدمة", "value": "5", "points": 10}
        ]
    ),
    AssessmentQuestion(
        question="كم ساعة تتعلم فيها أسبوعياً؟",
        category="intelligence",
        options=[
            {"text": "أقل من ساعة", "value": "1", "points": 1},
            {"text": "1-3 ساعات", "value": "2", "points": 3},
            {"text": "4-6 ساعات", "value": "3", "points": 5},
            {"text": "7-10 ساعات", "value": "4", "points": 7},
            {"text": "أكثر من 10 ساعات", "value": "5", "points": 10}
        ]
    ),
    
    # ❤️ الصحة (3 أسئلة)
    AssessmentQuestion(
        question="ما هي عاداتك الصحية اليومية؟",
        category="vitality",
        options=[
            {"text": "لا أهتم كثيراً", "value": "1", "points": 1},
            {"text": "نوم منتظم فقط", "value": "2", "points": 3},
            {"text": "نوم + تغذية جيدة", "value": "3", "points": 5},
            {"text": "نوم + تغذية + تمرين", "value": "4", "points": 7},
            {"text": "نظام صحي متكامل", "value": "5", "points": 10}
        ]
    ),
    AssessmentQuestion(
        question="كم ساعة تنام يومياً؟",
        category="vitality",
        options=[
            {"text": "أقل من 5 ساعات", "value": "1", "points": 1},
            {"text": "5-6 ساعات", "value": "2", "points": 3},
            {"text": "6-7 ساعات", "value": "3", "points": 5},
            {"text": "7-8 ساعات", "value": "4", "points": 7},
            {"text": "8+ ساعات ونوم عميق", "value": "5", "points": 10}
        ]
    ),
    AssessmentQuestion(
        question="كيف تقيم نظامك الغذائي؟",
        category="vitality",
        options=[
            {"text": "غير صحي وغير منتظم", "value": "1", "points": 1},
            {"text": "محاولة أكل صحي أحياناً", "value": "2", "points": 3},
            {"text": "نظام غذائي متوازن", "value": "3", "points": 5},
            {"text": "نظام غذائي صحي منتظم", "value": "4", "points": 7},
            {"text": "نظام غذائي مخصص ومتابعة", "value": "5", "points": 10}
        ]
    ),
    
    # 🤝 المرونة (3 أسئلة)
    AssessmentQuestion(
        question="كيف هي علاقاتك الاجتماعية؟",
        category="agility",
        options=[
            {"text": "منعزل ولا أحب الاجتماعات", "value": "1", "points": 1},
            {"text": "علاقات محدودة مع المقربين", "value": "2", "points": 3},
            {"text": "علاقات جيدة مع مجموعة معينة", "value": "3", "points": 5},
            {"text": "شبكة علاقات واسعة", "value": "4", "points": 7},
            {"text": "قائد اجتماعي وعلاقات متنوعة", "value": "5", "points": 10}
        ]
    ),
    AssessmentQuestion(
        question="كم عدد الأنشطة الاجتماعية الشهرية؟",
        category="agility",
        options=[
            {"text": "لا أشارك", "value": "1", "points": 1},
            {"text": "1-2 نشاط", "value": "2", "points": 3},
            {"text": "3-4 أنشطة", "value": "3", "points": 5},
            {"text": "5-6 أنشطة", "value": "4", "points": 7},
            {"text": "أكثر من 6 أنشطة", "value": "5", "points": 10}
        ]
    ),
    AssessmentQuestion(
        question="كيف تتعامل مع النزاعات؟",
        category="agility",
        options=[
            {"text": "أتهرب منها", "value": "1", "points": 1},
            {"text": "أواجهها بصعوبة", "value": "2", "points": 3},
            {"text": "أتعامل معها بشكل مقبول", "value": "3", "points": 5},
            {"text": "أحلها ببراعة", "value": "4", "points": 7},
            {"text": "أمنع حدوثها من الأساس", "value": "5", "points": 10}
        ]
    ),
    
    # 🕌 الإدراك (3 أسئلة)
    AssessmentQuestion(
        question="ما هو مستوى التزامك الديني/الفكري؟",
        category="perception",
        options=[
            {"text": "غير ملتزم", "value": "1", "points": 1},
            {"text": "ملتزم جزئياً", "value": "2", "points": 3},
            {"text": "ملتزم بشكل جيد", "value": "3", "points": 5},
            {"text": "ملتزم جداً ومتابع", "value": "4", "points": 7},
            {"text": "مثال يُحتذى به وقائد", "value": "5", "points": 10}
        ]
    ),
    AssessmentQuestion(
        question="كم وقت تخصصه للعبادات/التفكر؟",
        category="perception",
        options=[
            {"text": "أقل من ساعة أسبوعياً", "value": "1", "points": 1},
            {"text": "1-3 ساعات أسبوعياً", "value": "2", "points": 3},
            {"text": "4-6 ساعات أسبوعياً", "value": "3", "points": 5},
            {"text": "7-10 ساعات أسبوعياً", "value": "4", "points": 7},
            {"text": "أكثر من 10 ساعات أسبوعياً", "value": "5", "points": 10}
        ]
    ),
    AssessmentQuestion(
        question="ما مدى تأثير الجانب الروحي على حياتك؟",
        category="perception",
        options=[
            {"text": "تأثير ضعيف", "value": "1", "points": 1},
            {"text": "تأثير محدود", "value": "2", "points": 3},
            {"text": "تأثير واضح", "value": "3", "points": 5},
            {"text": "تأثير قوي", "value": "4", "points": 7},
            {"text": "تأثير كلي ومحرك أساسي", "value": "5", "points": 10}
        ]
    ),
    
    # 💸 الحرية (3 أسئلة)
    AssessmentQuestion(
        question="كيف تتعامل مع أمورك المالية؟",
        category="freedom",
        options=[
            {"text": "إدارة سيئة ودائماً أعاني", "value": "1", "points": 1},
            {"text": "أحاول التحكم لكن بصعوبة", "value": "2", "points": 3},
            {"text": "تخطيط مالي جيد", "value": "3", "points": 5},
            {"text": "استثمارات صغيرة وإدارة ممتازة", "value": "4", "points": 7},
            {"text": "مستقل مادياً واستثمارات ناجحة", "value": "5", "points": 10}
        ]
    ),
    AssessmentQuestion(
        question="كم من دخلك تدخر؟",
        category="freedom",
        options=[
            {"text": "لا أدخر", "value": "1", "points": 1},
            {"text": "أقل من 10%", "value": "2", "points": 3},
            {"text": "10-20%", "value": "3", "points": 5},
            {"text": "20-30%", "value": "4", "points": 7},
            {"text": "أكثر من 30%", "value": "5", "points": 10}
        ]
    ),
    AssessmentQuestion(
        question="ما هي خططك المالية المستقبلية؟",
        category="freedom",
        options=[
            {"text": "لا يوجد لدي خطط", "value": "1", "points": 1},
            {"text": "خطط بسيطة قصيرة المدى", "value": "2", "points": 3},
            {"text": "خطط واضحة قصيرة ومتوسطة", "value": "3", "points": 5},
            {"text": "خطط متوسطة وطويلة المدى", "value": "4", "points": 7},
            {"text": "خطط استراتيجية شاملة", "value": "5", "points": 10}
        ]
    )
]

# ============ نظام العقوبات العشوائي ============

class PenaltySystem:
    """نظام العقوبات المطور - يدعم العقوبات النسبية والعشوائية"""
    
    @staticmethod
    def generate_penalty(task_level: int, task_type: str, player_level: int, completion_pct: float = 0.0) -> Dict:
        """
        توليد عقوبة عشوائية ونسبية بناءً على نسبة الإنجاز.
        - completion_pct: نسبة ما أنجزه اللاعب (0.0 إلى 1.0).
        """
        
        # 1. حساب "نسبة التقصير" (Unmet Percentage)
        unmet_pct = max(0.0, 1.0 - completion_pct)
        
        # إذا كان التقصير صفراً (أنجز المهمة كاملة)، لا توجد عقوبة
        if unmet_pct <= 0:
            return {"type": "none", "description": "نجوت من العقوبة!"}

        # 2. تحديد "قيمة القاعدة" بناءً على مستوى المهمة
        if task_level <= 15:
            base_xp_loss = 100
            base_coin_loss = 50
            base_real_money = 10
        elif task_level <= 50:
            base_xp_loss = 500
            base_coin_loss = 250
            base_real_money = 30
        else:
            base_xp_loss = 1500
            base_coin_loss = 1000
            base_real_money = 100

        # 3. اختيار نوع العقوبة عشوائياً (كما طلبت: XP، عملات، تبرع واقعي)
        penalty_type = random.choice(["xp_loss", "coin_loss", "real_donation"])
        
        # 4. بناء العقوبة بناءً على النوع ونسبة التقصير
        if penalty_type == "xp_loss":
            final_loss = int(base_xp_loss * unmet_pct)
            return {
                "type": "xp_loss",
                "description": f"📉 فشل في الانضباط: خصم {final_loss} XP من جانب {task_type}.",
                "amount": final_loss,
                "currency": "xp",
                "category": task_type,
                "requires_proof": False
            }
        
        elif penalty_type == "coin_loss":
            final_loss = int(base_coin_loss * unmet_pct)
            return {
                "type": "coin_loss",
                "description": f"💸 غرامة النظام: خصم {final_loss} عملة ذهبية من رصيدك.",
                "amount": final_loss,
                "currency": "coins",
                "requires_proof": False
            }
        
        else: # real_donation (التبرع الحقيقي)
            final_amount = int(base_real_money * unmet_pct)
            # التأكد من وجود حد أدنى للتبرع ليكون ذا قيمة (مثلاً 5 ريال)
            final_amount = max(5, final_amount) 
            
            return {
                "type": "real_donation",
                "description": f"🚨 عقوبة واقعية: يجب عليك التبرع بمبلغ {final_amount} ريال لجهة خيرية ورفع الإثبات.",
                "amount": final_amount,
                "currency": "SAR",
                "requires_proof": True,
                "note": "العقوبة مرتبطة بالواقع لتعزيز الانضباط."
            }

    @staticmethod
    def get_penalty_for_portal(portal_level: str, participants: int) -> Dict:
        """عقوبة البوابات (تظل جماعية وثابتة لضمان رهبة الفشل)"""
        level_values = {"E": 1, "D": 2, "C": 4, "B": 8, "A": 15, "S": 30, "SS": 60}
        base_multiplier = level_values.get(portal_level, 1)
        
        penalty_type = random.choice(["xp_loss_all", "coin_loss_all"])
        
        if penalty_type == "xp_loss_all":
            amount = base_multiplier * 50
            return {
                "type": "xp_loss_all",
                "description": f"📉 انكسار الختم: خصم {amount} XP من جميع اللاعبين!",
                "amount": amount,
                "currency": "xp"
            }
        else:
            amount = base_multiplier * 25
            return {
                "type": "coin_loss_all",
                "description": f"💸 خسارة فادحة: غرامة {amount} عملة على جميع اللاعبين!",
                "amount": amount,
                "currency": "coins"
            }
# ============ دوال مساعدة ============

def get_questions_for_category(category: str, count: int = 3) -> List[AssessmentQuestion]:
    """الحصول على أسئلة عشوائية لفئة معينة"""
    category_questions = [q for q in ASSESSMENT_QUESTIONS if q.category == category]
    return random.sample(category_questions, min(count, len(category_questions)))

def get_all_assessment_questions() -> List[AssessmentQuestion]:
    """الحصول على جميع أسئلة الاختبار (3 لكل فئة)"""
    selected_questions = []
    categories = ["strength", "intelligence", "vitality", "agility", "perception", "freedom"]
    
    for category in categories:
        selected_questions.extend(get_questions_for_category(category, 3))
    
    random.shuffle(selected_questions)
    return selected_questions

def calculate_level_from_points(total_points: int) -> Tuple[int, int]:
    """حساب المستوى والخبرة المتبقية من النقاط (للتوافق مع الكود القديم)"""
    level, current_xp, xp_needed = calculate_level_120(total_points)
    return level, current_xp

# ============ اختبار النظام ============

# ============ نظام المستويات 1-120 مع تقدم سهل في البداية ويصعب مع الوقت ============

import math

MAX_LEVEL = 120  # الحد الأقصى للمستوى
TOTAL_DAYS = 3650  # 10 سنوات بالأيام (10 × 365)

def calculate_level_progressive(total_xp: int) -> Tuple[int, int, int]:
    """
    حساب المستوى (1-120) بناءً على نظام سهل في البداية ويصعب مع الوقت
    
    نظام تصاعدي: 
    - أول 50 مستوى: سهل (يصعد بسرعة)
    - من 50 إلى 100: متوسط (يتطلب جهداً)
    - من 100 إلى 120: صعب جداً (يتطلب تفانياً)
    
    معادلة: مستوى = 120 × (النقاط ^ 0.7) / (1000000 ^ 0.7)
    هذا يجعل التقدم سهلًا في البداية ويصعب مع الوقت
    """
    if total_xp <= 0:
        return 1, 0, 0
    
    # إجمالي XP المطلوب للوصول للمستوى 120
    total_xp_for_max = 500000  # 500,000 XP للوصول للمستوى 120
    
    # حساب المستوى باستخدام دالة أسية تجعل التقدم سهلًا أولاً ثم يصعب
    # معادلة: المستوى = 120 * (1 - (1 / (1 + (النقاط / 50000))))
    # هذا يعطي منحنى تصاعدي سهل في البداية ويصعب مع الوقت
    
    level = 120 * (1 - math.exp(-total_xp / 100000))
    level = max(1, min(MAX_LEVEL, int(level)))
    
    # حساب الـ XP المطلوب للوصول لهذا المستوى
    if level == MAX_LEVEL:
        xp_for_current_level = total_xp_for_max
        xp_for_next_level = total_xp_for_max
    else:
        # عكس المعادلة لحساب XP المطلوب لهذا المستوى
        xp_for_current_level = int(-100000 * math.log(1 - (level / 120)))
        xp_for_next_level = int(-100000 * math.log(1 - ((level + 1) / 120)))
    
    # XP المتبقي للوصول للمستوى التالي
    xp_needed = max(0, xp_for_next_level - xp_for_current_level)
    
    # الـ XP الحالي في هذا المستوى
    current_xp_in_level = total_xp - xp_for_current_level
    
    return level, current_xp_in_level, xp_needed

def calculate_daily_xp_target() -> float:
    """حساب الـ XP اليومي المطلوب للوصول للمستوى 120 في 10 سنوات"""
    total_xp_needed = 500000  # 500,000 XP للوصول للمستوى 120 في 10 سنوات
    daily_xp = total_xp_needed / TOTAL_DAYS
    return daily_xp  # ≈ 137 XP/يوم

def calculate_level_from_points(total_points: int) -> Tuple[int, int]:
    """
    دالة توافقية للكود القديم
    تحول النقاط إلى مستوى (1-120)
    """
    level, current_xp, xp_needed = calculate_level_progressive(total_points)
    return level, current_xp

if __name__ == "__main__":
    print("✅ نظام الأسئلة والعقوبات جاهز")
    print(f"عدد الأسئلة: {len(ASSESSMENT_QUESTIONS)}")
    print(f"الفئات: {set(q.category for q in ASSESSMENT_QUESTIONS)}")
    
    # اختبار نظام العقوبات
    penalty_system = PenaltySystem()
    
    print("\n🎯 أمثلة على العقوبات:")
    for level in [5, 15, 35, 65]:
        penalty = penalty_system.generate_penalty(level, "strength", 10)
        print(f"مهمة مستوى {level}: {penalty['description']}")