# Phase 3: Testing

## Context Links
- [Plan Overview](plan.md)
- [Phase 1: Bug Fixes](phase-01-code-review-bug-fixes.md) (prerequisite)
- [Phase 2: Docker Compose](phase-02-docker-compose-improvements.md) (prerequisite)

## Overview
- **Priority:** P1
- **Status:** Pending
- **Effort:** 30m
- **Description:** Manual integration testing with real URLs. Verify all 3 STT tiers, error handling, temp file cleanup, and Docker health check.

## Key Insights
- Unit tests have limited value here -- most logic is I/O-bound (API calls, file downloads). Integration tests with real URLs are more valuable.
- Testing locally first (without Docker) catches code bugs faster. Then Docker test verifies containerization.
- Must test with videos that have subtitles AND videos that don't, to exercise all STT tiers.

## Requirements

### Functional
- All 3 STT tiers produce valid output
- Temp files cleaned after each test
- Error messages shown to user on failures
- Docker container stays healthy under load

### Non-Functional
- Test with real Telegram bot (not mocked)
- Test takes < 30 minutes total

## Architecture
No changes. Testing existing architecture.

## Related Code Files
No new files. Testing existing codebase after Phase 1 and 2 changes.

## Implementation Steps

### Step 1: Local Smoke Test (no Docker)

1. Create `.env` with real API keys
2. Run `python -m bot.main`
3. Send test messages to bot in Telegram:

| Test | Input | Expected |
|------|-------|----------|
| YouTube with subs | `https://youtube.com/watch?v=dQw4w9WgXcQ` | Uses Tier 1 (subtitles), returns formatted script |
| YouTube Shorts | `https://youtube.com/shorts/<any_shorts_id>` | Works, any tier |
| TikTok | `https://tiktok.com/@<user>/video/<id>` | Uses Tier 2 (Groq) since TikTok has no subs |
| Long video (>15min) | Any video >15 min | Error: "Video qua dai" |
| Invalid URL | `hello world` | Bot ignores (no response) |
| Invalid video URL | `https://youtube.com/watch?v=INVALID123` | Error: "Co loi xay ra" |

### Step 2: Verify Temp File Cleanup

After each test:
```bash
ls /tmp/video-to-script/
# Should be empty after processing completes
```

### Step 3: Verify STT Tiers

To test each tier explicitly:
- **Tier 1 (Subtitles):** YouTube video with known captions. Log should say "Using YouTube subtitles".
- **Tier 2 (Groq):** TikTok video (no subs available). Log should say "Using Groq Whisper".
- **Tier 3 (OpenAI):** Temporarily set `GROQ_API_KEY` to invalid value. Should fall back to OpenAI. Log should say "Using OpenAI Whisper".

### Step 4: Docker Build & Run Test

```bash
docker compose build
docker compose up -d
docker compose ps          # Should show "healthy" after 30s
docker compose logs -f     # Watch for startup message
```

Send same test messages again. Verify identical behavior to local test.

```bash
# Verify health check
docker inspect video-to-script-bot --format='{{.State.Health.Status}}'
# Should output: healthy

# Verify resource limits
docker stats --no-stream video-to-script-bot
# Should show MEM LIMIT = 512MiB

# Verify tmpfs
docker exec video-to-script-bot df -h /tmp/video-to-script
# Should show tmpfs mount
```

### Step 5: Error Recovery Test

```bash
# Kill and verify auto-restart
docker compose kill bot
sleep 5
docker compose ps  # Should show container restarted
```

## Todo List
- [ ] Local smoke test with 4 URL types
- [ ] Verify temp file cleanup after each test
- [ ] Verify each STT tier logs correctly
- [ ] Docker build and run
- [ ] Docker health check verification
- [ ] Error recovery (kill + auto-restart) test

## Success Criteria
- All 4 URL types produce valid output
- Temp directory empty after each processing
- Log messages correctly identify which STT tier was used
- Docker container shows "healthy" status
- Container auto-restarts after kill

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| API rate limits during testing | Low | Space tests 10s apart. Use short videos (<2min) |
| TikTok URL blocked by yt-dlp | Medium | Try multiple TikTok URLs. Some regions block TikTok |
| Groq API key not activated | Low | Check Groq dashboard before testing |

## Security Considerations
- Use test API keys or rate-limited keys for testing
- Don't commit `.env` with real keys
- Test on local machine, not production server

## Next Steps
- If all tests pass, proceed to Phase 4 (Deploy)
- If any test fails, return to Phase 1 to fix the issue
