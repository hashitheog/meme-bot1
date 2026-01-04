import asyncio
from datetime import datetime

from app.config import settings
from app.utils.logging_config import logger
from app.cache.redis_client import redis_client
from app.scanner.dexscreener import dex_client
from app.filters.early_filter import EarlyFilter
from app.filters.advanced_filter import AdvancedFilter
from app.filters.scoring import ScoringEngine
from app.analysis.social import SocialAnalyzer
from app.analysis.onchain import OnChainAnalyzer
from app.analysis.ai_scoring import ai_engine
from app.paper_trader import paper_trader
from app.alerts.telegram import telegram_service
from app.db.models import AsyncSessionLocal, Token

class Scheduler:
    def __init__(self):
        self.running = False
        self.social_analyzer = SocialAnalyzer()
        self.onchain_analyzer = OnChainAnalyzer()

    async def start(self):
        self.running = True
        logger.info("Scheduler started.")
        while self.running:
            try:
                await self.run_cycle()
                await self.update_paper_trades() # Update active trades
            except Exception as e:
                logger.error("Error in scheduler loop", error=str(e))
            
            # Poll every 15 seconds
            await asyncio.sleep(15)

    async def stop(self):
        self.running = False
        logger.info("Scheduler stopped.")

    async def update_paper_trades(self):
        """Fetch current prices for active paper trades"""
        if not paper_trader.active_trades:
            return
            
        current_data = {}
        for trade in paper_trader.active_trades:
            # Fetch latest data
            pair_data = await dex_client.fetch_pair_data(trade.chain, trade.token_address)
            if pair_data:
                # Use FDV or Liquidity or Price?
                # V3 Strategy uses Market Cap logic. DexScreener provides 'fdv' or 'marketCap'.
                mc = pair_data.get("marketCap") or pair_data.get("fdv", 0)
                if mc:
                    current_data[trade.token_address] = mc
        
        # Run Update Logic
        updates = paper_trader.update_trades(current_data)
        
        # Notify Telegram of Exits/TPs
        for update in updates:
            type_ = update[0]
            trade = update[1]
            extra = update[2] if len(update) > 2 else None
            await telegram_service.send_trade_update(type_, trade, extra)

    async def run_cycle(self):
        # logger.debug("Polling DexScreener...")
        # HYBRID MODE: Scrape new pair addresses -> Fetch API details
        from app.scanner.stealth_scraper import stealth_scraper
        
        # 1. Scrape Addresses (Fast, Stealth)
        try:
            scraped_pairs = await stealth_scraper.fetch_new_pairs()
            logger.info(f"Stealth Scraper found {len(scraped_pairs)} pairs")
        except Exception as e:
            logger.error("Scraper loop failed", error=str(e))
            scraped_pairs = []

        # 2. Fetch Full API Data for each
        tasks = []
        for p in scraped_pairs:
            tasks.append(self.process_scraped_pair(p))
            
        if not scraped_pairs:
             # Fallback to API search if scraper fails or finds nothing
             logger.warning("Scraper yielded no results. Falling back to simple API search.")
             pairs = await dex_client.fetch_latest_pairs() 
             for pair in pairs:
                 tasks.append(self.process_pair(pair))

        if tasks:
            # FREE TIER LIMIT STRICT: 15 RPM (Requests Per Minute)
            # We set Concurrency=1 and Sleep=5s -> 12 RPM (Safe)
            semaphore = asyncio.Semaphore(1)
            async def run_with_sem(coro):
                async with semaphore:
                    await coro
                    await asyncio.sleep(5) 
            
            await asyncio.gather(*(run_with_sem(t) for t in tasks))

    async def process_scraped_pair(self, minimal_pair: dict):
        chain = minimal_pair.get("chainId")
        addr = minimal_pair.get("pairAddress")
        
        # Fetch detailed data
        full_pair = await dex_client.fetch_pair_data(chain, addr)
        if full_pair:
             await self.process_pair(full_pair)

    async def process_pair(self, pair: dict):
        base_token = pair.get("baseToken", {})
        address = base_token.get("address")
        chain = pair.get("chainId")
        
        if not address or not chain:
            return

        # 1. Deduplication
        if await redis_client.is_token_seen(chain, address):
            return
        
        logger.info("New pair detected", symbol=base_token.get("symbol"), address=address)
        
        # 2. Early Filter
        passed, reason = EarlyFilter.inspect(pair)
        if not passed:
            logger.debug("Early filter rejected", symbol=base_token.get("symbol"), reason=reason)
            await redis_client.mark_token_seen(chain, address, ttl=3600)
            return

        # 3. Deep Analysis (On-Chain + Social)
        onchain_data, social_data = await asyncio.gather(
            self.onchain_analyzer.analyze(chain, address),
            self.social_analyzer.analyze(pair)
        )

        # 4. Advanced Filter
        adv_passed, adv_reason = await AdvancedFilter.inspect(pair, onchain_data)
        if not adv_passed:
            logger.info("Advanced filter rejected", symbol=base_token.get("symbol"), reason=adv_reason)
            await redis_client.mark_token_seen(chain, address)
            return

        # 5. AI Scoring
        ai_input = {
            "token_name": base_token.get("name"),
            "symbol": base_token.get("symbol"),
            "chain": chain,
            "liquidity_usd": pair.get("liquidity", {}).get("usd"),
            "holders_count": len(onchain_data.get("holders", [])),
            "dev_wallet_percent": 0,
            "twitter": social_data.get("twitter"),
            "telegram": social_data.get("telegram"),
            "website_text": social_data.get("website_text")
        }
        
        ai_result = await ai_engine.analyze_token(ai_input)
        ai_score = ai_result.get("ai_risk_score", 50)
        
        # 6. Final Score
        social_score = 50.0 
        final_score = ScoringEngine.calculate_score(adv_passed, ai_score, social_score)
        
        logger.info("Analysis complete", symbol=base_token.get("symbol"), score=final_score, ai_verdict=ai_result.get("verdict"))

        # 7. Persist & Alert
        await redis_client.mark_token_seen(chain, address)
        
        try:
            async with AsyncSessionLocal() as session:
                token_db = Token(
                    address=address,
                    chain=chain,
                    name=base_token.get("name", ""),
                    symbol=base_token.get("symbol", ""),
                    launch_age_minutes=0,
                    final_score=final_score,
                    ai_risk_score=ai_score,
                    analysis_data=ai_result,
                    is_alerted=(final_score >= 70)
                )
                await session.merge(token_db)
                await session.commit()
        except Exception as e:
            # Ignore integrity errors if merge fails somehow, or log carefully
            logger.error("DB Save failed", error=str(e))

        # 8. Alert & Paper Trade (Dual Strategy)
        trade = None
        strategy = None
        
        # Strategy 1: Safe Shield (Strict Rules)
        if final_score >= 80 and adv_passed:
            strategy = "Safe Shield 🛡️"
            trade = paper_trader.safe_trader.process_signal(pair, ai_result)
            await telegram_service.send_alert(pair, final_score, ai_result, paper_trade=trade, strategy_name=strategy)
            
        # Strategy 2: Degen Sword (Risky, but High AI Score)
        # Note: We use ai_score directly sometimes, or final_score? 
        # Advanced Filter failed, so final_score might be low depending on scoring engine.
        # Let's trust AI Score explicitly for degens if filters failed.
        # Or just use the calculated final_score (which penalizes failures).
        # If Advanced Filter failed, ScoringEngine likely tanked the score to 0.
        # So we should check AI Score raw.
        elif ai_score >= 80 and not adv_passed:
            # Check basic hard limits (Liquidity) - done in EarlyFilter.
            # So this is for e.g. Mintable or Taxes.
            strategy = "Degen Sword ⚔️"
            trade = paper_trader.degen_trader.process_signal(pair, ai_result)
            await telegram_service.send_alert(pair, ai_score, ai_result, paper_trade=trade, strategy_name=strategy)

scheduler = Scheduler()
