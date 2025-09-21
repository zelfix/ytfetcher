from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Literal, Tuple
from urllib.parse import quote
from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.error import BadRequest
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

QualityChoice = Literal["medium", "high", "audio"]

URL_PATTERN = re.compile(r"(https?://\S+)")

BUTTONS: Dict[QualityChoice, str] = {
    "medium": "🎬 Среднее",
    "high": "🎞️ Высокое",
    "audio": "🎧 Аудио",
}

DOWNLOAD_ROOT = Path(os.getenv("DOWNLOAD_ROOT", "/srv/ytfetcher/downloads"))
DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")


@dataclass
class DownloadResult:
    file_path: Path
    info: Dict[str, object]
    media_kind: str


def build_application(token: str) -> Application:
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(handle_quality))
    return app


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "Привет! Отправьте ссылку на видео, и я предложу варианты скачивания."
    )


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    text = update.message.text or ""
    match = URL_PATTERN.search(text)
    if not match:
        await update.message.reply_text("Не нашёл ссылку. Отправьте полную URL.")
        return

    url = match.group(1)
    context.user_data["pending_url"] = url
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(label, callback_data=choice)
                for choice, label in BUTTONS.items()
            ]
        ]
    )
    await update.message.reply_text(
        "Выберите качество загрузки:", reply_markup=keyboard
    )


async def handle_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    await query.answer()
    choice = query.data
    if choice not in BUTTONS:
        await query.edit_message_text("Неизвестный вариант качества.")
        return

    url = context.user_data.get("pending_url")
    if not url:
        await query.edit_message_text("Сначала отправьте ссылку на видео.")
        return

    message = query.message
    if not message:
        return

    await message.edit_reply_markup(reply_markup=None)
    status_msg = await message.reply_text("Скачиваю, пожалуйста подождите…")

    try:
        result = await download_with_yt_dlp(url, choice)  # type: ignore[arg-type]
    except DownloadError as exc:
        logging.exception("Download failed: %s", exc)
        await status_msg.edit_text("Не удалось скачать видео. Попробуйте другую ссылку.")
        context.user_data.pop("pending_url", None)
        return
    except Exception as exc:  # pragma: no cover - defensive logging
        logging.exception("Unexpected error: %s", exc)
        await status_msg.edit_text("Произошла ошибка. Попробуйте позже.")
        context.user_data.pop("pending_url", None)
        return

    file_size = result.file_path.stat().st_size
    title = result.info.get("title", "Файл")

    link = build_public_link(result.file_path)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬇️ Скачать файл", url=link)]]
    )
    text = (
        "Готово!\n"
        f"Название: {title}\n"
        f"Размер: {humanize_size(file_size)}\n"
        "Нажмите кнопку ниже, чтобы скачать."
    )

    try:
        await status_msg.edit_text(text, reply_markup=keyboard)
    except BadRequest as exc:
        logging.warning("Failed to send button link, falling back to plain text: %s", exc)
        await status_msg.edit_text(
            text + f"\nПрямая ссылка: {link}", reply_markup=None
        )

    context.user_data.pop("pending_url", None)


def build_public_link(file_path: Path) -> str:
    if not PUBLIC_BASE_URL:
        raise RuntimeError("PUBLIC_BASE_URL не задан. Укажите базовый URL доступа к nginx.")
    base = PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/downloads/{quote(file_path.name)}"


def _yt_dlp_options(directory: str, choice: QualityChoice) -> Dict[str, object]:
    base: Dict[str, object] = {
        "outtmpl": str(Path(directory) / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }
    if choice == "medium":
        base["format"] = "bv*[height<=720]+ba/b[height<=720]/best[height<=720]"
    elif choice == "high":
        base["format"] = "bv*+ba/best"
    else:
        base["format"] = "bestaudio/best"
        base["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
        base["merge_output_format"] = "mp3"
    return base


def _run_download(url: str, choice: QualityChoice, directory: str) -> Tuple[Path, Dict[str, object], str]:
    options = _yt_dlp_options(directory, choice)
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

    files = sorted(Path(directory).glob("*"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise DownloadError("yt-dlp did not produce output.")

    media_kind = "audio" if choice == "audio" else "video"
    return files[-1], info, media_kind


async def download_with_yt_dlp(url: str, choice: QualityChoice) -> DownloadResult:
    loop = asyncio.get_running_loop()
    temp_dir = TemporaryDirectory()

    def task() -> DownloadResult:
        file_path, info, media_kind = _run_download(url, choice, temp_dir.name)
        extension = file_path.suffix or (".mp3" if media_kind == "audio" else ".mp4")
        target_name = build_filename(info, media_kind, extension)
        target_path = DOWNLOAD_ROOT / target_name
        shutil.move(str(file_path), target_path)
        return DownloadResult(target_path, info, media_kind)

    try:
        return await loop.run_in_executor(None, task)
    finally:
        temp_dir.cleanup()


def humanize_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if size < 1024 or unit == "ГБ":
            text = f"{size:.1f}".rstrip("0").rstrip(".")
            return f"{text} {unit}"
        size /= 1024
    return f"{size:.1f} ГБ"  # fallback


def build_filename(info: Dict[str, object], media_kind: str, extension: str) -> str:
    title = str(info.get("title") or "")
    base = sanitize_filename(title) or media_kind
    suffix = uuid4().hex[:8]
    return f"{base}_{suffix}{extension}"


def sanitize_filename(value: str, max_length: int = 80) -> str:
    value = value.strip()
    if not value:
        return ""
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^\w.-]", "_", value, flags=re.UNICODE)
    value = re.sub(r"_+", "_", value)
    return value[:max_length].strip("._")
