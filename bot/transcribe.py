"""
Транскрипция видео/аудио через OpenAI Whisper API.
Поддерживает YouTube-ссылки (через yt-dlp) и прямые загрузки аудио/видео.
"""
import os
import logging
import tempfile
import asyncio
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")
WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"

# Лимит OpenAI Whisper API на размер файла — 25 МБ
MAX_FILE_BYTES = 25 * 1024 * 1024

YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "m.youtube.com", "www.youtube.com")


def is_youtube_url(text: str) -> bool:
    text = text.strip().lower()
    return text.startswith(("http://", "https://")) and any(h in text for h in YOUTUBE_HOSTS)


async def download_youtube_audio(url: str, out_dir: str) -> str:
    """Скачивает аудио с YouTube как m4a через yt-dlp. Возвращает путь к файлу."""
    out_template = os.path.join(out_dir, "audio.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bestaudio[ext=m4a]/bestaudio/best",
        "--no-playlist",
        "--no-warnings",
        "-o", out_template,
        url,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp ошибка: {stderr.decode(errors='ignore')[:500]}")

    files = list(Path(out_dir).glob("audio.*"))
    if not files:
        raise RuntimeError("yt-dlp не создал файл")
    return str(files[0])


async def transcribe_file(file_path: str, language: str = "ru") -> str:
    """Отправляет файл в OpenAI Whisper, возвращает расшифрованный текст."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY не задан в окружении")

    size = os.path.getsize(file_path)
    if size > MAX_FILE_BYTES:
        raise RuntimeError(
            f"Файл {size // 1024 // 1024} МБ > лимита Whisper API 25 МБ. "
            f"Видео слишком длинное."
        )

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    timeout = aiohttp.ClientTimeout(total=600)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        with open(file_path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("file", f, filename=os.path.basename(file_path))
            data.add_field("model", WHISPER_MODEL)
            data.add_field("response_format", "text")
            if language:
                data.add_field("language", language)

            async with session.post(WHISPER_URL, headers=headers, data=data) as resp:
                body = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"Whisper API {resp.status}: {body[:500]}")
                return body.strip()


async def transcribe_youtube(url: str, language: str = "ru") -> str:
    """Скачивает аудио с YouTube и транскрибирует."""
    with tempfile.TemporaryDirectory() as tmp:
        audio_path = await download_youtube_audio(url, tmp)
        return await transcribe_file(audio_path, language=language)
