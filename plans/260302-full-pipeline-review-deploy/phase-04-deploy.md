# Phase 4: Deploy

## Context Links
- [Plan Overview](plan.md)
- [Phase 3: Testing](phase-03-testing.md) (prerequisite)

## Overview
- **Priority:** P1
- **Status:** Pending
- **Effort:** 30m
- **Description:** Deploy to production VPS. Push code, create `.env`, build Docker image, run with `docker compose`, verify bot responds.

## Key Insights
- Repo already cloned on server at `/root/projects/telegram-video-to-script/`
- Docker v29.2.1 + Compose v5.0.2 already installed
- 8GB RAM, 54% disk free (54GB available) -- more than sufficient
- No CI/CD pipeline -- manual deploy via SSH + git pull + docker compose

## Requirements

### Functional
- Bot running on server, responding to Telegram messages
- Container auto-restarts on crash
- Health check passing

### Non-Functional
- Deploy takes < 15 minutes
- Zero downtime not required (single instance, acceptable for V1)

## Architecture

```
Developer Machine                    VPS (103.110.84.230)
    |                                    |
    | git push origin master             |
    |----------------------------------→ |
                                         | git pull
                                         | docker compose build
                                         | docker compose up -d
                                         |
                                    Container: video-to-script-bot
                                         ├── Polling Telegram API
                                         └── tmpfs /tmp/video-to-script
```

## Related Code Files

### Files to Create (on server only)
| File | Location | Purpose |
|------|----------|---------|
| `.env` | `/root/projects/telegram-video-to-script/.env` | Production secrets |

### Files Modified (from previous phases)
All changes from Phase 1-2 committed and pushed to `master`.

## Implementation Steps

### Step 1: Push Code to Remote

On developer machine:
```bash
git add -A
git commit -m "feat: bug fixes, docker-compose, monitoring"
git push origin master
```

### Step 2: SSH to Server & Pull

```bash
ssh root@103.110.84.230
cd /root/projects/telegram-video-to-script
git pull origin master
```

### Step 3: Create `.env` on Server

```bash
cat > .env << 'EOF'
TELEGRAM_BOT_TOKEN=<user provides>
GROQ_API_KEY=<user provides>
GEMINI_API_KEY=<user provides>
OPENAI_API_KEY=<user provides or empty>
MAX_VIDEO_DURATION=900
TEMP_DIR=/tmp/video-to-script
EOF
chmod 600 .env
```

**IMPORTANT:** User must provide actual API keys. Do NOT commit `.env` to git.

### Step 4: Build Docker Image

```bash
docker compose build
```

Expected output: successful build, ~300MB image (python:3.12-slim + ffmpeg + pip packages).

### Step 5: Start Container

```bash
docker compose up -d
```

### Step 6: Verify Deployment

```bash
# Check container status
docker compose ps
# Expected: video-to-script-bot  running (healthy)

# Check logs
docker compose logs --tail 50
# Expected: "Bot started" message

# Check resource usage
docker stats --no-stream video-to-script-bot

# Check health
docker inspect video-to-script-bot --format='{{.State.Health.Status}}'
# Expected: healthy
```

### Step 7: Test Bot in Telegram

Send a YouTube URL to the bot. Verify it responds with formatted script.

### Step 8: Verify Cleanup

```bash
# After processing, check temp files are cleaned
docker exec video-to-script-bot ls /tmp/video-to-script/
# Expected: empty or only current processing files
```

## Todo List
- [ ] Push all code changes to `master`
- [ ] SSH to server, pull latest code
- [ ] Create `.env` with real API keys
- [ ] `docker compose build`
- [ ] `docker compose up -d`
- [ ] Verify container healthy
- [ ] Test bot with real Telegram message
- [ ] Verify temp file cleanup on server

## Success Criteria
- Container status: `running (healthy)`
- Bot responds to YouTube URL within 60 seconds
- Bot responds to TikTok URL within 60 seconds
- `docker compose logs` shows no errors
- Temp directory clean after processing

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| API keys incorrect | High | Test each key individually before deploying |
| Docker build fails on ARM | N/A | Server is x86_64, same arch as dev machine |
| Port conflict | N/A | Bot uses outbound polling, no ports exposed |
| Disk space during build | Low | 54GB free, build needs ~500MB |
| Old container still running | Medium | Run `docker compose down` before `up` |

## Security Considerations
- `.env` file: `chmod 600` -- only root can read
- No ports exposed to internet (outbound polling only)
- API keys in environment variables, not in image layers
- `.dockerignore` excludes `.env` from build context

## Next Steps
- After successful deploy, proceed to Phase 5 (Monitoring)
- If deploy fails, check logs with `docker compose logs` and fix
