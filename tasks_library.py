# tasks_library.py

VITALITY_TASKS = {
    "health_teeth": {
        "title": "🪥 غسيل الأسنان",
        "description": "الحفاظ على نظافة الفم والأسنان.",
        "type": "buttons",
        "category": "vitality",  # ✅ تمت الإضافة (ضروري جداً)
        "exertion": "low",
        "expect_young": "both", 
        "expect_senior": "once",
        "xp_reward": 40,
        "options": [
            {"label": "صباحاً ومساءً", "value": "both", "xp_pct": 1.0},
            {"label": "مرة واحدة فقط", "value": "once", "xp_pct": 0.5}
        ]
    },
    "health_caffeine": {
        "title": "☕ التحكم في الكافيين",
        "description": "موازنة الشاي والقهوة (الحد الأقصى 4 وحدات).",
        "type": "modal_dual",
        "category": "vitality", # ✅ تمت الإضافة
        "exertion": "low",
        "xp_reward": 50,
        "max_units": 4
    },
    "health_water": {
        "title": "💧 شرب الماء",
        "description": "ترطيب الجسم طوال اليوم.",
        "type": "modal_numeric",
        "category": "vitality", # ✅ تمت الإضافة
        "unit": "لتر", 
        "exertion": "low",
        "xp_reward": 60,
        "targets": {"young": 3.0, "senior": 2.0} 
    },
    "health_sleep_duration": {
        "title": "😴 ساعات النوم",
        "description": "النوم الكافي لاستعادة الطاقة.",
        "type": "modal_numeric",
        "category": "vitality", # ✅ تمت الإضافة
        "unit": "ساعة", 
        "exertion": "low",
        "xp_reward": 80,
        "targets": {"young": 7.0, "senior": 6.0}
    },
    "health_sun": {
        "title": "☀️ التعرض للشمس",
        "description": "الحصول على فيتامين د لمدة 15 دقيقة.",
        "type": "confirm",
        "category": "vitality", # ✅ تمت الإضافة
        "exertion": "low",
        "xp_reward": 30
    },
    "health_nails": {
        "title": "✂️ قص الأظافر",
        "description": "سنة النظافة (يوم الجمعة).",
        "type": "confirm",
        "category": "vitality", # ✅ تمت الإضافة
        "exertion": "low",
        "schedule": "friday",
        "xp_reward": 40
    },
    "health_haircut": {
        "title": "💈 حلاقة الشعر",
        "description": "الاهتمام بالمظهر (أول الشهر).",
        "type": "confirm",
        "category": "vitality", # ✅ تمت الإضافة
        "exertion": "low",
        "gender": "male",
        "schedule": "first_of_month",
        "xp_reward": 50
    },
    "health_sleep_time": {
        "title": "🌙 موعد النوم",
        "description": "الانضباط في وقت الذهاب للفراش (ليلة أمس).",
        "type": "select",
        "category": "vitality", # ✅ تمت الإضافة
        "exertion": "low",
        "xp_reward": 70,
        "options": [
            {"label": "قبل منتصف الليل", "value": "early", "xp_pct": 1.0},
            {"label": "في منتصف الليل", "value": "on_time", "xp_pct": 0.8},
            {"label": "بعد منتصف الليل", "value": "late", "xp_pct": 0.5},
            {"label": "إلى الصباح ⚠️", "value": "too_late", "xp_pct": 0.0}
        ]
    },
    "health_shower": {
        "title": "🚿 الاستحمام",
        "description": "النظافة الشخصية اليومية.",
        "type": "confirm",
        "category": "vitality", # ✅ تمت الإضافة
        "exertion": "medium",
        "frequency_young": "daily", 
        "frequency_senior": "weekly",
        "schedule_senior": "friday", 
        "xp_reward": 40
    }
}

FREEDOM_TASKS = {
    "fin_monthly_saving": {
        "title": "💰 ادخار الاستثمار",
        "description": "اقتطاع جزء من الدخل للادخار أو الاستثمار (بداية الشهر).",
        "type": "modal_numeric",
        "unit": "ريال",
        "exertion": "low",
        "schedule": "first_of_month", # تظهر فقط يوم 1 في الشهر
        "xp_reward": 200, # مكافأة كبيرة لأنها شهرية وتتطلب انضباطاً عالياً
        "category": "freedom"
    },
    "fin_expense_logging": {
        "title": "📝 تسجيل المصاريف",
        "description": "تدوين كافة مصاريف اليوم وتقسيمها (سكن، طعام، فواتير...).",
        "type": "confirm",
        "exertion": "low",
        "xp_reward": 50,
        "category": "freedom"
    },
    "fin_avoid_junk": {
        "title": "🚫 تجنب شراء التسالي",
        "description": "توفير المال و الحفاظ على الصحه بتجنب التسالي و المواد الحافظه و الكافيين.",
        "type": "confirm",
        "exertion": "low",
        "bxp_reward": 60,
        "category": "freedom"
    },
    "work_attendance": {
        "title": "🏢 الذهاب للعمل/الدراسة",
        "description": "الانضباط في الحضور وأداء ساعات العمل الرسمية.",
        "type": "confirm",
        "is_work": True, # وسم أيام العمل (تختفي في الإجازة)
        "exertion": "high",
        "xp_reward": 100,
        "category": "freedom"
    }
}

STRENGTH_TASKS = {
    "str_gym_session": {
        "title": "🏋️ جلسة التدريب الاحترافية (Gym)",
        "description": "ذهاب للنادي وأداء تمارين المقاومة الشاملة.",
        "type": "confirm",
        "category": "strength",
        "exertion": "high",
        "gender": "male",
        "min_rank": "C", # تظهر من رتبة C فما فوق
        "xp_reward": 150
    },
    "str_home_workout": {
        "title": "🏠 تمارين القوة المنزلية",
        "description": "تمارين بوزن الجسم (ضغط، بطن، عقلة) لمدة 30 دقيقة.",
        "type": "confirm",
        "category": "strength",
        "exertion": "medium",
        # تظهر للنساء دائماً، وللرجال في الرتب الضعيفة E و D
        "xp_reward": 80
    },
    "str_walking": {
        "title": "🚶 مهمة المشي السريع",
        "description": "المشي المتواصل لمدة ساعة (60 دقيقة) لتعزيز التحمل.",
        "type": "modal_numeric",
        "unit": "دقيقة",
        "category": "strength",
        "exertion": "medium",
        "targets": {"young": 60, "senior": 30}, # الشاب ساعة، الكبير نصف ساعة
        "xp_reward": 70
    }
}
INTELLIGENCE_TASKS = {
    "int_reading": {
        "title": "📖 ورد القراءة اليومي",
        "description": "قراءة في كتاب غير روائي (تطوير ذات، علم، تاريخ).",
        "type": "modal_numeric",
        "unit": "دقيقة",
        "category": "intelligence",
        # التوقع يتدرج حسب الرتبة (Rank Scaling)
        "targets_by_rank": {
            "E": 15, "D": 20, "C": 30, "B": 45, "A": 60, "S": 90, "SS": 120
        },
        "xp_reward": 80
    },
    "int_anki_summary": {
        "title": "📝 التلخيص النشط (Anki)",
        "description": "تحويل ما تعلمته اليوم إلى أسئلة وأجوبة في تطبيق Anki.",
        "type": "confirm",
        "category": "intelligence",
        "xp_reward": 50
    },
    "int_review": {
        "title": "🔄 المراجعة المتباعدة",
        "description": "مراجعة المعلومات السابقة لضمان عدم النسيان.",
        "type": "confirm",
        "category": "intelligence",
        "xp_reward": 40
    },
    "int_teaching": {
        "title": "🗣️ شرح المفهوم",
        "description": "اشرح شيئاً تعلمته اليوم لشخص آخر (صديق، قريب، زميل).",
        "type": "confirm",
        "category": "intelligence",
        "xp_reward": 60
    }
}

AGILITY_TASKS = {
    "soc_friend_contact": {
        "title": "🤝 صلة الأصدقاء",
        "description": "التواصل مع صديق لتعزيز العلاقة.",
        "type": "buttons",
        "category": "agility",
        "options": [
            {"label": "زيارة ميدانية 🏠", "value": "visit", "xp_pct": 1.0},
            {"label": "اتصال هادفي 📞", "value": "call", "xp_pct": 0.7},
            {"label": "رسالة نصية 💬", "value": "message", "xp_pct": 0.4}
        ],
        "xp_reward": 50
    },
    "soc_relative_contact": {
        "title": "🕌 صلة الرحم الأسبوعية",
        "description": "التواصل مع الأقارب (تظهر في أيام الإجازة فقط).",
        "type": "buttons",
        "category": "agility",
        "is_off_day_only": True, # وسم خاص لأيام الإجازة
        "options": [
            {"label": "زيارة 🏠", "value": "visit", "xp_pct": 1.0},
            {"label": "اتصال 📞", "value": "call", "xp_pct": 0.7},
            {"label": "رسالة 💬", "value": "message", "xp_pct": 0.4}
        ],
        "xp_reward": 100 # مكافأة أعلى لأنها أسبوعية
    },
    "soc_stranger_help": {
        "title": "🌟 صناعة المعروف",
        "description": "مساعدة شخص غريب دون انتظار مقابل.",
        "type": "confirm",
        "category": "agility",
        "xp_reward": 70
    },
    "soc_problem_solver": {
        "title": "🛠️ مبادرة الإصلاح",
        "description": "حل مشكلة في محيطك (المنزل، العمل، الأصدقاء).",
        "type": "confirm",
        "category": "agility",
        "xp_reward": 80
    }
}

PERCEPTION_TASKS = {
    # === 🌙 الصيام (يعتمد على التاريخ الهجري) ===
    "rel_ramadan": {
        "title": "🌙 صيام رمضان",
        "description": "فريضـة الصيام.",
        "type": "confirm",
        "category": "perception",
        "exertion": "medium",
        "is_religious": True, # يُحذف في العذر الشرعي
        "hijri_month": 9, # يظهر طوال شهر رمضان
        "xp_reward": 300
    },
    "rel_ashura": {
        "title": "🕌 صيام عاشوراء",
        "description": "صيام يوم عاشوراء (كفارة سنة).",
        "type": "confirm",
        "category": "perception",
        "exertion": "medium",
        "is_religious": True,
        "hijri_month": 1, "hijri_day": 10,
        "xp_reward": 200
    },
    "rel_white_days": {
        "title": "🌕 صيام الأيام البيض",
        "description": "صيام 13، 14، 15 من الشهر الهجري.",
        "type": "confirm",
        "category": "perception",
        "exertion": "medium",
        "is_religious": True,
        "hijri_days": [13, 14, 15],
        "exclude_months": [9], # لا تظهر في رمضان
        "xp_reward": 150
    },
    "rel_mon_thu": {
        "title": "📅 صيام السنة (الإثنين/الخميس)",
        "description": "صيام التطوع الأسبوعي.",
        "type": "confirm",
        "category": "perception",
        "exertion": "medium",
        "is_religious": True,
        "weekdays": [0, 3], # 0=الإثنين, 3=الخميس
        "exclude_months": [9], # لا تظهر في رمضان
        "xp_reward": 100
    },

    # === 🕌 الصلوات (مدمجة: فرض + سنة + أذكار) ===
    # تم دمج الفرض والسنة والختم في قائمة واحدة لتسهيل الإدخال
    "rel_fajr": {
        "title": "🌌 صلاة الفجر",
        "description": "تسجيل أداء صلاة الفجر وسنتها وأذكارها.",
        "type": "select",
        "category": "perception",
        "is_religious": True,
        "xp_reward": 200,
        "options": [
            {"label": "جماعة/وقت + سنة + أذكار (كاملة)", "value": "perfect", "xp_pct": 1.0},
            {"label": "الفرض جماعه + السنة فقط", "value": "sunnah", "xp_pct": 0.9},
            {"label": "الفرض جماعه + الاذكار", "value": "fard+1", "xp_pct": 0.8},
            {"label": "الفرض جماعه", "value": "fard", "xp_pct": 0.7},
            {"label": "الفرض منفرد + اذكار + سنه", "value": "perfect-1", "xp_pct": 0.5},
            {"label": "الفرض منفرد + السنة فقط", "value": "sunnah-1", "xp_pct": 0.4},
            {"label": "الفرض منفرد + اذكار", "value": "fard-1", "xp_pct": 0.3},
            {"label": "الفرض منفرد", "value": "fard-2", "xp_pct": 0.2},
            {"label": "قضاء / متأخر ⚠️", "value": "late", "xp_pct": 0.1}
        ]
    },
    "rel_duha": {
        "title": "☀️ صلاة الضحى",
        "description": "صلاة الأوابين (ركعتان على الأقل).",
        "type": "confirm",
        "category": "perception",
        "is_religious": True,
        "xp_reward": 40
    },
    "rel_dhuhr": {
        "title": "☀️ صلاة الظهر/الجمعة",
        "description": "تسجيل أداء الصلاة (تتغير تلقائياً يوم الجمعة).",
        "type": "select",
        "category": "perception",
        "is_religious": True,
        "xp_reward": 80,
        "options": [
            {"label": "جماعة/وقت + سنة + أذكار (كاملة)", "value": "perfect", "xp_pct": 1.0},
            {"label": "الفرض جماعه + السنة فقط", "value": "sunnah", "xp_pct": 0.9},
            {"label": "الفرض جماعه + الاذكار", "value": "fard+1", "xp_pct": 0.8},
            {"label": "الفرض جماعه", "value": "fard", "xp_pct": 0.7},
            {"label": "الفرض منفرد + اذكار + سنه", "value": "perfect-1", "xp_pct": 0.5},
            {"label": "الفرض منفرد + السنة فقط", "value": "sunnah-1", "xp_pct": 0.4},
            {"label": "الفرض منفرد + اذكار", "value": "fard-1", "xp_pct": 0.3},
            {"label": "الفرض منفرد", "value": "fard-2", "xp_pct": 0.2},
            {"label": "قضاء / متأخر ⚠️", "value": "late", "xp_pct": 0.1}
        ]
    },
    "rel_asr": {
        "title": "🌤️ صلاة العصر",
        "description": "الصلاة الوسطى.",
        "type": "select",
        "category": "perception",
        "is_religious": True,
        "xp_reward": 80,
        "options": [
            {"label": "جماعة/وقت + أذكار", "value": "perfect", "xp_pct": 1.0},
            {"label": "الفرض جماعه", "value": "fard", "xp_pct": 0.7},
            {"label": "الفرض منفرد + اذكار", "value": "fard-1", "xp_pct": 0.5},
            {"label": "الفرض منفرد", "value": "fard-2", "xp_pct": 0.3},
            {"label": "متأخر ⚠️", "value": "late", "xp_pct": 0.2}
        ]
    },
    "rel_maghrib": {
        "title": "🌇 صلاة المغرب",
        "description": "تسجيل أداء صلاة المغرب.",
        "type": "select",
        "category": "perception",
        "is_religious": True,
        "xp_reward": 80,
        "options": [
            {"label": "جماعة/وقت + سنة + أذكار (كاملة)", "value": "perfect", "xp_pct": 1.0},
            {"label": "الفرض جماعه + السنة فقط", "value": "sunnah", "xp_pct": 0.9},
            {"label": "الفرض جماعه + الاذكار", "value": "fard+1", "xp_pct": 0.8},
            {"label": "الفرض جماعه", "value": "fard", "xp_pct": 0.7},
            {"label": "الفرض منفرد + اذكار + سنه", "value": "perfect-1", "xp_pct": 0.5},
            {"label": "الفرض منفرد + السنة فقط", "value": "sunnah-1", "xp_pct": 0.4},
            {"label": "الفرض منفرد + اذكار", "value": "fard-1", "xp_pct": 0.3},
            {"label": "الفرض منفرد", "value": "fard-2", "xp_pct": 0.2},
            {"label": "قضاء / متأخر ⚠️", "value": "late", "xp_pct": 0.1}
        ]
    },
    "rel_isha": {
        "title": "🌌 صلاة العشاء",
        "description": "تسجيل أداء صلاة العشاء.",
        "type": "select",
        "category": "perception",
        "is_religious": True,
        "xp_reward": 80,
        "options": [
            {"label": "جماعة/وقت + سنة + أذكار (كاملة)", "value": "perfect", "xp_pct": 1.0},
            {"label": "الفرض جماعه + السنة فقط", "value": "sunnah", "xp_pct": 0.9},
            {"label": "الفرض جماعه + الاذكار", "value": "fard+1", "xp_pct": 0.8},
            {"label": "الفرض جماعه", "value": "fard", "xp_pct": 0.7},
            {"label": "الفرض منفرد + اذكار + سنه", "value": "perfect-1", "xp_pct": 0.5},
            {"label": "الفرض منفرد + السنة فقط", "value": "sunnah-1", "xp_pct": 0.4},
            {"label": "الفرض منفرد + اذكار", "value": "fard-1", "xp_pct": 0.3},
            {"label": "الفرض منفرد", "value": "fard-2", "xp_pct": 0.2},
            {"label": "قضاء / متأخر ⚠️", "value": "late", "xp_pct": 0.1}
        ]
    },
    
    # === 🌟 النوافل والعبادات (Ranks & Habits) ===
    "rel_qiyam": {
        "title": "🌃 قيام الليل",
        "description": "ركعتان على الأقل في جوف الليل.",
        "type": "confirm",
        "category": "perception",
        "is_religious": True,
        "min_rank": "B", # للرتب العالية فقط (B, A, S)
        "xp_reward": 150
    },
    "rel_witr": {
        "title": "🤲 صلاة الوتر",
        "description": "ركعة واحدة على الأقل قبل النوم.",
        "type": "confirm",
        "category": "perception",
        "is_religious": True,
        "xp_reward": 50
    },
    "rel_quran": {
        "title": "📖 الورد القرآني",
        "description": "تلاوة ورد يومي من القرآن الكريم.",
        "type": "modal_numeric",
        "unit": "صفحة",
        "category": "perception",
        "is_religious": True, # تخطي في العذر (أو يمكن إبقاؤه للقراءة من الهاتف)
        "targets_by_rank": {"E": 2, "D": 4, "C": 10, "B": 20, "A": 30, "S": 60},
        "xp_reward": 90
    },
    "rel_istighfar": {
        "title": "📿 الاستغفار (100 مرة)",
        "description": "ورد الاستغفار اليومي.",
        "type": "confirm",
        "category": "perception",
        "xp_reward": 40
    },
    "rel_adhkar_morning": {
        "title": "🌅 أذكار الصباح",
        "description": "بداية اليوم بذكر الله.",
        "type": "confirm",
        "category": "perception",
        "xp_reward": 40
    },
    "rel_adhkar_evening": {
        "title": "🌆 أذكار المساء",
        "description": "حصن المسلم في المساء.",
        "type": "confirm",
        "category": "perception",
        "xp_reward": 40
    },
    "rel_adhkar_sleep": {
        "title": "🛌 أذكار النوم",
        "description": "ختام اليوم بذكر الله.",
        "type": "confirm",
        "category": "perception",
        "xp_reward": 30
    },
    "rel_charity": {
        "title": "🎁 الصدقة الأسبوعية",
        "description": "التصدق ولو بالقليل (يوم الجمعة).",
        "type": "confirm",
        "category": "perception",
        "schedule": "friday",
        "xp_reward": 100
    },
    "rel_bad_words": {
        "title": "🤐 طهارة اللسان",
        "description": "هل امتنعت عن الكلام السيء والغيبة اليوم؟",
        "type": "confirm",
        "category": "perception",
        "xp_reward": 60
    }
}
# تحديث السطر النهائي لدمج الكل
ALL_TASKS = {**VITALITY_TASKS, **FREEDOM_TASKS, **STRENGTH_TASKS, **INTELLIGENCE_TASKS, **AGILITY_TASKS, **PERCEPTION_TASKS}