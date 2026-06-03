# 🎬 Video Downloader API

واجهة خلفية (Backend) لتنزيل الفيديوهات من فيسبوك ومنصات أخرى  
مبنية بـ **FastAPI + yt-dlp**

---

## 📁 هيكل الملفات

```
├── main.py            ← الخادم الرئيسي
├── requirements.txt   ← المكتبات
├── Dockerfile         ← للنشر عبر Docker
└── README.md
```

---

## ⚡ التشغيل المحلي

### 1. تثبيت المتطلبات
```bash
pip install -r requirements.txt
```

> ⚠️ تأكد من تثبيت **ffmpeg** على جهازك:
> - macOS: `brew install ffmpeg`
> - Ubuntu/Debian: `sudo apt install ffmpeg`
> - Windows: [تنزيل من ffmpeg.org](https://ffmpeg.org/download.html)

### 2. تشغيل الخادم
```bash
uvicorn main:app --reload --port 8000
```

### 3. فتح التوثيق التلقائي
```
http://localhost:8000/docs
```

---

## 🐳 التشغيل بـ Docker

```bash
# بناء الصورة
docker build -t video-downloader-api .

# تشغيل الحاوية
docker run -p 8000:8000 video-downloader-api
```

---

## 🌐 نقاط API (Endpoints)

### `GET /info?url=...`
جلب معلومات الفيديو بدون تنزيل.

**مثال:**
```
GET /info?url=https://www.facebook.com/watch?v=123456789
```

**الاستجابة:**
```json
{
  "title": "عنوان الفيديو",
  "duration": 120,
  "thumbnail": "https://...",
  "uploader": "اسم الصفحة",
  "formats": [...]
}
```

---

### `POST /download`
تنزيل الفيديو وإرجاعه كملف.

**جسم الطلب (JSON):**
```json
{
  "url": "https://www.facebook.com/watch?v=123456789",
  "quality": "best",
  "audio_only": false
}
```

| الحقل | القيم المقبولة | الوصف |
|-------|---------------|-------|
| `url` | رابط أي فيديو | مطلوب |
| `quality` | `best`, `worst`, `720`, `480`, `360` | الجودة المطلوبة |
| `audio_only` | `true` / `false` | تنزيل الصوت فقط (MP3) |

---

### `GET /direct-url?url=...&quality=best`
استخراج الرابط المباشر للفيديو (بدون تخزين على الخادم).

---

## 🔗 استخدامه في تطبيقك (JavaScript)

```javascript
// جلب معلومات الفيديو
const info = await fetch(`https://your-api.com/info?url=${encodeURIComponent(videoUrl)}`);
const data = await info.json();

// تنزيل الفيديو
const response = await fetch('https://your-api.com/download', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url: videoUrl, quality: '720' })
});
const blob = await response.blob();
const link = document.createElement('a');
link.href = URL.createObjectURL(blob);
link.download = 'video.mp4';
link.click();
```

---

## ☁️ النشر على السحابة

### Render.com (مجاني)
1. ارفع الملفات على GitHub
2. أنشئ Web Service جديد على [render.com](https://render.com)
3. اختر **Docker** كبيئة تشغيل
4. ابدأ النشر!

### Railway.app
```bash
railway init
railway up
```

---

## 🔒 ملاحظات مهمة

- **فيسبوك**: بعض الفيديوهات تتطلب تسجيل الدخول. استخدم `cookiefile` في الكود.
- **CORS**: عدّل `allow_origins` في `main.py` لتقتصر على نطاق تطبيقك.
- **الملفات المؤقتة**: يتم حذف الفيديوهات تلقائيًا بعد إرسالها.

---

## 🛠️ المنصات المدعومة

فيسبوك، يوتيوب، إنستغرام، تيك توك، تويتر/X، ديلي موشن، وأكثر من 1000 موقع آخر عبر yt-dlp.
