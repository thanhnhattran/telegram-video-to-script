# Research Report: Python Telegram Bot Production Best Practices
**Date:** 2026-03-02
**Focus:** aiogram 3.x + yt-dlp + google-generativeai hardening & code review

---

## 1. aiogram 3.x Production Error Handling & Graceful Shutdown

### Key Findings
- **Error Handlers:** Use try-except in handlers + router/dispatcher-level error handlers for fallback
- **Graceful Shutdown:** Aiogram 3.13+ supports signal-based graceful shutdown (Linux/Mac). Dispatcher stops polling cleanly without errors.
- **Middleware:** Use new interface—avoid both middleware/middlewares attributes in same context. Dispatcher now includes workflow_data in startup/shutdown events.
- **Critical Action:** Implement dispatcher-level error handler to catch unhandled exceptions, log them, and notify user gracefully.

### Production Checklist
- [ ] Add `@dp.error_handler()` to catch ALL exceptions from handlers
- [ ] Use `dp.run_polling()` which respects signals for clean shutdown
- [ ] Log errors with traceback for debugging
- [ ] Send user-friendly Telegram messages instead of stack traces

---

## 2. yt-dlp Security: Cookie Leaks, Temp Files, Rate Limiting

### Key Findings
- **Cookie Security Risk:** yt-dlp leaks cookies on HTTP redirects or when download fragments differ from manifest host. MITIGATION: Avoid --cookies unless essential. If needed, delete after use.
- **Cookie Freshness:** Cookies expire in ~30 mins. YouTube rotates cookies frequently. Export from fresh browser session only.
- **Rate Limits:** Guest sessions: ~300 videos/hr. Add 5-10s delay between downloads. Using account risks ban—use throwaway account or accept risk.
- **Temp File Cleanup:** Interrupted downloads leave temp files. Use --exec hooks or containerization. Leftover files prevent subsequent downloads if disk full.

### Production Checklist
- [ ] NEVER store persistent cookies file—generate fresh or delete post-download
- [ ] Add 5-10s delay between video downloads to avoid rate limits
- [ ] Implement cleanup hook: `--exec after_dl:"rm -rf temp_file"` or cleanup in code
- [ ] Use temporary directory context manager, auto-cleanup on exit
- [ ] Validate video URL before passing to yt-dlp (prevent command injection)

---

## 3. google-generativeai Async Best Practices

### Key Findings
- **API Errors:** Catch `google.genai.errors.APIError` with .code and .message properties.
- **Async Client Lifecycle:** Use `client.aio` for async. MUST call `await aclient.aclose()` to release resources. Avoid "client has been closed" errors.
- **Event Loop Requirement:** Async client must run in same event loop as caller. Mismatched loops = errors.
- **Retry Logic:** Use retry decorator with randomized waits for quota limit hits.
- **Function Calling:** Don't raise exceptions in functions—return error responses to model.

### Production Checklist
- [ ] Wrap google API calls in try-except APIError
- [ ] Implement `async with AsyncClient(...):` pattern or ensure `aclose()` called
- [ ] Add retry decorator with exponential backoff (500ms→4s) + jitter for quota limits
- [ ] Handle rate limits gracefully: return to user "API busy, retry in 30s"

---

## 4. Python Async Temp File Management

### Key Findings
- **Built-in Solution:** Use `tempfile.TemporaryDirectory()` or `NamedTemporaryFile()` as context managers. Auto-cleanup on exit, even on exceptions.
- **Async Context Managers:** Use `@asynccontextmanager` for async file cleanup. Implement `__aenter__()` / `__aexit__()` for custom cleanup.
- **Guarantee:** Context managers prevent resource leaks (files, memory, sockets). Exception-safe.
- **Key Setting:** `delete=True` (default) + context manager = guaranteed removal.

### Production Checklist
- [ ] Use `with tempfile.TemporaryDirectory() as tmpdir:` for all downloads
- [ ] Download videos to tmpdir, process, then auto-cleanup
- [ ] For custom cleanup, implement `@asynccontextmanager` wrapper
- [ ] NEVER manually delete files—let context managers handle it

---

## 5. Groq Whisper API (Not Researched)
**Note:** Web search returned no specific Groq Whisper API limits. Recommend:
- Check Groq official docs for file size limits (likely 25MB+)
- Check rate limits in your API key dashboard
- Implement retry with exponential backoff

---

## Actionable Integration Plan

### Risk Areas to Harden
1. **Cookie Security:** Remove persistent cookie storage. Use temp cookies or none.
2. **Rate Limiting:** Add delays between yt-dlp calls. Implement queue system if processing multiple videos.
3. **Temp File Cleanup:** Use context managers for ALL temp directories. Test cleanup on interruption.
4. **Error Recovery:** Add global error handlers in aiogram dispatcher. Notify user on API failures.
5. **Async Lifecycle:** Ensure google-generativeai and httpx clients closed properly on bot shutdown.

### Quick Wins (30 min each)
- [ ] Replace persistent cookies with fresh-per-download approach
- [ ] Add 5s delay between video downloads
- [ ] Wrap all temp operations in context managers
- [ ] Add dispatcher-level error handler + user notification
- [ ] Test graceful shutdown with SIGTERM signal

---

## Sources
- [aiogram 3.25.0 Changelog](https://docs.aiogram.dev/en/latest/changelog.html)
- [aiogram Error Handling](https://docs.aiogram.dev/en/latest/dispatcher/errors.html)
- [aiogram Graceful Shutdown PR #1124](https://github.com/aiogram/aiogram/pull/1124)
- [yt-dlp FAQ & Security](https://github.com/yt-dlp/yt-dlp/wiki/FAQ)
- [yt-dlp Cookie Leak Advisory](https://github.com/yt-dlp/yt-dlp/security/advisories/GHSA-v8mc-9377-rwjj)
- [google-genai SDK Docs](https://googleapis.github.io/python-genai/)
- [Python tempfile Module](https://docs.python.org/3/library/tempfile.html)
- [Python Context Managers Guide](https://realpython.com/python-with-statement/)
