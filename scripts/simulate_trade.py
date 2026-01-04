import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.utils.logging_config import configure_logging, logger
from app.analysis.ai_scoring import ai_engine
from app.paper_trader import paper_trader
from app.alerts.telegram import telegram_service

# Mock Token Data simulating a "Gem"
MOCK_TOKEN = {
    "chainId": "solana",
    "pairAddress": "RunSimulatedPairAddress123",
    "baseToken": {
        "address": "SimulatedTokenAddress456",
        "name": "Super Gem Coin",
        "symbol": "GEM"
    },
    "liquidity": {
        "usd": 150000.00
    },
    "pairCreatedAt": 1700000000, # Old enough
    "info": {
        "socials": [
            {"type": "twitter", "url": "https://twitter.com/SuperGemCoin"},
            {"type": "telegram", "url": "https://t.me/SuperGemCoin"}
        ]
    }
}

async def run_simulation():
    configure_logging()
    logger.info("🧪 STARTING SUCCESSFUL TRADE SIMULATION")

    # 1. Initialize Services
    logger.info("...Initializing Telegram Bot...")
    await telegram_service.start()
    
    # 2. Simulate AI Analysis
    logger.info("...Running AI Analysis on Mock Token...")
    # Force a high score via mock? Or let real AI analyze the mock data?
    # Real AI might give low score because data is fake/shallow.
    # We will wrap it or trust the prompt.
    # To Ensure success, let's manually constructing a High Score Result if AI fails?
    # No, let's try the real AI first. The prompt should handle it.
    # Actually, AI reads 'risk' from data. If fields are missing it might flag it.
    # Let's populate mock data well.
    
    analysis_result = await ai_engine.analyze_token(MOCK_TOKEN)
    logger.info(f"AI Result: {analysis_result}")
    
    # Override for simulation purposes if AI is skeptical of the fake data
    if analysis_result.get("ai_risk_score", 100) > 30:
        logger.warning("AI was skeptical (expected for fake data). forcing VALIDATION for simulation.")
        analysis_result = {
            "ai_risk_score": 10,
            "ai_confidence": 0.95,
            "risk_flags": [],
            "positive_signals": ["High Liquidity", "Active Socials", "Simulation Mode"],
            "summary": "This is a SIMULATED perfect trade setup. Strong fundamentals detected.",
            "verdict": "PASS"
        }

    score = analysis_result["ai_risk_score"]
    
    # 3. Trigger Alert
    logger.info(f"...Sending Telegram Alert (Score: {score})...")
    
    # 4. Execute Paper Trade
    logger.info("...Executing Paper Byte...")
    trade = paper_trader.process_signal(MOCK_TOKEN, analysis_result)
    
    if trade:
        logger.info(f"✅ Trade Opened: {trade.symbol} at ${trade.entry_mc}")
        await telegram_service.send_alert(MOCK_TOKEN, score, analysis_result, paper_trade=trade)
    else:
        logger.error("❌ Trade Failed to Open")

    logger.info("Simulation Complete. Check your Telegram!")
    await telegram_service.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_simulation())
