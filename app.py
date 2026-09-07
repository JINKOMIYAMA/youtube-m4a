from __future__ import annotations

import io
import re
import shutil
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import requests
import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from mutagen.mp4 import MP4, MP4Cover
from PIL import Image
from pydantic import BaseModel, HttpUrl, Field
from starlette.background import BackgroundTask

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

app = FastAPI(title="YouTube → M4A", version="1.0.0")

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


class InfoRequest(BaseModel):
    url: HttpUrl


class DownloadRequest(BaseModel):
    url: HttpUrl
    title: str = Field(min_length=1, max_length=300)
    artist: str = Field(min_length=1, max_length=300)


def validate_youtube_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in YOUTUBE_HOSTS:
        raise HTTPException(status_code=400, detail="YouTube のURLを入力してください。")
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="URL形式が正しくありません。")
    return url


def clean_filename(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip()
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value[:180] or "audio")


def ydl_base_options() -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "restrictfilenames": False,
        # Deno is auto-detected by current yt-dlp when available.
    }


def extract_info(url: str) -> dict:
    opts = ydl_base_options()
    opts["skip_download"] = True
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise RuntimeError("動画情報を取得できませんでした。")
            return info
    except yt_dlp.utils.DownloadError as exc:
        raise HTTPException(status_code=422, detail=f"動画情報を取得できませんでした: {exc}") from exc


def choose_thumbnail(info: dict) -> str | None:
    thumbnails = info.get("thumbnails") or []
    usable = [t for t in thumbnails if t.get("url")]
    if usable:
        usable.sort(key=lambda t: (t.get("width") or 0) * (t.get("height") or 0), reverse=True)
        return usable[0]["url"]
    return info.get("thumbnail")


def square_jpeg_from_url(url: str) -> bytes:
    response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    image = Image.open(io.BytesIO(response.content)).convert("RGB")
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    image = image.resize((1000, 1000), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=92, optimize=True)
    return out.getvalue()


def tag_m4a(path: Path, title: str, artist: str, artwork: bytes | None) -> None:
    audio = MP4(path)
    if audio.tags is None:
        audio.add_tags()
    audio.tags["\xa9nam"] = [title]
    audio.tags["\xa9ART"] = [artist]
    audio.tags["aART"] = [artist]
    if artwork:
        audio.tags["covr"] = [MP4Cover(artwork, imageformat=MP4Cover.FORMAT_JPEG)]
    audio.save()


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "deno": shutil.which("deno") is not None,
    }


@app.post("/api/info")
def api_info(payload: InfoRequest):
    url = validate_youtube_url(str(payload.url))
    info = extract_info(url)
    return {
        "id": info.get("id"),
        "title": info.get("title") or "Untitled",
        "artist": info.get("channel") or info.get("uploader") or "Unknown Artist",
        "thumbnail": choose_thumbnail(info),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url") or url,
    }


@app.post("/api/download")
def api_download(payload: DownloadRequest):
    url = validate_youtube_url(str(payload.url))
    title = payload.title.strip()
    artist = payload.artist.strip()
    if not title or not artist:
        raise HTTPException(status_code=400, detail="タイトルとアーティスト名を入力してください。")

    workdir = Path(tempfile.mkdtemp(prefix="ytm4a_"))
    output_template = str(workdir / "source.%(ext)s")

    opts = ydl_base_options()
    opts.update(
        {
            "format": "m4a/bestaudio/best",
            "outtmpl": output_template,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "0",
                }
            ],
        }
    )

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        candidates = list(workdir.glob("*.m4a"))
        if not candidates:
            raise HTTPException(status_code=500, detail="M4Aファイルを生成できませんでした。FFmpegを確認してください。")
        m4a_path = max(candidates, key=lambda p: p.stat().st_size)

        artwork = None
        thumbnail_url = choose_thumbnail(info)
        if thumbnail_url:
            try:
                artwork = square_jpeg_from_url(thumbnail_url)
            except Exception:
                artwork = None

        tag_m4a(m4a_path, title, artist, artwork)

        final_name = f"{clean_filename(title)}.m4a"
        final_path = workdir / final_name
        if m4a_path != final_path:
            m4a_path.replace(final_path)

        return FileResponse(
            path=final_path,
            media_type="audio/mp4",
            filename=final_name,
            background=BackgroundTask(shutil.rmtree, workdir, ignore_errors=True),
        )
    except HTTPException:
        shutil.rmtree(workdir, ignore_errors=True)
        raise
    except yt_dlp.utils.DownloadError as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"ダウンロードに失敗しました: {exc}") from exc
    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"処理中にエラーが発生しました: {exc}") from exc


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
