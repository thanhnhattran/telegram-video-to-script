import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    telegram_token: str
    groq_api_key: str
    openai_api_key: str
    gemini_api_key: str
    max_video_duration: int = 1800  # 30 minutes in seconds
    temp_dir: str = "/tmp/video-to-script"
    max_message_length: int = 4000
    telegram_api_url: str = "https://api.telegram.org"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            telegram_token=os.environ["TELEGRAM_BOT_TOKEN"],
            groq_api_key=os.environ["GROQ_API_KEY"],
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            gemini_api_key=os.environ["GEMINI_API_KEY"],
            max_video_duration=int(os.environ.get("MAX_VIDEO_DURATION", "1800")),
            temp_dir=os.environ.get("TEMP_DIR", "/tmp/video-to-script"),
            telegram_api_url=os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org"),
        )
