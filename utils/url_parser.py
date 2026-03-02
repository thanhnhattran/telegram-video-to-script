import re
from enum import Enum


class Platform(Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"


# YouTube patterns
_YT_PATTERNS = [
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([\w-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([\w-]{11})"),
    re.compile(r"(?:https?://)?youtu\.be/([\w-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/live/([\w-]{11})"),
]

# TikTok patterns
_TT_PATTERNS = [
    re.compile(r"(?:https?://)?(?:www\.)?tiktok\.com/@[\w.-]+/video/(\d+)"),
    re.compile(r"(?:https?://)?(?:vm|vt)\.tiktok\.com/([\w]+)"),
]


def parse_video_url(text: str) -> tuple[Platform, str, str] | None:
    """Parse a video URL and return (platform, video_id, clean_url) or None."""
    for pattern in _YT_PATTERNS:
        match = pattern.search(text)
        if match:
            video_id = match.group(1)
            url = match.group(0)
            if not url.startswith("http"):
                url = "https://" + url
            return Platform.YOUTUBE, video_id, url

    for pattern in _TT_PATTERNS:
        match = pattern.search(text)
        if match:
            video_id = match.group(1)
            url = match.group(0)
            if not url.startswith("http"):
                url = "https://" + url
            return Platform.TIKTOK, video_id, url

    return None
