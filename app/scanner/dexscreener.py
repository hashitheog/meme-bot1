import asyncio
import aiohttp
from typing import List, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.utils.logging_config import logger
from app.utils.rate_limiter import AsyncRateLimiter

# 300 calls per minute strict limit is standard, but we target much lower (10k/day ~ 7/min)
# We set strict limiter to 60 calls per minute to be safe allowing burst, 
# but scheduler controls the main flow.
rate_limiter = AsyncRateLimiter(max_calls=60, period=60)

class DexScreenerClient:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "MemeBot/1.0"},
            timeout=aiohttp.ClientTimeout(total=45) # Increased for stability
        )

    async def close(self):
        if self.session:
            await self.session.close()

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def fetch_latest_pairs(self) -> List[Dict]:
        """
        Fetches the latest pairs. 
        Note: DexScreener doesn't have a perfect 'newest' endpoint. 
        We mimic this by searching or using a specific chain endpoint if available.
        For this implementation, we will use a search query that often returns active pairs
        and filter by age on client side if needed, or assume this endpoint returns mixed data.
        
        Ref: https://api.dexscreener.com/latest/dex/search/?q=...
        """
        if not self.session:
            raise RuntimeError("Client not started")

        await rate_limiter.acquire()
        
        # Searching for 'sol' or 'eth' to get recent lists, or empty q?
        # A common trick is searching for generic terms or monitoring specific token addresses 
        # from a node. Since we are restricted to DexScreener, we try a broad search.
        # Ideally, we would use `https://api.dexscreener.com/latest/dex/tokens/new` if it existed.
        url = f"{settings.DEXSCREENER_API_URL}/search?q=pair-age:6h" 
        # NOTE: 'pair-age' is not a documented filter for search q, but illustrative.
        # In PROD, rely on a dedicated "new pairs" provider or specific chain monitoring.
        
        # Let's use a generic query that gives us content
        url = f"{settings.DEXSCREENER_API_URL}"
        # For now, let's target specific chain pairs endpoint if valid? 
        # No, /latest/dex/pairs requires addresses.
        # Fallback: search?q=WETH
        url = "https://api.dexscreener.com/latest/dex/search?q=WETH" 

        async with self.session.get(url) as response:
            if response.status == 429:
                logger.warning("DexScreener Rate Limit 429")
                raise aiohttp.ClientResponseError(
                    response.request_info, response.history, status=429
                )
            
            response.raise_for_status()
            data = await response.json()
            pairs = data.get("pairs", [])
            return pairs

    async def fetch_pair_data(self, chain_id: str, pair_address: str) -> Optional[Dict]:
        """Fetch real-time data for a specific pair to update paper trades."""
        if not self.session:
            return None
            
        await rate_limiter.acquire()
        url = f"https://api.dexscreener.com/latest/dex/pairs/{chain_id}/{pair_address}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        return pairs[0] # Return the first matching pair data

        except Exception as e:
            logger.warning(f"Direct fetch failed for {pair_address}: {e}")
        
        # Fallback: Search API (Handles case-insensitivity)
        # Often scraper returns lowercase address, but API needs specific case.
        # Search API ?q=address handles this.
        try:
            search_url = f"https://api.dexscreener.com/latest/dex/search?q={pair_address}"
            async with self.session.get(search_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        logger.info(f"Search Fallback Success for {pair_address}")
                        return pairs[0]
        except Exception as e:
             logger.error(f"Search fallback failed for {pair_address}: {e}")
            
        return None

dex_client = DexScreenerClient()
