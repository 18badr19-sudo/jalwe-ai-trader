# استخدام صورة بايثون رسمية خفيفة
FROM python:3.10-slim

# تحديد مجلد العمل داخل السيرفر
WORKDIR /app

# تثبيت متطلبات النظام الأساسية إن وجدت
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات أولاً لتحسين التخزين المؤقت (Caching)
COPY requirements.txt .

# تثبيت مكتبات بايثون المطلوبة
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع إلى مجلد العمل
COPY . .

# الأمر الافتراضي لتشغيل البوت فور إقلاع الحاوية
CMD ["python", "main.py"]