import asyncio
import logging
import time
from pathlib import Path

from aiogram import Router, types
from aiogram.filters import CommandStart, Command

from bot.config import Config
from services.downloader import Downloader
from services.transcriber import Transcriber
from services.formatter import Formatter
from services.output import OutputHandler
from utils.url_parser import parse_video_url, Platform

router = Router()
logger = logging.getLogger(__name__)

_processing_semaphore = asyncio.Semaphore(3)
_start_time = time.time()
_last_processed: float | None = None


def mark_processed() -> None:
    global _last_processed
    _last_processed = time.time()


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    await message.answer(
        "Chào! Gửi link video TikTok/YouTube/Shorts để tôi chuyển thành script.\n\n"
        "Hỗ trợ:\n"
        "- YouTube (video, Shorts)\n"
        "- TikTok\n\n"
        "Giới hạn: video tối đa 30 phút."
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    await message.answer(
        "Cách dùng: gửi link video trực tiếp.\n\n"
        "Ví dụ:\n"
        "• https://youtube.com/watch?v=xxx\n"
        "• https://youtube.com/shorts/xxx\n"
        "• https://tiktok.com/@user/video/xxx\n\n"
        "Bot sẽ trích xuất giọng đọc và format thành script có cấu trúc."
    )


@router.message(Command("status"))
async def cmd_status(message: types.Message) -> None:
    import subprocess
    import platform

    uptime_seconds = int(time.time() - _start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    try:
        result = subprocess.run(
            ["yt-dlp", "--version"], capture_output=True, text=True, timeout=5
        )
        ytdlp_version = result.stdout.strip()
    except Exception:
        ytdlp_version = "unknown"

    last_video = "never"
    if _last_processed:
        ago = int(time.time() - _last_processed)
        if ago < 60:
            last_video = f"{ago}s ago"
        elif ago < 3600:
            last_video = f"{ago // 60}m ago"
        else:
            last_video = f"{ago // 3600}h ago"

    status_text = (
        f"Bot Status: OK\n"
        f"Uptime: {hours}h {minutes}m {seconds}s\n"
        f"Python: {platform.python_version()}\n"
        f"yt-dlp: {ytdlp_version}\n"
        f"Last video: {last_video}"
    )
    await message.answer(status_text)


@router.message()
async def handle_message(message: types.Message, config: Config) -> None:
    if not message.text:
        return

    parsed = parse_video_url(message.text.strip())
    if not parsed:
        return  # Ignore non-URL messages

    platform, video_id, url = parsed
    status_msg = await message.answer("⏳ Đang xử lý video...")

    if _processing_semaphore.locked():
        await status_msg.edit_text("⏳ Đang xử lý video khác, vui lòng chờ...")

    async with _processing_semaphore:
        try:
            downloader = Downloader(config)
            transcriber = Transcriber(config)
            formatter = Formatter(config)
            output_handler = OutputHandler(config)

            # Step 1: Get video info & check duration
            info = await downloader.get_video_info(url)
            duration = info.get("duration", 0)
            if duration > config.max_video_duration:
                await status_msg.edit_text(
                    f"❌ Video quá dài ({duration // 60} phút). Giới hạn: {config.max_video_duration // 60} phút."
                )
                return

            await status_msg.edit_text("📝 Đang trích xuất transcript...")

            # Step 2: Get transcript (subtitles or STT)
            transcript = await transcriber.get_transcript(url, platform, info)

            if not transcript or not transcript.strip():
                await status_msg.edit_text("❌ Không thể trích xuất nội dung từ video này.")
                return

            await status_msg.edit_text("✨ Đang format script...")

            # Step 3: Format with AI
            title = info.get("title", "Untitled")
            script = await formatter.format_transcript(transcript, title)

            # Step 4: Send output
            await output_handler.send(message, script, title)
            await status_msg.delete()
            mark_processed()

        except Exception:
            logger.exception("Error processing video: %s", url)
            await status_msg.edit_text("❌ Có lỗi xảy ra khi xử lý video. Thử lại sau.")
