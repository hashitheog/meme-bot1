import asyncio
import time
from app.utils.logging_config import logger

class AsyncRateLimiter:
    """
    Token bucket rate limiter.
    """
    def __init__(self, max_calls: int, period: int = 60):
        self.max_calls = max_calls
        self.period = period
        self.tokens = max_calls
        self.last_updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_updated
            
            # Replenish tokens
            new_tokens = elapsed * (self.max_calls / self.period)
            self.tokens = min(self.max_calls, self.tokens + new_tokens)
            self.last_updated = now

            if self.tokens >= 1:
                self.tokens -= 1
                return
            else:
                # Wait until we have 1 token
                wait_time = (1 - self.tokens) * (self.period / self.max_calls)
                logger.debug(f"Rate limit hit, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self.tokens = 0
                self.last_updated = time.monotonic()
