import os
import re
import uuid
import asyncio
import tempfile
from pathlib import Path
from typing import Optional

import yt_dlp
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, HttpUrl

app = FastAPI(
    title="Video Downloader API",
    description="API for downloading videos using yt-dlp (Facebook, YouTube, Instagram, etc.)",
    version="1.0.0"
)

# ─── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # ضع هنا رابط تطبيقك بدلاً من * في الإنتاج
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── مجلد مؤقت لحفظ الفيديوهات ───────────────────────────────────────────
DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "video_downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# ─── نماذج البيانات ───────────────────────────────────────────────────────
class DownloadRequest(BaseModel):
    url: str
    quality: Optional[str] = "best"   # best | worst | 720 | 480 | 360
    audio_only: Optional[bool] = False

class VideoInfo(BaseModel):
    title: str
    duration: Optional[int]
    thumbnail: Optional[str]
    formats: list
    uploader: Optional[str]
    url: str

# ─── دالة مساعدة: خيارات yt-dlp ──────────────────────────────────────────
def build_ydl_opts(output_path: str, quality: str = "best", audio_only: bool = False) -> dict:
    if audio_only:
        format_str = "bestaudio/best"
        postprocessors = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        if quality == "best":
            format_str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        elif quality == "worst":
            format_str = "worst"
        else:
            # جودة محددة مثل 720 أو 480
            format_str = f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}]/best"
        postprocessors = []

    opts = {
        "format": format_str,
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        # ─── خيارات فيسبوك ───
        "cookiefile": None,       # ضع مسار ملف cookies هنا إذا احتجت
        "socket_timeout": 30,
        "retries": 3,
        # ─── User-Agent لتجنب الحجب ───
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    }

    if postprocessors:
        opts["postprocessors"] = postprocessors

    return opts


# ─── تنظيف الملفات القديمة (أكثر من ساعة) ────────────────────────────────
def cleanup_old_files():
    import time
    now = time.time()
    for f in DOWNLOAD_DIR.iterdir():
        if f.is_file() and (now - f.stat().st_mtime) > 3600:
            f.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "ok", "message": "Video Downloader API is running 🚀"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# ─── 1. جلب معلومات الفيديو بدون تنزيل ──────────────────────────
@app.get("/info")
async def get_video_info(url: str):
    """
    جلب معلومات الفيديو (العنوان، المدة، الجودات المتاحة، الصورة المصغرة).
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = []
        for f in info.get("formats", []):
            if f.get("vcodec") != "none":
                formats.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution") or f"{f.get('height', '?')}p",
                    "filesize": f.get("filesize"),
                    "fps": f.get("fps"),
                })

        return {
            "title": info.get("title"),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "uploader": info.get("uploader"),
            "view_count": info.get("view_count"),
            "upload_date": info.get("upload_date"),
            "formats": formats,
            "url": url,
        }

    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(status_code=400, detail=f"فشل في جلب معلومات الفيديو: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ غير متوقع: {str(e)}")


# ─── 2. تنزيل الفيديو وإرجاعه مباشرةً ───────────────────────────
@app.post("/download")
async def download_video(request: DownloadRequest, background_tasks: BackgroundTasks):
    """
    تنزيل الفيديو وإرجاعه كملف للتحميل المباشر.
    يدعم: فيسبوك، يوتيوب، إنستغرام، تيك توك، وغيرها.
    """
    file_id = str(uuid.uuid4())
    output_template = str(DOWNLOAD_DIR / f"{file_id}.%(ext)s")

    ydl_opts = build_ydl_opts(
        output_path=output_template,
        quality=request.quality,
        audio_only=request.audio_only,
    )

    try:
        loop = asyncio.get_event_loop()

        def do_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(request.url, download=True)
                return info

        info = await loop.run_in_executor(None, do_download)

        # إيجاد الملف المنزَّل
        downloaded_files = list(DOWNLOAD_DIR.glob(f"{file_id}.*"))
        if not downloaded_files:
            raise HTTPException(status_code=500, detail="لم يتم العثور على الملف بعد التنزيل")

        file_path = downloaded_files[0]
        filename = re.sub(r'[^\w\-_\. ]', '_', info.get("title", "video"))
        filename = f"{filename}{file_path.suffix}"

        # جدولة حذف الملف بعد إرساله
        background_tasks.add_task(lambda: file_path.unlink(missing_ok=True))
        background_tasks.add_task(cleanup_old_files)

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/octet-stream",
        )

    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(status_code=400, detail=f"فشل التنزيل: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ غير متوقع: {str(e)}")


# ─── 3. الحصول على رابط التنزيل المباشر فقط (بدون تنزيل على الخادم) ─
@app.get("/direct-url")
async def get_direct_url(url: str, quality: Optional[str] = "best"):
    """
    استخراج الرابط المباشر للفيديو لتنزيله من المتصفح مباشرةً
    دون تخزينه على الخادم.
    """
    if quality == "best":
        format_str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    else:
        format_str = f"best[height<={quality}]/best"

    ydl_opts = {
        "format": format_str,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            )
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        direct_url = info.get("url") or (
            info.get("formats", [{}])[-1].get("url") if info.get("formats") else None
        )

        if not direct_url:
            raise HTTPException(status_code=404, detail="تعذّر استخراج الرابط المباشر")

        return {
            "title": info.get("title"),
            "direct_url": direct_url,
            "ext": info.get("ext"),
            "filesize": info.get("filesize"),
            "thumbnail": info.get("thumbnail"),
        }

    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
