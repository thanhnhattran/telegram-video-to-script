# Phase 5: Monitoring

## Context Links
- [Research: Docker & Monitoring](research/researcher-02-docker-deploy-monitoring.md)
- [Plan Overview](plan.md)
- [Phase 2: Docker Compose](phase-02-docker-compose-improvements.md) (health check already added)

## Overview
- **Priority:** P2
- **Status:** Pending
- **Effort:** 30m
- **Description:** Add `/status` command to bot for manual health checking. Enhance Docker health check to verify actual bot connectivity. Setup log monitoring on server.

## Key Insights
- Docker HEALTHCHECK in Phase 2 only verifies config loads (env vars present). It doesn't verify bot can reach Telegram API.
- A `/status` command lets admins check bot health via Telegram itself -- zero infrastructure needed.
- Log rotation already configured in `docker-compose.yml` (10MB x 3 files).
- Heavy monitoring tools (Prometheus, Grafana) are overkill for single bot. KISS principle.

## Requirements

### Functional
- `/status` command shows: uptime, Python version, yt-dlp version, last processed video time
- Docker health check verifies bot token validity (calls `bot.get_me()`)

### Non-Functional
- No new services or containers
- No external monitoring dependencies

## Architecture

```
Admin sends /status → Bot responds with:
  - Uptime: 2d 3h 15m
  - yt-dlp: 2025.01.15
  - Last video: 5 min ago
  - Status: OK

Docker health check (every 30s):
  - python health_check.py
  - Verifies: config loads + Telegram API reachable
```

## Related Code Files

### Files to Create
| File | Purpose |
|------|---------|
| `health_check.py` | Standalone script for Docker HEALTHCHECK |

### Files to Modify
| File | Changes |
|------|---------|
| `bot/handlers.py` | Add `/status` command handler |
| `bot/main.py` | Track bot start time |
| `Dockerfile` | Update HEALTHCHECK to use `health_check.py` |

## Implementation Steps

### Step 1: Create `health_check.py`

Standalone script that Docker runs every 30s. Must exit 0 (healthy) or 1 (unhealthy).

```python
"""Docker health check script. Exits 0 if healthy, 1 if not."""
import asyncio
import sys
import os

async def check():
    try:
        from bot.config import Config
        config = Config.from_env()

        from aiogram import Bot
        bot = Bot(token=config.telegram_token)
        try:
            me = await bot.get_me()
            if me.username:
                return 0
        finally:
            await bot.session.close()
    except Exception:
        pass
    return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(check()))
```

**Design:** Creates a temporary Bot instance just to call `get_me()`. Lightweight (single API call). Verifies:
1. Config loads (env vars present)
2. Telegram token is valid
3. Network connectivity works

### Step 2: Update Dockerfile HEALTHCHECK

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python health_check.py || exit 1
```

- `start-period=15s`: Give bot time to start before first check
- `interval=30s`: Check every 30 seconds
- `retries=3`: 3 consecutive failures = unhealthy
- `timeout=10s`: Single check must complete within 10s

### Step 3: Add `/status` Command

In `bot/handlers.py`, add:

```python
import time

_start_time = time.time()
_last_processed: float | None = None

def mark_processed():
    global _last_processed
    _last_processed = time.time()
```

Add handler:
```python
@router.message(Command("status"))
async def cmd_status(message: types.Message) -> None:
    import subprocess
    import platform

    uptime_seconds = int(time.time() - _start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Get yt-dlp version
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"], capture_output=True, text=True, timeout=5
        )
        ytdlp_version = result.stdout.strip()
    except Exception:
        ytdlp_version = "unknown"

    last_video = "never"
    if _last_processed:
        ago = int(time.time() - _last_processed)
        if ago < 60:
            last_video = f"{ago}s ago"
        elif ago < 3600:
            last_video = f"{ago // 60}m ago"
        else:
            last_video = f"{ago // 3600}h ago"

    status_text = (
        f"Bot Status: OK\n"
        f"Uptime: {hours}h {minutes}m {seconds}s\n"
        f"Python: {platform.python_version()}\n"
        f"yt-dlp: {ytdlp_version}\n"
        f"Last video: {last_video}"
    )
    await message.answer(status_text)
```

### Step 4: Call `mark_processed()` in Handler

In `handle_message()` in `handlers.py`, after successful processing (after `await output_handler.send(...)`):
```python
mark_processed()
```

### Step 5: Server Log Monitoring (Optional)

Setup simple log check alias on server:
```bash
# Add to /root/.bashrc
alias bot-logs='docker compose -f /root/projects/telegram-video-to-script/docker-compose.yml logs --tail 100 -f'
alias bot-status='docker inspect video-to-script-bot --format="{{.State.Health.Status}}"'
alias bot-restart='docker compose -f /root/projects/telegram-video-to-script/docker-compose.yml restart'
```

## Todo List
- [ ] Create `health_check.py`
- [ ] Update Dockerfile HEALTHCHECK command
- [ ] Add `/status` command handler in `handlers.py`
- [ ] Add `mark_processed()` call in message handler
- [ ] Add `_start_time` and `_last_processed` module variables
- [ ] Test `/status` command locally
- [ ] Rebuild and deploy Docker image
- [ ] Setup server aliases (optional)

## Success Criteria
- `/status` returns uptime, versions, last processed time
- Docker health check shows "healthy" when bot is running
- Docker health check shows "unhealthy" when Telegram token is invalid
- `docker compose ps` shows health status

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| Health check creates too many `get_me()` calls | Low | 30s interval = 2880 calls/day, well within Telegram limits |
| `/status` exposes info to any user | Low | Only shows versions and uptime, no sensitive data. Can restrict to admin later |
| `subprocess.run` for yt-dlp version hangs | Low | `timeout=5` prevents hang |

## Security Considerations
- `/status` does not expose API keys, user data, or internal paths
- Health check uses same credentials as bot (no additional secrets)
- No new ports exposed

## Next Steps
- After monitoring setup, the full pipeline is complete
- Future improvements (not in scope):
  - Restrict `/status` to admin user IDs
  - Add external uptime monitoring (healthchecks.io)
  - Add processed video counter / daily stats
  - Weekly yt-dlp auto-update via Docker rebuild
