from typing import Dict, Tuple
from app.config import settings
from app.utils.logging_config import logger
from datetime import datetime

class EarlyFilter:
    """
    Applies fast, in-memory filters to pairs before expensive analysis.
    Criteria:
    - Liquidity >= $10,000
    - Pair age >= 2 minutes (implied by discovery time or explicit field)
    - Buys >= Sells (volume trend)
    - Supported chain (ETH, SOL, BSC)
    """
    
    SUPPORTED_CHAINS = {"ethereum", "solana", "bsc", "base", "arbitrum"}

    @staticmethod
    def inspect(pair_data: Dict) -> Tuple[bool, str]:
        """
        Returns (Passed: bool, Reason: str)
        """
        # 1. Chain Check
        chain_id = pair_data.get("chainId")
        if chain_id not in EarlyFilter.SUPPORTED_CHAINS:
            return False, f"Unsupported Chain: {chain_id}"

        # 2. Liquidity Check
        liquidity = pair_data.get("liquidity", {})
        usd_liquidity = liquidity.get("usd", 0)
        if usd_liquidity < settings.MIN_LIQUIDITY_USD:
            return False, f"Low Liquidity: ${usd_liquidity}"

        # 3. Volume / Txns (Buys >= Sells is a heuristic)
        # DexScreener provides txns.h1 or m5
        txns = pair_data.get("txns", {}).get("h1", {})
        buys = txns.get("buys", 0)
        sells = txns.get("sells", 0)
        
        # Simple volume check? Or Buy/Sell ratio?
        # "Buys >= Sells"
        # Avoid div by zero, if 0 sells and >0 buys, pass.
        if sells > buys:
             # Strict policy: filter if more sells than buys? 
             # Prompt: "Buys >= sells"
             return False, f"Sell Pressure: {sells} sells > {buys} buys"

        # 4. Pair Age (DexScreener usually provides 'pairCreatedAt')
        created_at_ts = pair_data.get("pairCreatedAt")
        if created_at_ts:
            age_minutes = (datetime.utcnow().timestamp() * 1000 - created_at_ts) / 1000 / 60
            if age_minutes < settings.MIN_PAIR_AGE_MINUTES:
                return False, f"Too Young: {age_minutes:.1f}m"
        
        return True, "Passed Early Filter"
