import asyncio
import sys
from app.config import settings
from app.utils.logging_config import configure_logging, logger
from app.cache.redis_client import redis_client
from app.scanner.dexscreener import dex_client
from app.alerts.telegram import telegram_service
from app.db.models import init_db
from app.scheduler import scheduler

async def main():
    # 1. Config & Logging
    configure_logging()
    logger.info("Starting Meme Coin Analysis Platform", env=settings.ENV)

    # 2. Infrastructure Init
    await redis_client.connect()
    await dex_client.start()
    await init_db()

    # 3. Start Telegram Bot & Notify
    await telegram_service.start()
    await telegram_service.send_startup_message()

    # 4. Start Scheduler
    try:
        await scheduler.start()
    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        await scheduler.stop()
        await telegram_service.stop()
        await dex_client.close()
        await redis_client.close()

if __name__ == "__main__":
    try:
        # if sys.platform == 'win32':
        #      asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
