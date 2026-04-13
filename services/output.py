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

    async def send(self, message: types.Message, script: str, title: str) -> list[int]:
        """Send script as message(s) or file based on length. Returns sent message IDs."""
        if len(script) <= self._max_length:
            try:
                sent = await message.answer(script, parse_mode="Markdown")
            except Exception:
                sent = await message.answer(script)
            return [sent.message_id]

        # Long script -> send file + short summary
        file_path = Path(self._temp_dir) / f"{_safe_filename(title)}.md"
        file_path.write_text(script, encoding="utf-8")

        sent_ids: list[int] = []
        try:
            summary = self._extract_summary(script)
            summary_text = (
                f"Script dai ({len(script)} ky tu), gui file dinh kem.\n\n"
                f"Tom tat:\n{summary}"
            )
            try:
                sent = await message.answer(summary_text, parse_mode="Markdown")
            except Exception:
                sent = await message.answer(summary_text)
            sent_ids.append(sent.message_id)

            doc = FSInputFile(str(file_path), filename=f"{_safe_filename(title)}.md")
            sent_doc = await message.answer_document(doc)
            sent_ids.append(sent_doc.message_id)
        finally:
            file_path.unlink(missing_ok=True)
        return sent_ids

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
