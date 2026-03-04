"""Docker health check script. Exits 0 if healthy, 1 if not."""
import asyncio
import sys


async def check() -> int:
    try:
        from bot.config import Config
        config = Config.from_env()

        from aiogram import Bot
        from aiogram.client.session.aiohttp import AiohttpSession
        session = AiohttpSession(api=config.telegram_api_url)
        bot = Bot(token=config.telegram_token, session=session)
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
