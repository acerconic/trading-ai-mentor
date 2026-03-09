import asyncio
import logging
import os

from aiohttp import web
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

async def health_check(request):
    """Dummy health check endpoint for Render."""
    return web.Response(text="Bot is alive!")

async def start_dummy_server():
    """Starts a dummy aiohttp server to bind a port for Render."""
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Dummy web server started on http://0.0.0.0:{port}")

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
        # Start dummy web server for Render binding
        await start_dummy_server()
        
        # Skip previously sent updates to avoid processing old messages
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Failed to start polling: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        # Use uvloop if available (Linux/Render), otherwise standard asyncio
        try:
            import uvloop
            uvloop.run(main())
        except ImportError:
            asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped correctly.")
