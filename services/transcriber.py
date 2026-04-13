import asyncio
import logging
import subprocess
from pathlib import Path

import httpx
from google import genai
from google.genai import types

from bot.config import Config
from services.downloader import Downloader
from utils.url_parser import Platform

logger = logging.getLogger(__name__)

WHISPER_MAX_BYTES = 24 * 1024 * 1024  # 24MB (safe margin under Whisper 25MB limit)
CHUNK_DURATION_SECONDS = 600  # 10-minute chunks


class Transcriber:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._downloader = Downloader(config)
        self._gemini = genai.Client(api_key=config.gemini_api_key)

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

        chunks: list[Path] = []
        try:
            chunks = await self._maybe_split_audio(audio_path)
            transcripts = []
            for chunk in chunks:
                text = await self._transcribe_with_fallback(chunk)
                if text:
                    transcripts.append(text)
            return " ".join(transcripts) if transcripts else None
        finally:
            # Clean up chunks directory if audio was split
            if chunks and chunks != [audio_path]:
                for chunk in chunks:
                    chunk.unlink(missing_ok=True)
                try:
                    chunks[0].parent.rmdir()
                except Exception:
                    pass
            audio_path.unlink(missing_ok=True)

    async def _maybe_split_audio(self, audio_path: Path) -> list[Path]:
        """Return [audio_path] if under limit, else split into 10-min chunks."""
        if audio_path.stat().st_size <= WHISPER_MAX_BYTES:
            return [audio_path]

        size_mb = audio_path.stat().st_size / 1024 / 1024
        logger.info("Audio %.1fMB exceeds Whisper limit, splitting into chunks", size_mb)

        chunks_dir = audio_path.parent / f"{audio_path.stem}_chunks"
        chunks_dir.mkdir(exist_ok=True)

        await asyncio.to_thread(
            subprocess.run,
            [
                "ffmpeg", "-i", str(audio_path),
                "-f", "segment",
                "-segment_time", str(CHUNK_DURATION_SECONDS),
                "-c", "copy",
                str(chunks_dir / "chunk_%03d.mp3"),
                "-y",
            ],
            capture_output=True,
            check=True,
        )

        chunks = sorted(chunks_dir.glob("chunk_*.mp3"))
        logger.info("Split into %d chunks", len(chunks))
        return chunks

    async def _transcribe_with_fallback(self, audio_path: Path) -> str | None:
        """Try Gemini Flash first, fall back to Groq then OpenAI Whisper."""
        # Tier 1: Gemini Flash (best Vietnamese support)
        try:
            result = await self._transcribe_gemini(audio_path)
            if result:
                return result
        except Exception:
            logger.warning("Gemini STT failed, falling back to Groq", exc_info=True)

        # Tier 2: Groq Whisper
        try:
            result = await self._transcribe_groq(audio_path)
            if result:
                return result
        except Exception:
            logger.warning("Groq Whisper failed, falling back to OpenAI", exc_info=True)

        # Tier 3: OpenAI Whisper
        if self._config.openai_api_key:
            try:
                return await self._transcribe_openai(audio_path)
            except Exception:
                logger.error("OpenAI Whisper also failed", exc_info=True)

        return None

    async def _transcribe_gemini(self, audio_path: Path) -> str | None:
        """Transcribe using Gemini Flash with native audio understanding."""
        uploaded = await self._gemini.aio.files.upload(file=audio_path)
        try:
            response = await self._gemini.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Content(parts=[
                        types.Part.from_uri(
                            file_uri=uploaded.uri,
                            mime_type=uploaded.mime_type,
                        ),
                        types.Part.from_text(
                            text="Transcribe this audio exactly as spoken. "
                            "Keep the original language. "
                            "Output only the transcription, no timestamps or labels."
                        ),
                    ]),
                ],
                config=types.GenerateContentConfig(temperature=0.1),
            )
            text = response.text.strip() if response.text else None
            logger.info("Gemini STT succeeded (%d chars)", len(text) if text else 0)
            return text
        finally:
            await self._gemini.aio.files.delete(name=uploaded.name)

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
