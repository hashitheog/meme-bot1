import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.logging_config import configure_logging, logger
from app.scanner.stealth_scraper import stealth_scraper

async def test_scraper():
    configure_logging()
    logger.info("🕷️ STARTING SCRAPER TEST")
    
    try:
        logger.info("Fetching new pairs from DexScreener...")
        pairs = await stealth_scraper.fetch_new_pairs()
        
        if pairs:
            logger.info(f"✅ Scraper Success! Found {len(pairs)} pairs.")
            for p in pairs[:3]:
                logger.info(f"Sample: {p['baseToken']['symbol']} ({p['pairAddress']})")
        else:
            logger.warning("⚠️ Scraper ran but found 0 pairs. Check screenshot if saved.")
            
    except Exception as e:
        logger.error(f"❌ Scraper Failed: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
       asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(test_scraper())
