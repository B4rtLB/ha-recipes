"""Video download (yt-dlp) and ffmpeg helpers. All functions here are blocking."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import shutil
import subprocess
from typing import Any

from .const import MAX_VIDEO_BYTES

_LOGGER = logging.getLogger(__name__)

# Prefer H.264 + AAC in MP4 so Safari on iOS can always play it inline.
FORMAT = (
    "b[vcodec^=avc1][ext=mp4][height<=1920]"
    "/bv*[vcodec^=avc1][height<=1920]+ba[acodec^=mp4a]"
    "/bv*[vcodec^=avc1][height<=1920]+ba"
    "/b[ext=mp4]/bv*+ba/b"
)


class VideoError(Exception):
    """Raised when a video cannot be downloaded."""


def ffmpeg_bin() -> str | None:
    """Locate ffmpeg (bundled in the Home Assistant container)."""
    return shutil.which("ffmpeg")


def ffprobe_bin() -> str | None:
    """Locate ffprobe."""
    return shutil.which("ffprobe")


def ytdlp_version() -> str | None:
    """Return the installed yt-dlp version."""
    try:
        from yt_dlp.version import __version__  # noqa: PLC0415
    except ImportError:
        return None
    return __version__


def download_video(url: str, folder: Path, cookie_file: Path | None) -> dict[str, Any]:
    """Download the video at url into folder/video.mp4 using yt-dlp.

    Returns a dict with the useful metadata (description, uploader, thumbnail,
    duration, width, height, webpage_url, path).
    """
    import yt_dlp  # noqa: PLC0415 - heavy import, keep it in the executor

    folder.mkdir(parents=True, exist_ok=True)
    opts: dict[str, Any] = {
        "outtmpl": str(folder / "download.%(ext)s"),
        "format": FORMAT,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 30,
        "retries": 3,
        "max_filesize": MAX_VIDEO_BYTES,
        "overwrites": True,
        "cachedir": False,
    }
    if (ff := ffmpeg_bin()) is not None:
        opts["ffmpeg_location"] = ff
    if cookie_file is not None and cookie_file.exists():
        opts["cookiefile"] = str(cookie_file)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as err:  # yt-dlp raises many different exception types
        raise VideoError(str(err).replace("\x1b[0;31m", "").replace("\x1b[0m", "")) from err
    if info is None:
        raise VideoError("yt-dlp returned no information")
    if info.get("_type") == "playlist" and info.get("entries"):
        info = next(e for e in info["entries"] if e)

    downloaded = sorted(folder.glob("download.*"), key=lambda p: p.stat().st_size, reverse=True)
    downloaded = [p for p in downloaded if p.suffix.lower() in (".mp4", ".mov", ".m4v", ".webm", ".mkv")]
    result = {
        "description": info.get("description") or "",
        "title": info.get("title") or info.get("fulltitle"),
        "uploader": info.get("uploader") or info.get("channel") or info.get("creator"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url") or url,
        "path": None,
    }
    if downloaded:
        final = folder / "video.mp4"
        make_ios_friendly(downloaded[0], final)
        for leftover in folder.glob("download.*"):
            leftover.unlink(missing_ok=True)
        result["path"] = final
        result.update(probe(final))
    return result


def probe(path: Path) -> dict[str, Any]:
    """Return codec, width, height and duration of a video."""
    if (fp := ffprobe_bin()) is None:
        return {}
    try:
        out = subprocess.run(
            [fp, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            capture_output=True, check=True, timeout=60,
        ).stdout
        data = json.loads(out)
    except (subprocess.SubprocessError, ValueError):
        return {}
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    width, height = video.get("width"), video.get("height")
    rotation = 0
    for side in video.get("side_data_list", []) or []:
        if "rotation" in side:
            rotation = abs(int(side["rotation"]))
    if rotation in (90, 270):
        width, height = height, width
    duration = data.get("format", {}).get("duration")
    return {
        "codec": video.get("codec_name"),
        "width": width,
        "height": height,
        "duration": float(duration) if duration else None,
        "has_audio": any(s.get("codec_type") == "audio" for s in data.get("streams", [])),
    }


def make_ios_friendly(src: Path, dst: Path) -> None:
    """Remux/transcode so the file plays inline in iOS Safari and starts fast."""
    ff = ffmpeg_bin()
    if ff is None:
        shutil.move(src, dst)
        return
    info = probe(src)
    codec = info.get("codec")
    tmp = dst.with_suffix(".tmp.mp4")
    if codec in ("h264", None):
        args = ["-c", "copy"]
    elif codec == "hevc":
        args = ["-c", "copy", "-tag:v", "hvc1"]
    else:  # vp9 / av1: transcode
        args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k"]
    cmd = [ff, "-y", "-v", "error", "-i", str(src), *args, "-movflags", "+faststart", str(tmp)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=900)
        tmp.replace(dst)
        if src != dst:
            src.unlink(missing_ok=True)
    except subprocess.SubprocessError as err:
        _LOGGER.warning("ffmpeg remux failed (%s), keeping original file", err)
        tmp.unlink(missing_ok=True)
        shutil.move(src, dst)


def save_image(data: bytes, dst: Path, max_width: int = 1600) -> bool:
    """Normalize any image (webp/heic/png) into a reasonably sized JPEG."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".src")
    tmp.write_bytes(data)
    ff = ffmpeg_bin()
    try:
        if ff is None:
            tmp.replace(dst)
            return True
        subprocess.run(
            [ff, "-y", "-v", "error", "-i", str(tmp), "-vf",
             f"scale='min({max_width},iw)':-2", "-frames:v", "1", "-q:v", "3", str(dst)],
            check=True, capture_output=True, timeout=60,
        )
        return True
    except subprocess.SubprocessError as err:
        # Unknown format (e.g. HEIC without decoder): let the caller fall back
        # to a frame from the video instead of storing something Safari can't show.
        _LOGGER.debug("Image conversion failed: %s", err)
        return False
    finally:
        tmp.unlink(missing_ok=True)


def poster_from_video(video: Path, dst: Path, at: float = 0.8) -> bool:
    """Grab a frame from the video as poster image."""
    ff = ffmpeg_bin()
    if ff is None:
        return False
    try:
        subprocess.run(
            [ff, "-y", "-v", "error", "-ss", str(at), "-i", str(video), "-frames:v", "1",
             "-vf", "scale='min(1080,iw)':-2", "-q:v", "3", str(dst)],
            check=True, capture_output=True, timeout=60,
        )
    except subprocess.SubprocessError:
        return False
    return dst.exists()


def extract_audio(video: Path, dst: Path, max_seconds: int) -> bool:
    """Extract mono 16 kHz Opus/OGG audio for speech-to-text."""
    ff = ffmpeg_bin()
    if ff is None:
        return False
    try:
        subprocess.run(
            [ff, "-y", "-v", "error", "-i", str(video), "-t", str(max_seconds), "-vn",
             "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "24k", "-f", "ogg", str(dst)],
            check=True, capture_output=True, timeout=300,
        )
    except subprocess.SubprocessError as err:
        _LOGGER.debug("Audio extraction failed: %s", err)
        return False
    return dst.exists() and dst.stat().st_size > 1000


def write_bytes(path: Path, data: bytes) -> None:
    """Write a file, creating parent folders."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
