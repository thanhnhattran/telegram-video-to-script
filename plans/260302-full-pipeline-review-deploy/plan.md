---
title: "Full Pipeline: Video-to-Script Bot"
description: "Code review, bug fixes, Docker Compose deploy, monitoring setup"
status: in_progress
priority: P1
effort: 4h
branch: master
tags: [python, telegram, docker, deploy]
created: 2026-03-02
---

# Full Pipeline: Telegram Video-to-Script Bot

## Objective
Fix 9 identified bugs, add Docker Compose production config, deploy to VPS, add basic monitoring.

## Phases

| # | Phase | Effort | Status | Files |
|---|-------|--------|--------|-------|
| 1 | [Code Review & Bug Fixes](phase-01-code-review-bug-fixes.md) | 1.5h | ✅ Complete | 6 files |
| 2 | [Docker Compose & Improvements](phase-02-docker-compose-improvements.md) | 1h | ✅ Complete | 3 files |
| 3 | [Testing](phase-03-testing.md) | 30m | ✅ Complete | manual |
| 4 | [Deploy](phase-04-deploy.md) | 30m | ✅ Complete | server |
| 5 | [Monitoring](phase-05-monitoring.md) | 30m | ✅ Complete | 2 files |

## Critical Bugs (Phase 1)

1. **Temp file leak** -- audio cleanup only in tier 3 `finally`, skipped if tier 2 succeeds
2. **Subtitle logic bug** -- iterates identical list twice, never reaches `auto_subs`
3. **`re` import inside loop** -- `downloader.py` line 122
4. **Gemini system prompt ignored** -- `SYSTEM_PROMPT` variable unused in API call
5. **No error middleware** -- unhandled exceptions crash silently
6. **No graceful shutdown** -- `start_polling()` without signal handling
7. **Markdown parse_mode crash** -- raw AI markdown breaks Telegram's parser
8. **Output file not cleaned** -- `output.py` file cleanup only on happy path
9. **No URL scheme validation** -- URLs without `https://` may behave unexpectedly

## Architecture (unchanged)

```
User -> Telegram -> aiogram Bot -> Downloader (yt-dlp)
                                -> Transcriber (subs/Groq/OpenAI)
                                -> Formatter (Gemini)
                                -> Output (msg or .md file)
```

## Deploy Target
- Server: 103.110.84.230 (Ubuntu 22.04, Docker 29.2.1)
- Path: `/root/projects/telegram-video-to-script/`

## Dependencies
- Phase 2 depends on Phase 1
- Phase 3 depends on Phase 2
- Phase 4 depends on Phase 3
- Phase 5 can start after Phase 2

## Research Reports
- [Python Bot Best Practices](research/researcher-01-python-bot-best-practices.md)
- [Docker Deploy & Monitoring](research/researcher-02-docker-deploy-monitoring.md)

## Validation Log

### Session 1 — 2026-03-02
**Trigger:** Initial plan creation — validate assumptions before implementation
**Questions asked:** 4

#### Questions & Answers

1. **[Scope]** Bot hiện tại ai gửi URL cũng xử lý được. Cần giới hạn user không?
   - Options: Không cần, ai dùng cũng được | Whitelist user IDs | Chỉ admin dùng
   - **Answer:** Không cần, ai dùng cũng được
   - **Rationale:** Bot public, MVP stage. Không cần thêm auth logic, giữ simple.

2. **[Architecture]** Nếu nhiều người gửi URL cùng lúc, bot xử lý song song (có thể vượt RAM/tmpfs). Thêm hàng đợi không?
   - Options: Không cần queue | Thêm semaphore đơn giản (Recommended) | Thêm asyncio.Queue
   - **Answer:** Thêm semaphore đơn giản
   - **Rationale:** Giới hạn max concurrent downloads để tránh vượt 512MB RAM / 256MB tmpfs. asyncio.Semaphore không cần dependency ngoài.

3. **[Deploy]** API keys cho deploy: bạn đã có sẵn các keys chưa?
   - Options: Có đủ rồi | Cần tạo mới | Có nhưng chưa đủ
   - **Answer:** Có đủ rồi
   - **Rationale:** Deploy không bị block bởi API key setup. Có thể deploy ngay sau code changes.

4. **[Testing]** Plan chỉ có manual testing (không unit test). Chấp nhận không?
   - Options: Manual testing là đủ (Recommended) | Thêm basic unit tests
   - **Answer:** Manual testing là đủ
   - **Rationale:** Bot I/O-bound, manual test với real URLs hiệu quả hơn mock tests. Tiết kiệm effort.

#### Confirmed Decisions
- **Access control:** Public bot, no restrictions — MVP first
- **Concurrency:** Add asyncio.Semaphore (max 3 concurrent) in Phase 1
- **API keys:** Ready, no blocker for deploy
- **Testing:** Manual only, no unit tests

#### Action Items
- [ ] Add asyncio.Semaphore to handlers.py (max 3 concurrent video processing)
- [ ] Update Phase 1 to include semaphore implementation

#### Impact on Phases
- Phase 1: Add Bug 10 — concurrency control with asyncio.Semaphore(3) in handlers.py
