import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import Database
from middlewares.throttling import ThrottlingMiddleware
from middlewares.auth import AuthMiddleware
from handlers.admin import admin_router
from handlers.start import start_router
from handlers.menu import menu_router
from handlers.study import study_router
from handlers.practice import practice_router

async def init_bot() -> Bot:
    """Initialize bot instance."""
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    return bot

async def main():
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Init DB
    logger.info("Initializing database...")
    await Database.init_db()

    bot = await init_bot()
    dp = Dispatcher()
    
    # -------------------------------------------------------------
    # Register Middlewares
    # -------------------------------------------------------------
    # System evaluates limits first, and overrides messages
    dp.message.middleware(ThrottlingMiddleware(limit=30))
    dp.message.outer_middleware(AuthMiddleware())
    dp.callback_query.outer_middleware(AuthMiddleware())
    
    # -------------------------------------------------------------
    # Register Routers (Blueprints)
    # -------------------------------------------------------------
    dp.include_routers(
        start_router,
        admin_router,
        menu_router,
        study_router,
        practice_router
    )
    
    logger.info("Starting polling...")
    try:
        # Skip previously sent updates to avoid processing old messages
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Failed to start polling: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped correctly.")
