import logging
import tempfile
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


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    await message.answer(
        "Chào! Gửi link video TikTok/YouTube/Shorts để tôi chuyển thành script.\n\n"
        "Hỗ trợ:\n"
        "- YouTube (video, Shorts)\n"
        "- TikTok\n\n"
        "Giới hạn: video tối đa 15 phút."
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


@router.message()
async def handle_message(message: types.Message, config: Config) -> None:
    if not message.text:
        return

    parsed = parse_video_url(message.text.strip())
    if not parsed:
        return  # Ignore non-URL messages

    platform, video_id, url = parsed
    status_msg = await message.answer("⏳ Đang xử lý video...")

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

    except Exception:
        logger.exception("Error processing video: %s", url)
        await status_msg.edit_text("❌ Có lỗi xảy ra khi xử lý video. Thử lại sau.")
