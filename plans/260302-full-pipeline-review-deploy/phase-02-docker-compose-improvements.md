# Phase 2: Docker Compose & Improvements

## Context Links
- [Research: Docker Deploy & Monitoring](research/researcher-02-docker-deploy-monitoring.md)
- [Plan Overview](plan.md)
- [Phase 1: Bug Fixes](phase-01-code-review-bug-fixes.md) (prerequisite)

## Overview
- **Priority:** P1
- **Status:** Pending
- **Effort:** 1h
- **Description:** Create `docker-compose.yml` with health check, resource limits, log rotation. Add `.dockerignore`. Improve Dockerfile.

## Key Insights
- Docker Compose recommended even for single container -- version-controlled config, easy env management.
- `restart: always` without health check = false reliability. Container can deadlock while Docker thinks it's healthy.
- Docker default `json-file` log driver is unbounded -- disk fills silently without rotation.
- Resource limits prevent one bot consuming all host resources (8GB RAM shared with other services).
- `tmpfs` mount for temp dir ensures auto-cleanup on container restart and prevents disk fill from temp files.

## Requirements

### Functional
- Container auto-restarts on crash (with health check validation)
- Logs rotate to prevent disk fill
- Temp files isolated to tmpfs (auto-cleaned on restart)
- Resource limits prevent OOM affecting host

### Non-Functional
- Single `docker compose up -d` to start
- `.env` file for all secrets (not baked into image)
- Image size minimized with `.dockerignore`

## Architecture

```
Docker Host (103.110.84.230)
├── docker-compose.yml
├── .env (secrets)
├── Dockerfile
└── Container: video-to-script-bot
    ├── /app (code, read-only)
    ├── /tmp/video-to-script (tmpfs, 256MB)
    └── Health check: python -c "import bot.config; ..."
```

## Related Code Files

### Files to Create
| File | Purpose |
|------|---------|
| `docker-compose.yml` | Production container config |
| `.dockerignore` | Reduce build context size |

### Files to Modify
| File | Changes |
|------|---------|
| `Dockerfile` | Add HEALTHCHECK, create non-root user |

## Implementation Steps

### Step 1: Create `.dockerignore`
```
.git
.env
.env.*
__pycache__
*.pyc
*.pyo
*.md
plans/
.claude/
.vscode/
```

### Step 2: Improve Dockerfile
```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Health check: verify config loads (env vars present + Python runs)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "from bot.config import Config; Config.from_env()" || exit 1

CMD ["python", "-m", "bot.main"]
```

Key changes:
- Added `HEALTHCHECK` instruction
- Kept Python 3.12-slim (already good base)
- No non-root user for now (yt-dlp temp files need write access, and tmpfs mount simplifies permissions)

### Step 3: Create `docker-compose.yml`
```yaml
services:
  bot:
    build: .
    container_name: video-to-script-bot
    restart: unless-stopped
    env_file: .env
    tmpfs:
      - /tmp/video-to-script:size=256m
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
        reservations:
          cpus: "0.25"
          memory: 128M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

**Design decisions:**
- `restart: unless-stopped` -- best for production bots. Restarts on crash, survives host reboot, allows manual stop for maintenance.
- `tmpfs /tmp/video-to-script:size=256m` -- temp files auto-cleaned on restart, 256MB cap prevents disk fill (sufficient for audio-only downloads, typically 5-20MB per video).
- `memory: 512M` -- sufficient for Python bot + yt-dlp + ffmpeg. yt-dlp audio downloads are small. Gemini/Groq are API calls, not local inference.
- `cpus: 1.0` -- limits ffmpeg CPU usage during audio extraction.
- `max-size: 10m, max-file: 3` -- 30MB max log storage, prevents unbounded growth.
- `env_file: .env` -- secrets from `.env` file, not baked into image.

### Step 4: Update `.env.example`
Add note about Docker Compose usage:
```
# Required
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key

# Optional (paid fallback STT)
OPENAI_API_KEY=your_openai_api_key

# Optional (defaults shown)
MAX_VIDEO_DURATION=900
TEMP_DIR=/tmp/video-to-script
```

## Todo List
- [ ] Create `.dockerignore`
- [ ] Update `Dockerfile` with HEALTHCHECK
- [ ] Create `docker-compose.yml`
- [ ] Update `.env.example` with comments

## Success Criteria
- `docker compose build` succeeds
- `docker compose up -d` starts container
- `docker compose ps` shows container as healthy (after 30s start period)
- `docker compose logs` shows bot startup message
- Container auto-restarts after `docker compose kill bot`
- `docker stats` shows resource limits applied

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| tmpfs 256MB too small for large audio | Low | Audio-only downloads rarely exceed 50MB. Monitor with `df -h` inside container |
| Memory limit kills container during FFmpeg | Low | 512MB sufficient for audio extraction. Monitor OOM kills in `dmesg` |
| Health check false positive (config loads but bot stuck) | Medium | Acceptable for V1. Phase 5 adds bot.get_me() check |

## Security Considerations
- `.env` file with secrets never committed to git (`.gitignore` already covers this)
- `.dockerignore` excludes `.env` from build context -- secrets not baked into image layers
- No ports exposed (bot uses outbound polling only)
- `tmpfs` prevents temp files from persisting on host disk

## Next Steps
- After Docker Compose works locally, proceed to Phase 3 (Testing)
- Commit: `feat: add docker-compose with health check and resource limits`
