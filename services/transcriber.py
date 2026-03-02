import logging
from pathlib import Path

import httpx

from bot.config import Config
from services.downloader import Downloader
from utils.url_parser import Platform

logger = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._downloader = Downloader(config)

    async def get_transcript(self, url: str, platform: Platform, info: dict) -> str | None:
        """Get transcript using the 3-tier fallback pipeline.

        1. YouTube subtitles (free, instant)
        2. Groq Whisper API (free tier)
        3. OpenAI Whisper API (paid fallback)
        """
        # Tier 1: YouTube subtitles (only for YouTube)
        if platform == Platform.YOUTUBE:
            subs = await self._downloader.get_subtitles(url, info)
            if subs and len(subs.strip()) > 50:
                logger.info("Using YouTube subtitles for %s", url)
                return subs

        # Need audio for STT
        logger.info("Downloading audio for STT: %s", url)
        audio_path = await self._downloader.download_audio(url)

        if not audio_path.exists():
            logger.error("Audio file not found: %s", audio_path)
            return None

        try:
            # Tier 2: Groq Whisper (free)
            transcript = await self._transcribe_groq(audio_path)
            if transcript:
                logger.info("Using Groq Whisper for %s", url)
                return transcript
        except Exception:
            logger.warning("Groq Whisper failed, falling back to OpenAI", exc_info=True)

        try:
            # Tier 3: OpenAI Whisper (paid)
            if self._config.openai_api_key:
                transcript = await self._transcribe_openai(audio_path)
                if transcript:
                    logger.info("Using OpenAI Whisper for %s", url)
                    return transcript
        except Exception:
            logger.error("OpenAI Whisper also failed", exc_info=True)
        finally:
            audio_path.unlink(missing_ok=True)

        return None

    async def _transcribe_groq(self, audio_path: Path) -> str | None:
        """Transcribe using Groq Whisper large-v3 API."""
        async with httpx.AsyncClient(timeout=120) as client:
            with open(audio_path, "rb") as f:
                response = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self._config.groq_api_key}"},
                    files={"file": (audio_path.name, f, "audio/mpeg")},
                    data={
                        "model": "whisper-large-v3",
                        "response_format": "text",
                    },
                )
            response.raise_for_status()
            return response.text.strip()

    async def _transcribe_openai(self, audio_path: Path) -> str | None:
        """Transcribe using OpenAI Whisper API."""
        async with httpx.AsyncClient(timeout=120) as client:
            with open(audio_path, "rb") as f:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self._config.openai_api_key}"},
                    files={"file": (audio_path.name, f, "audio/mpeg")},
                    data={
                        "model": "whisper-1",
                        "response_format": "text",
                    },
                )
            response.raise_for_status()
            return response.text.strip()
