import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.utils.logging_config import configure_logging, logger
from app.cache.redis_client import redis_client
from app.analysis.onchain import OnChainAnalyzer
from app.analysis.ai_scoring import ai_engine
from app.analysis.social import SocialAnalyzer
from app.alerts.telegram import telegram_service

configure_logging()

async def check_redis():
    logger.info("--- Checking Redis ---")
    try:
        await redis_client.connect()
        logger.info("✅ Redis Connected")
        await redis_client.close()
    except Exception as e:
        logger.error(f"❌ Redis Failed: {e}")

async def check_ai():
    provider = settings.AI_PROVIDER.upper()
    logger.info(f"--- Checking AI ({provider}) ---")
    
    key = settings.DEEPSEEK_API_KEY if provider == "DEEPSEEK" else (settings.OPENAI_API_KEY if provider == "OPENAI" else settings.GEMINI_API_KEY)

    if not key:
        logger.warning(f"⚠️ No API KEY found for {provider}.")
        # Continue anyway to test if it fails gracefully or if env var was just missed in this check but present in os
    
    try:
        # Mock simple input
        res = await ai_engine.analyze_token({
            "token_name": "TestToken",
            "symbol": "TEST", 
            "liquidity_usd": 50000
        })
        if res.get("ai_risk_score") is not None:
             logger.info(f"✅ AI ({provider}) Working. Risk Score for Test: {res.get('ai_risk_score')}")
        else:
             logger.error(f"❌ AI Response Invalid: {res}")
    except Exception as e:
        logger.error(f"❌ AI Failed: {e}")

async def check_goplus():
    logger.info("--- Checking GoPlus Security ---")
    # Check USDT on Ethereum (Safe known contract)
    usdt_eth = "0xdac17f958d2ee523a2206206994597c13d831ec7"
    try:
        analyzer = OnChainAnalyzer()
        res = await analyzer.analyze("ethereum", usdt_eth)
        if res.get("contract_verified"):
            logger.info("✅ GoPlus Working (Verified USDT)")
        else:
            logger.warning("⚠️ GoPlus returned unexpected data for USDT")
    except Exception as e:
        logger.error(f"❌ GoPlus Failed: {e}")

async def check_telegram():
    logger.info("--- Checking Telegram ---")
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("⚠️ Telegram Config Missing")
        return
    
    # We won't send a real message to 'spam' the user, 
    # but we can check getMe or just trust the config if init didn't fail.
    # telegram_alerter init doesn't make net calls. 
    # Let's try get_me if possible or a silent message? 
    # Safer to just log that config exists.
    logger.info("✅ Telegram Configured")

async def check_social():
    logger.info("--- Checking Nitter Scraper (May take time) ---")
    try:
        analyzer = SocialAnalyzer()
        # Test with a known handle, e.g., 'Bitcoin'
        pair_data = {"info": {"socials": [{"type": "twitter", "url": "https://twitter.com/Bitcoin"}]}}
        
        # This is blocking inside, wrapped in asyncio.to_thread in the real class
        # But here let's run it.
        logger.info("Scraping @Bitcoin...")
        res = await analyzer.analyze(pair_data)
        if res["twitter"]["exists"]:
            logger.info(f"✅ Nitter Scraper Working. @Bitcoin followers: {res['twitter'].get('followers')}")
        else:
            logger.warning("⚠️ Nitter failed to scrape @Bitcoin (might be instance rate limit)")
    except Exception as e:
        logger.error(f"❌ Social Scraper Failed: {e}")


async def main():
    logger.info("🚀 STARTING SYSTEM HEALTH CHECK")
    await check_redis()
    await check_goplus()
    await check_ai()
    await check_telegram()
    await check_social()
    logger.info("🏁 HEALTH CHECK COMPLETE")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
