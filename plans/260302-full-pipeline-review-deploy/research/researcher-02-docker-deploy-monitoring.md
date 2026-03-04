# Docker Deployment & Monitoring Research Report
**Date:** 2026-03-02 | **Focus:** Python Telegram bot + yt-dlp on Ubuntu 22.04 VPS

---

## 1. Docker Best Practices for Python Bots

### Health Checks (Critical)
- **Interval:** 30-60 seconds balances detection speed vs resource overhead
- **Check type:** Command-based preferred for bots (test actual functionality, not just process alive)
- **Without health check:** Container can deadlock/OOM while Docker thinks it's healthy
- **Restart + health check combo:** Essential. `restart:always` alone = false reliability

### Restart Policies
| Policy | Use Case |
|--------|----------|
| `always` | Never appropriate without health check |
| `unless-stopped` | **Best for production** - reliable + allows maintenance |
| `on-failure` | For batch jobs, not persistent bots |

**Implementation:** Combine with resource limits to prevent cascade failures when bot loops.

### Resource Limits
```yaml
# CPU limit prevents one bot consuming all host resources
# Memory limit prevents OOM from affecting other containers
limits:
  cpus: '1'
  memory: 512M
reservations:  # Guaranteed minimum
  cpus: '0.5'
  memory: 256M
```

### Log Rotation (Missing from many bots)
- Docker default `json-file` driver unbounded = disk fills silently
- Use `--log-opt max-size=10m --log-opt max-file=3` to prevent 100GB logs
- Consider `splunk` or `awslogs` driver for centralized logging

---

## 2. Docker Compose vs Standalone Docker

### Single-Container Bot Decision:
| Aspect | Standalone Docker | Docker Compose |
|--------|------------------|-----------------|
| Setup complexity | Simpler for 1 container | Extra YAML |
| Future scaling | Hard to add services | Easy (add to compose file) |
| CLI verbosity | Long `docker run` commands | `docker-compose up` |
| Recommended? | Only if truly isolated | **Better choice** even for 1 container |

**Practical recommendation:** Use Docker Compose even for single bot. Enables:
- Easy addition of: monitoring sidecar, log aggregator, health check service
- Version-controlled deployment config
- Environment variable management (`.env` files)
- Network isolation from host

---

## 3. yt-dlp in Docker: Disk Space & FFmpeg

### Critical Issue: Temporary Files
- **FFmpeg merging doubles disk usage:**
  - Video: 22GB (temp) + Audio: 3GB (temp) + Merged: 25GB (final) = **50GB need, only 25GB final**
  - Interrupted downloads = lingering temp files consuming space

**Solutions:**
1. Specify separate `--temp-directory` for incomplete files on larger partition
2. Implement cleanup script: `trap "rm -rf /tmp/yt-dlp/*" EXIT` in entrypoint
3. Use `tmpfs` volume for small temp dir (limits runaway downloads)

### Docker Setup
```dockerfile
# Multi-stage build to keep final image lean
FROM python:3.11-slim as base
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install yt-dlp

# Mount points:
# /downloads - final output
# /temp - for --temp-directory (separate partition if possible)
```

### Volume Strategy
```yaml
volumes:
  - /data/videos:/downloads
  - /tmp/yt-dlp-temp:/temp  # On different partition if available
```

---

## 4. Monitoring Telegram Bots (Lightweight)

### Pattern 1: Periodic Self-Check (Built-in)
```python
async def health_check():
    try:
        me = await bot.get_me()  # Verify bot token works
        logger.info(f"Health check passed: {me.username}")
        return True
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False
```
Schedule every 5 min. If 3 failures → restart container.

### Pattern 2: External Monitoring (Simplest)
- Deploy separate lightweight bot: sends test message to main bot every 5 min
- If no response → sends alert to ops channel
- **Cost:** Single extra tiny container

### Pattern 3: Healthchecks.io Integration
- Webhook ping every N minutes to healthchecks.io
- Configurable Telegram notification on failure
- Free tier: 20 checks

### Logs Without Heavy Tools
- `docker logs -f --tail 100` for real-time (dev)
- `journalctl -u docker --since "1 hour ago"` for system logs
- `--log-opt splunk-insecure=true` sends to Splunk (but Splunk costs)
- **Simple solution:** `docker logs > /var/log/bot.log 2>&1` + logrotate

**Recommended:** Combination:
1. Built-in health check (command runs every 30s)
2. Docker restart policy (`unless-stopped`)
3. Simple file logging with rotation
4. Optional: Separate monitoring bot for Telegram notifications

---

## 5. yt-dlp Auto-Update Strategy

### Problem: Sites change extractor constantly
- yt-dlp has built-in self-update mechanism
- But Docker containers run fixed snapshots → updates won't apply

### Solution 1: Weekly Rebuild (Production-Safe)
```dockerfile
# In CI/CD: weekly scheduled rebuild with latest yt-dlp
# - More stable (test before deploy)
# - Updates on schedule, not ad-hoc failures
```

### Solution 2: Runtime Update Check (Risky but responsive)
```python
import subprocess
import logging

async def check_yt_dlp_version():
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True)
        version = result.stdout.strip()
        logging.info(f"yt-dlp version: {version}")

        # Optional: trigger update
        # subprocess.run(['yt-dlp', '-U'])  # Self-update
    except Exception as e:
        logging.error(f"Version check failed: {e}")
```

### Solution 3: Multi-Stage CI/CD
1. Daily: Build new Docker image if yt-dlp has update
2. Test image locally (1-2 hours)
3. Deploy to prod if tests pass
4. Publish built image to Docker Hub for reuse

**Recommended:** Solution 1 (weekly scheduled rebuild)
- Best balance: automatic, safe, predictable downtime
- Add `--version` to health check to log current yt-dlp version
- Set up daily GitHub Actions to rebuild if update available

---

## 6. Integration Roadmap

**Container configuration (day 1):**
1. Compose file with health check command
2. Resource limits (CPU 1, memory 512M)
3. Restart: unless-stopped
4. Log rotation config
5. Volume mounts for downloads & temp space

**Monitoring setup (day 2):**
1. Health check procedure in bot code (get_me + logging)
2. File-based logging with logrotate
3. Optional: monitoring bot sidecar for Telegram notifications

**yt-dlp updates (day 3):**
1. Weekly scheduled rebuild in CI/CD
2. Separate download/temp volumes with size monitoring
3. Cleanup trap in entrypoint

---

## Key Actionable Takeaways

1. **Don't skip health checks** - restart:always alone ≠ reliability
2. **Temp disk space = sneaky issue** - FFmpeg merging triples space needs
3. **Docker Compose scales up gracefully** - use it even for 1 container
4. **Monitoring = alerting** - health check without notification = useless
5. **Auto-updates via CI/CD > runtime updates** - more stable, testable

---

## Sources
- [Docker Health Check Best Practices (Oneuptime, 2026)](https://oneuptime.com/blog/post/2026-01-30-docker-health-check-best-practices/view)
- [Docker Production Best Practices (Mykola Aleksandrov, 2026)](https://www.mykolaaleksandrov.dev/posts/2026/02/docker-production-best-practices/)
- [Docker Restart Policies Guide (TechEduByte)](https://www.techedubyte.com/docker-restart-policies-complete-guide-4-strategies/)
- [yt-dlp Docker Images (Hub.docker.com)](https://hub.docker.com/r/tnk4on/yt-dlp)
- [yt-dlp GitHub Issues (Disk/Temp Management)](https://github.com/yt-dlp/yt-dlp/issues/14042)
- [Healthchecks.io Telegram Integration](https://healthchecks.io/integrations/telegram/)
