import logging

from google import genai
from google.genai import types

from bot.config import Config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a transcript formatter. Convert raw video transcripts into well-structured, readable scripts.

Rules:
- Add clear headings (##) for each major section/topic
- Use bullet points for key points and lists
- Add a "Key Takeaways" section at the end with 3-5 main points
- Keep the ORIGINAL language (do not translate)
- Fix obvious STT typos/errors
- Remove filler words (um, uh, à, ờ) and repetitions
- Keep the content faithful to the original - do not add or remove meaning
- Use Markdown formatting"""


class Formatter:
    def __init__(self, config: Config) -> None:
        self._client = genai.Client(api_key=config.gemini_api_key)

    async def format_transcript(self, transcript: str, title: str) -> str:
        """Format raw transcript into structured script using Gemini."""
        prompt = (
            f"Video title: {title}\n\n"
            f"Raw transcript:\n{transcript}\n\n"
            "Format this transcript into a well-structured, readable script."
        )

        try:
            response = await self._client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
            )
            return response.text or transcript
        except Exception:
            logger.exception("Gemini formatting failed, returning raw transcript")
            return f"## {title}\n\n{transcript}"
