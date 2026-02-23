# 1. استخدام نسخة بايثون مستقرة وخفيفة (تدعم ARM و x86)
FROM python:3.9-slim

# 2. إعداد المتغيرات البيئية لضمان سرعة الأداء وتثبيت التوقيت
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Africa/Cairo

WORKDIR /app

# 3. تثبيت التبعيات النظامية الضرورية فقط
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 4. نسخ ملف المتطلبات وتثبيت المكتبات (هذه الخطوة منفصلة لتسريع البناء لاحقاً)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. نسخ كافة ملفات المشروع (بما فيها المحرك والمكتبات الجديدة)
# تأكد أن ملف .dockerignore يتجاهل المجلدات غير الضرورية مثل __pycache__
COPY . .

# 6. إنشاء مجلدات البيانات والسجلات لضمان عدم حدوث أخطاء Permission
RUN mkdir -p /app/logs /app/data /app/assets

# 7. تشغيل البوت
CMD ["python", "bot.py"]