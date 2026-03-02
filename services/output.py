import tempfile
from pathlib import Path

from aiogram import types
from aiogram.types import FSInputFile

from bot.config import Config
from utils.text_utils import split_text


class OutputHandler:
    def __init__(self, config: Config) -> None:
        self._max_length = config.max_message_length
        self._temp_dir = config.temp_dir

    async def send(self, message: types.Message, script: str, title: str) -> None:
        """Send script as message(s) or file based on length."""
        if len(script) <= self._max_length:
            try:
                await message.answer(script, parse_mode="Markdown")
            except Exception:
                await message.answer(script)
            return

        # Long script -> send file + short summary
        file_path = Path(self._temp_dir) / f"{_safe_filename(title)}.md"
        file_path.write_text(script, encoding="utf-8")

        try:
            summary = self._extract_summary(script)
            summary_text = (
                f"Script dai ({len(script)} ky tu), gui file dinh kem.\n\n"
                f"Tom tat:\n{summary}"
            )
            try:
                await message.answer(summary_text, parse_mode="Markdown")
            except Exception:
                await message.answer(summary_text)

            doc = FSInputFile(str(file_path), filename=f"{_safe_filename(title)}.md")
            await message.answer_document(doc)
        finally:
            file_path.unlink(missing_ok=True)

    def _extract_summary(self, script: str) -> str:
        """Extract Key Takeaways section or first 500 chars."""
        lower = script.lower()
        idx = lower.find("key takeaway")
        if idx != -1:
            return script[idx : idx + 500].strip()
        return script[:500].strip() + "..."


def _safe_filename(title: str) -> str:
    """Convert title to safe filename."""
    safe = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
    return safe.strip()[:80] or "script"
