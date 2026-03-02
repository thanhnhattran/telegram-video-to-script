# Telegram Video-to-Script Bot

Telegram bot chuyển video TikTok/YouTube Shorts/YouTube thành script đọc được.

## Features

- Nhận URL video → trả script có cấu trúc (headings, bullet points, key takeaways)
- Hỗ trợ: YouTube, YouTube Shorts, TikTok
- Ngôn ngữ: Tiếng Việt + Tiếng Anh
- STT pipeline 3 tầng: YouTube subs → Groq Whisper (free) → OpenAI Whisper (fallback)
- AI formatting bằng Gemini API
- Output thông minh: message ngắn hoặc file .md nếu dài

## Setup

```bash
# Clone
git clone https://github.com/thanhnhattran/telegram-video-to-script.git
cd telegram-video-to-script

# Install
pip install -r requirements.txt

# Config
cp .env.example .env
# Edit .env with your API keys

# Run
python -m bot.main
```

## Docker

```bash
docker build -t video-to-script .
docker run -d --env-file .env --name video-to-script video-to-script
```

## API Keys needed

| Key | Source | Cost |
|-----|--------|------|
| TELEGRAM_BOT_TOKEN | [@BotFather](https://t.me/BotFather) | Free |
| GROQ_API_KEY | [console.groq.com](https://console.groq.com) | Free tier |
| GEMINI_API_KEY | [aistudio.google.com](https://aistudio.google.com) | Free tier |
| OPENAI_API_KEY | [platform.openai.com](https://platform.openai.com) | $0.006/min (optional fallback) |
