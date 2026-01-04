from typing import Dict, Tuple

class AdvancedFilter:
    """
    Simulates deeper on-chain checks. 
    In a real system, this would call GoPlus, HoneyPot.is, or RugCheck.xyz APIs.
    For this MVP, we structure it to accept data and pass/fail.
    """
    
    @staticmethod
    async def inspect(pair_data: Dict, onchain_data: Dict) -> Tuple[bool, str]:
        """
        Unpacks on-chain data and applies hard filters.
        """
        # 1. Honeypot check
        if onchain_data.get("is_honeypot", False):
            return False, "Is Honeypot"
            
        # 2. Mintable
        if onchain_data.get("mintable", True): # Default to true (fail) if unknown? Or False?
            # Safe default -> fail if we can't verify 'not mintable' strictly? 
            # Let's say we trust the data source.
            return False, "Token is Mintable (High Risk)"

        # 3. LP Locked
        lp_locked_percent = onchain_data.get("lp_locked", 0)
        if lp_locked_percent < 90:
            return False, f"LP Not Locked Enough: {lp_locked_percent}%"

        # 4. Top Holders
        holders = onchain_data.get("holders", [])
        # Example: [{"address": "...", "percent": 10}]
        for h in holders:
            if h.get("percent", 0) > 20: # Prompt: No holder > 20%
                 return False, f"Whale Alert: Holder has {h['percent']}%"

        # 5. Taxes
        buy_tax = onchain_data.get("buy_tax", 0)
        sell_tax = onchain_data.get("sell_tax", 0)
        if buy_tax + sell_tax > 10:
             return False, f"High Taxes: Buy {buy_tax}% / Sell {sell_tax}%"

        return True, "Passed Advanced Filter"
