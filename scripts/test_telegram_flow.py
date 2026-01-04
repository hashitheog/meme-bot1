import asyncio
import sys
import logging
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.utils.logging_config import configure_logging, logger
from app.paper_trader import paper_trader
from app.alerts.telegram import telegram_service

# Configure logging to show info
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mock Tokens
TOKENS = [
    {
        "id": "token_a",
        "data": {
            "chainId": "solana",
            "pairAddress": "TokenA_Address_123",
            "baseToken": {"address": "TokenA_Mint", "name": "Super Saiyan Doge", "symbol": "SSDOGE"},
            "liquidity": {"usd": 250000},
            "priceUsd": "0.000123",
            "marketCap": 123000
        },
        "analysis": {
            "ai_risk_score": 15, # Low risk
            "summary": "Strong community, clean contract, high liquidity. Verified safely.",
            "verdict": "BUY"
        },
        "score": 85
    },
    {
        "id": "token_b",
        "data": {
            "chainId": "solana",
            "pairAddress": "TokenB_Address_456",
            "baseToken": {"address": "TokenB_Mint", "name": "Rug Pull Inu", "symbol": "RUG"},
            "liquidity": {"usd": 5000}, # Low liq
            "priceUsd": "0.0000001",
            "marketCap": 5000
        },
        "analysis": {
            "ai_risk_score": 95, # High risk
            "summary": "Liquidity unlocked, owner holds 90%, honeypot detected.",
            "verdict": "AVOID"
        },
        "score": 10
    },
    {
        "id": "token_c",
        "data": {
            "chainId": "solana",
            "pairAddress": "TokenC_Address_789",
            "baseToken": {"address": "TokenC_Mint", "name": "Galactic Pepe", "symbol": "GPEPE"},
            "liquidity": {"usd": 500000},
            "priceUsd": "0.005",
            "marketCap": 5000000
        },
        "analysis": {
            "ai_risk_score": 20,
            "summary": "Massive volume, trending on socials, contract renounced.",
            "verdict": "BUY"
        },
        "score": 92
    }
]

async def run_simulation():
    print("----------------------------------------------------------------")
    print("🤖 STARTING TELEGRAM FLOW SIMULATION")
    print("----------------------------------------------------------------")
    print("1. Starting Telegram Service...")
    await telegram_service.start()
    
    # Send startup message
    await telegram_service.send_startup_message()
    
    # Process Tokens
    print("\n2. Processing Mock Tokens...")
    # Process Tokens
    print("\n2. Processing Mock Tokens...")
    from app.paper_trader import safe_trader, degen_trader
    
    for t in TOKENS:
        print(f"\nProcessing {t['data']['baseToken']['symbol']}...")
        await asyncio.sleep(2) 
        
        # Determine Strategy mimic logic
        # Token A & C are Safe (High Score, clean) -> Strategy 1
        # Token B is Risky (we need to boost its score for this test) -> Strategy 2
        
        score = t['score']
        # Force modify Token B to test Degen Mode
        if t['id'] == 'token_b':
             score = 85 # Boost score
             t['analysis']['verdict'] = "CAUTION"
             t['analysis']['summary'] = "Mintable but high viral potential."
        
        # Logic: 
        # Safe: Score >= 80 AND Safe (Tokens A, C)
        # Degen: Score >= 80 AND Risky (Token B)
        
        if score >= 80:
            trade = None
            strategy = "Unknown"
            
            if t['id'] == 'token_b': # Simulating FAILED Advanced Filter
                 print(f"   🎰 DEGEN DETECTED (Score {score}) -> Strategy 2")
                 strategy = "Degen Sword ⚔️"
                 trade = degen_trader.process_signal(t['data'], t['analysis'])
                 await telegram_service.send_alert(t['data'], score, t['analysis'], paper_trade=trade, strategy_name=strategy)
            else:
                 print(f"   🛡️ SAFE GEM (Score {score}) -> Strategy 1")
                 strategy = "Safe Shield 🛡️"
                 trade = safe_trader.process_signal(t['data'], t['analysis'])
                 await telegram_service.send_alert(t['data'], score, t['analysis'], paper_trade=trade, strategy_name=strategy)

        else:
            print(f"   ❌ Score {score} -> Skipped")

    print("\n----------------------------------------------------------------")
    print("✅ SIMULATION BATCH COMPLETE")
    print("----------------------------------------------------------------")
    print("The bot is now running in MAIN LOOP mode.")
    print("👉 OPEN TELEGRAM NOW.")
    print("👉 Try commands: /balance, /active, /stats")
    print("👉 Press Ctrl+C in this terminal to stop.")
    print("----------------------------------------------------------------")

    # Infinite loop to keep bot alive for commands
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        print("Stopping...")
    finally:
        await telegram_service.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(run_simulation())
    except KeyboardInterrupt:
        pass
