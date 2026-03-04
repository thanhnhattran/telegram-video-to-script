# Phase 1: Code Review & Bug Fixes

## Context Links
- [Research: Python Bot Best Practices](research/researcher-01-python-bot-best-practices.md)
- [Research: Docker & Monitoring](research/researcher-02-docker-deploy-monitoring.md)
- [Plan Overview](plan.md)

## Overview
- **Priority:** P1 (Critical -- blocks all other phases)
- **Status:** Pending
- **Effort:** 1.5h
- **Description:** Fix 9 bugs found during code review. Focus on data safety (temp files), correctness (subtitle logic, system prompt), and stability (error handling, shutdown).

## Key Insights
- Audio file cleanup only triggers when OpenAI tier runs (tier 3 `finally` block). If Groq succeeds, audio leaks on disk.
- Subtitle method has dead code: iterates `["vi", "en"]` twice with condition `lang_prefs == ["vi", "en"]` which is always true (list identity vs equality bug -- actually equality, but both lists are identical so `source` is always `subs`, never `auto_subs`).
- Gemini `SYSTEM_PROMPT` is defined but never passed to the model -- `GenerativeModel()` accepts `system_instruction` parameter.
- `re` module imported inside `for` loop in `_clean_vtt()` -- works but wasteful.
- `parse_mode="Markdown"` in output.py will crash on AI-generated markdown with unbalanced `*`, `_`, `` ` `` characters.

## Requirements

### Functional
- All temp audio files must be cleaned up regardless of which STT tier succeeds
- Subtitle extraction must check both manual and auto-generated captions
- Gemini must receive the system prompt
- Error handler must catch unhandled exceptions and notify user
- Bot must shut down gracefully on SIGTERM

### Non-Functional
- No new dependencies
- Backward-compatible (same env vars, same user-facing behavior)

## Architecture
No architectural changes. All fixes are in-place within existing modules.

## Related Code Files

### Files to Modify
| File | Lines | Changes |
|------|-------|---------|
| `services/transcriber.py` | 58-59 | Move audio cleanup to cover all tiers |
| `services/downloader.py` | 33-38, 104-128 | Fix subtitle logic + move `re` import to top |
| `services/formatter.py` | 25 | Pass `system_instruction` to `GenerativeModel` |
| `services/output.py` | 19, 29 | Fix parse_mode to handle invalid markdown |
| `bot/main.py` | 19-29 | Add graceful shutdown + error handler |
| `bot/handlers.py` | 42-91 | Add tempfile context manager |

### Files to Create
None.

### Files to Delete
None.

## Implementation Steps

### Bug 1: Temp File Leak (transcriber.py)
**Problem:** `audio_path.unlink()` only in tier 3 `finally` block (line 58-59). If tier 2 (Groq) succeeds, function returns at line 45 and audio file is never deleted.

**Fix:** Move audio cleanup to a `try/finally` that wraps ALL tiers (2 and 3).

```python
# transcriber.py -- get_transcript method, after line 34
audio_path = await self._downloader.download_audio(url)
if not audio_path.exists():
    logger.error("Audio file not found: %s", audio_path)
    return None

try:
    # Tier 2: Groq
    try:
        transcript = await self._transcribe_groq(audio_path)
        if transcript:
            logger.info("Using Groq Whisper for %s", url)
            return transcript
    except Exception:
        logger.warning("Groq Whisper failed, falling back to OpenAI", exc_info=True)

    # Tier 3: OpenAI
    try:
        if self._config.openai_api_key:
            transcript = await self._transcribe_openai(audio_path)
            if transcript:
                logger.info("Using OpenAI Whisper for %s", url)
                return transcript
    except Exception:
        logger.error("OpenAI Whisper also failed", exc_info=True)

    return None
finally:
    audio_path.unlink(missing_ok=True)
```

### Bug 2: Subtitle Logic (downloader.py lines 33-38)
**Problem:** `for lang_prefs in [["vi", "en"], ["vi", "en"]]` -- both elements identical. The condition `source = subs if lang_prefs == ["vi", "en"] else auto_subs` always evaluates to `subs` because both lists equal `["vi", "en"]`.

**Fix:** Iterate over `(source_dict, is_auto)` tuples directly.

```python
async def get_subtitles(self, url: str, info: dict) -> str | None:
    """Try to get existing subtitles from YouTube."""
    subs = info.get("subtitles", {})
    auto_subs = info.get("automatic_captions", {})

    # Prefer: manual vi/en -> auto vi/en
    for source, is_auto in [(subs, False), (auto_subs, True)]:
        for lang in ["vi", "en"]:
            if lang in source:
                return await self._download_subtitle(url, lang, is_auto)

    return None
```

### Bug 3: `re` Import Inside Loop (downloader.py line 122)
**Problem:** `import re` inside `for line in vtt_text.split("\n")` loop. Python caches imports so no real performance hit, but bad practice.

**Fix:** Move `import re` to top of `downloader.py` (line 1-4 area, alongside other imports). Remove line 122.

### Bug 4: Gemini System Prompt (formatter.py line 25)
**Problem:** `SYSTEM_PROMPT` string defined but never passed to the model. `GenerativeModel()` has a `system_instruction` parameter.

**Fix:**
```python
# formatter.py line 25
self._model = genai.GenerativeModel(
    "gemini-2.0-flash",
    system_instruction=SYSTEM_PROMPT,
)
```

Also simplify the prompt in `format_transcript` -- remove "following the rules above" since rules are now in system instruction:
```python
prompt = (
    f"Video title: {title}\n\n"
    f"Raw transcript:\n{transcript}\n\n"
    "Format this transcript into a well-structured, readable script."
)
```

### Bug 5: Error Handler Middleware (main.py)
**Problem:** No dispatcher-level error handler. Unhandled exceptions in handlers just log to console.

**Fix:** Add error handler in `main.py`:
```python
from aiogram.types import ErrorEvent

@dp.error()
async def on_error(event: ErrorEvent) -> bool:
    logger.exception("Unhandled error: %s", event.exception)
    if event.update and event.update.message:
        try:
            await event.update.message.answer(
                "Loi he thong. Vui long thu lai sau."
            )
        except Exception:
            pass
    return True  # Prevent further propagation
```

### Bug 6: Graceful Shutdown (main.py)
**Problem:** `dp.start_polling()` without shutdown handling. On SIGTERM (Docker stop), bot may not close cleanly.

**Fix:** Use `dp.run_polling()` which handles signals automatically in aiogram 3.13+. Replace `asyncio.run(main())` pattern:
```python
async def main() -> None:
    config = Config.from_env()
    bot = Bot(token=config.telegram_token)
    dp = Dispatcher()
    dp["config"] = config
    dp.include_router(router)

    # Register error handler
    @dp.error()
    async def on_error(event: ErrorEvent) -> bool:
        logger.exception("Unhandled error: %s", event.exception)
        if event.update and event.update.message:
            try:
                await event.update.message.answer("Loi he thong. Thu lai sau.")
            except Exception:
                pass
        return True

    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
```

Note: `asyncio.run()` + `dp.start_polling()` already handles SIGINT/SIGTERM on Linux (aiogram 3.13+). No extra signal handling needed.

### Bug 7: Markdown parse_mode (output.py lines 19, 29)
**Problem:** `parse_mode="Markdown"` will fail if Gemini output contains unbalanced `*`, `_`, or backticks. Telegram's Markdown parser is strict.

**Fix:** Use `try/except` fallback -- try Markdown first, fall back to plain text:
```python
async def send(self, message: types.Message, script: str, title: str) -> None:
    if len(script) <= self._max_length:
        try:
            await message.answer(script, parse_mode="Markdown")
        except Exception:
            await message.answer(script)
        return

    # Long script -> file
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
```

### Bug 8: Output File Cleanup (output.py)
**Problem:** If `message.answer()` or `answer_document()` throws, the `.md` file is never cleaned up.

**Fix:** Wrapped in `try/finally` in Bug 7 fix above.

### Bug 9: URL Scheme (url_parser.py)
**Problem:** Regex patterns use `(?:https?://)?` making scheme optional. URLs without scheme work fine with yt-dlp, so this is low-risk. The `parse_video_url` returns `match.group(0)` which may not include scheme.

**Fix (minimal):** Ensure returned URL has scheme:
```python
def parse_video_url(text: str) -> tuple[Platform, str, str] | None:
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
```

### Bug 10: Concurrency Control (handlers.py) — Added from Validation
**Problem:** Multiple users sending URLs simultaneously → parallel yt-dlp downloads → may exceed 512MB RAM / 256MB tmpfs.

**Fix:** Add `asyncio.Semaphore(3)` to limit concurrent video processing.

```python
# handlers.py — module level
import asyncio
_processing_semaphore = asyncio.Semaphore(3)

# In handle_message(), wrap processing in semaphore:
async def handle_message(message: types.Message, config: Config) -> None:
    # ... URL parsing, status_msg ...

    async with _processing_semaphore:
        # ... all processing steps (download, transcribe, format, send) ...
```

If semaphore is full, add message to user:
```python
if _processing_semaphore.locked():
    await status_msg.edit_text("⏳ Đang xử lý video khác, vui lòng chờ...")
```

## Todo List
- [ ] Fix temp file leak in `transcriber.py` (Bug 1)
- [ ] Fix subtitle logic in `downloader.py` (Bug 2)
- [ ] Move `re` import to module level in `downloader.py` (Bug 3)
- [ ] Pass system_instruction to Gemini in `formatter.py` (Bug 4)
- [ ] Add error handler in `main.py` (Bug 5)
- [ ] Verify graceful shutdown works with current setup (Bug 6)
- [ ] Fix Markdown parse_mode with try/except fallback in `output.py` (Bug 7)
- [ ] Add file cleanup in `output.py` with try/finally (Bug 8)
- [ ] Ensure URL scheme in `url_parser.py` (Bug 9)
- [ ] Add asyncio.Semaphore concurrency control in `handlers.py` (Bug 10)

## Success Criteria
- All 9 bugs fixed with minimal code changes
- No new dependencies added
- Bot behavior unchanged from user perspective (same commands, same output)
- Temp files cleaned up in ALL code paths (verify with `ls /tmp/video-to-script/` after processing)

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| Gemini system_instruction changes output format | Medium | Test with real video, compare output quality |
| Markdown fallback to plain text loses formatting | Low | Acceptable -- better than crash |
| Subtitle logic change breaks existing working flow | Medium | Test with YouTube video that has both manual and auto subs |

## Security Considerations
- URL validation prevents injection (regex already restrictive, only allows known domains)
- No persistent cookie storage (yt-dlp uses fresh sessions)
- API keys remain in env vars, not in code

## Next Steps
- After all bugs fixed, proceed to Phase 2 (Docker Compose)
- Commit all fixes in single commit: `fix: resolve 9 bugs from code review`
