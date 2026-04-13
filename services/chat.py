import logging
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from bot.config import Config

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = (
    "You are a helpful assistant discussing video content. "
    "The user has just received a transcript from a video. "
    "Answer questions about the content, provide analysis, summaries, "
    "or discuss any topic the user brings up. "
    "Keep the ORIGINAL language of the conversation. "
    "If the user writes in Vietnamese, reply in Vietnamese."
)


@dataclass
class ChatSession:
    transcript: str
    script_message_ids: set[int] = field(default_factory=set)
    history: list[types.Content] = field(default_factory=list)


class ChatManager:
    def __init__(self, config: Config) -> None:
        self._client = genai.Client(api_key=config.gemini_api_key)
        self._sessions: dict[int, ChatSession] = {}

    def create_session(
        self, chat_id: int, transcript: str, script_message_ids: list[int]
    ) -> None:
        self._sessions[chat_id] = ChatSession(
            transcript=transcript,
            script_message_ids=set(script_message_ids),
        )
        logger.info("Chat session created for chat_id=%d", chat_id)

    def get_session(self, chat_id: int) -> ChatSession | None:
        return self._sessions.get(chat_id)

    def remove_session(self, chat_id: int) -> None:
        self._sessions.pop(chat_id, None)

    def is_reply_to_script(self, chat_id: int, reply_to_id: int) -> bool:
        session = self._sessions.get(chat_id)
        if not session:
            return False
        return reply_to_id in session.script_message_ids

    async def chat(self, chat_id: int, user_message: str) -> str | None:
        session = self._sessions.get(chat_id)
        if not session:
            return None

        session.history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        )

        # Build contents: transcript context + conversation history
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=
                    f"Here is the video transcript for context:\n\n{session.transcript}"
                )],
            ),
            types.Content(
                role="model",
                parts=[types.Part.from_text(text=
                    "Got it. I've read the transcript. How can I help you?"
                )],
            ),
            *session.history,
        ]

        try:
            response = await self._client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=CHAT_SYSTEM_PROMPT,
                    temperature=0.5,
                    max_output_tokens=4096,
                ),
            )
            reply = response.text.strip() if response.text else None
            if reply:
                session.history.append(
                    types.Content(
                        role="model", parts=[types.Part.from_text(text=reply)]
                    )
                )
            return reply
        except Exception:
            logger.exception("Gemini chat failed for chat_id=%d", chat_id)
            return None
