# Recent Sessions

---
## [2026-03-05] - Tăng video 30 phút + audio chunking + google-genai + deploy
**Focus:** Tăng giới hạn video 15→30 phút, thêm audio chunking tự động cho Whisper 25MB limit, migrate google-generativeai→google-genai, tăng tmpfs/memory Docker, deploy VPS thành công
**Commits:** 86421a1 feat: tăng giới hạn video 30 phút + audio chunking + migrate google-genai
**Next:** Không có task mới — bot healthy trên VPS

---
## [2026-03-02 17:00] - Full Pipeline: Bug fixes, Docker, Deploy
**Focus:** Fix 10 bugs from code review, add Docker Compose with health check/resource limits, add monitoring (/status + health_check.py), deploy to VPS
**Commits:**
- bd713e2 fix: Phase 1 & 2 - Bug fixes and Docker infrastructure improvements
**Deploy:** Bot @tiktok_noidung_bot running on 103.110.84.230 (healthy)
**Key changes:**
- transcriber.py: Audio cleanup wraps all STT tiers
- downloader.py: Subtitle logic fixed (manual -> auto fallback), re import moved to top
- formatter.py: system_instruction passed to Gemini
- output.py: Markdown try/except fallback + try/finally file cleanup
- url_parser.py: URL scheme prepended if missing
- handlers.py: asyncio.Semaphore(3) + /status command
- main.py: Error handler middleware
- New: docker-compose.yml, .dockerignore, health_check.py
**Note:** google.generativeai deprecated warning - migrate to google.genai in future
**Next:** Manual testing with real URLs, monitor logs
