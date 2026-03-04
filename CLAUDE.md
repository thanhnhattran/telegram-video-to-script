# Telegram Video-to-Script Bot

## Project Overview
Telegram bot nhận URL video (TikTok/YouTube/Shorts) → trả về script có cấu trúc.

## Tech Stack
- **Language:** Python 3.10+
- **Bot Framework:** python-telegram-bot
- **STT:** YouTube subs → Groq Whisper → OpenAI Whisper (3-tier fallback)
- **AI Formatting:** Gemini API
- **Deploy:** Docker

## Deployment

### Server Info
- **Host:** `103.110.84.230`
- **User:** `root`
- **SSH:** Dùng SSH key local (không cần password)
- **OS:** Ubuntu 22.04 (Linux 5.15.0)
- **Hostname:** `onefix-relay.local`

### Server Resources
- **RAM:** 8GB (available ~3.4GB)
- **Disk:** 100GB (used 46%, available ~52GB)
- **Docker:** v29.2.1 + Compose v5.0.2

### Project Path on Server
```
/root/projects/telegram-video-to-script/
```

### Deploy Commands
```bash
# SSH vào server
ssh root@103.110.84.230

# Pull latest code
cd /root/projects/telegram-video-to-script
git pull origin master

# Build & run with Docker
docker build -t video-to-script .
docker run -d --env-file .env --name video-to-script --restart unless-stopped video-to-script

# Hoặc rebuild
docker stop video-to-script && docker rm video-to-script
docker build -t video-to-script .
docker run -d --env-file .env --name video-to-script --restart unless-stopped video-to-script

# Xem logs
docker logs -f video-to-script
```

### Environment Variables
Tạo file `.env` trên server tại `/root/projects/telegram-video-to-script/.env` với các keys:
- `TELEGRAM_BOT_TOKEN`
- `GROQ_API_KEY`
- `GEMINI_API_KEY`
- `OPENAI_API_KEY` (optional)

## Project Structure
```
bot/           # Telegram bot core (main, handlers, config)
services/      # Business logic (downloader, transcriber, formatter, output)
utils/         # Helpers (url_parser, text_utils)
Dockerfile     # Docker build
requirements.txt
```
