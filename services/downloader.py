import asyncio
import logging
import os
from pathlib import Path

import yt_dlp

from bot.config import Config

logger = logging.getLogger(__name__)


class Downloader:
    def __init__(self, config: Config) -> None:
        self._temp_dir = config.temp_dir

    async def get_video_info(self, url: str) -> dict:
        """Get video metadata without downloading."""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        return await asyncio.to_thread(self._extract_info, url, opts)

    async def get_subtitles(self, url: str, info: dict) -> str | None:
        """Try to get existing subtitles from YouTube."""
        # Check for manual subtitles first, then auto-generated
        subs = info.get("subtitles", {})
        auto_subs = info.get("automatic_captions", {})

        # Prefer: manual vi/en → auto vi/en
        for lang_prefs in [["vi", "en"], ["vi", "en"]]:
            source = subs if lang_prefs == ["vi", "en"] else auto_subs
            for lang in lang_prefs:
                if lang in source:
                    return await self._download_subtitle(url, lang, source is auto_subs)

        return None

    async def download_audio(self, url: str) -> Path:
        """Download audio only, return path to audio file."""
        output_path = os.path.join(self._temp_dir, "%(id)s.%(ext)s")
        opts = {
            "format": "bestaudio/best",
            "outtmpl": output_path,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",
                }
            ],
            "quiet": True,
            "no_warnings": True,
        }
        info = await asyncio.to_thread(self._extract_info, url, opts, download=True)
        video_id = info.get("id", "unknown")
        audio_path = Path(self._temp_dir) / f"{video_id}.mp3"

        if not audio_path.exists():
            # yt-dlp might use different extension
            for ext in ["mp3", "m4a", "webm", "opus"]:
                alt = Path(self._temp_dir) / f"{video_id}.{ext}"
                if alt.exists():
                    return alt

        return audio_path

    async def _download_subtitle(self, url: str, lang: str, is_auto: bool) -> str | None:
        """Download subtitle and return as text."""
        output_path = os.path.join(self._temp_dir, "%(id)s")
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "writesubtitles": not is_auto,
            "writeautomaticsub": is_auto,
            "subtitleslangs": [lang],
            "subtitlesformat": "vtt",
            "outtmpl": output_path,
        }

        info = await asyncio.to_thread(self._extract_info, url, opts, download=True)
        video_id = info.get("id", "unknown")

        # Find the subtitle file
        sub_path = Path(self._temp_dir) / f"{video_id}.{lang}.vtt"
        if not sub_path.exists():
            return None

        text = sub_path.read_text(encoding="utf-8")
        sub_path.unlink(missing_ok=True)
        return self._clean_vtt(text)

    @staticmethod
    def _extract_info(url: str, opts: dict, download: bool = False) -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            if download:
                return ydl.extract_info(url, download=True)
            return ydl.extract_info(url, download=False)

    @staticmethod
    def _clean_vtt(vtt_text: str) -> str:
        """Remove VTT formatting, timestamps, duplicates → clean text."""
        lines: list[str] = []
        seen: set[str] = set()

        for line in vtt_text.split("\n"):
            line = line.strip()
            # Skip headers, timestamps, empty lines
            if (
                not line
                or line.startswith("WEBVTT")
                or line.startswith("Kind:")
                or line.startswith("Language:")
                or "-->" in line
                or line.isdigit()
            ):
                continue
            # Remove HTML tags
            import re

            clean = re.sub(r"<[^>]+>", "", line)
            if clean and clean not in seen:
                seen.add(clean)
                lines.append(clean)

        return " ".join(lines)
