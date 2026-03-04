import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import ErrorEvent
from dotenv import load_dotenv

from bot.config import Config
from bot.handlers import router

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    config = Config.from_env()
    os.makedirs(config.temp_dir, exist_ok=True)

    session = AiohttpSession(api=config.telegram_api_url)
    bot = Bot(token=config.telegram_token, session=session)
    dp = Dispatcher()
    dp["config"] = config
    dp.include_router(router)

    @dp.error()
    async def on_error(event: ErrorEvent) -> bool:
        logger.exception("Unhandled error: %s", event.exception)
        if event.update and event.update.message:
            try:
                await event.update.message.answer(
                    "Loi he thong. Vui long thu lai sau."
                )
            except Exception:
                pass
        return True

    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
