import redis.asyncio as redis
from app.config import settings
from app.utils.logging_config import logger

class RedisClient:
    def __init__(self):
        self._redis: redis.Redis = None

    async def connect(self):
        """Initializes the Redis connection pool."""
        try:
            self._redis = redis.from_url(
                settings.REDIS_URL, 
                encoding="utf-8", 
                decode_responses=True,
                socket_connect_timeout=1 # Fast fail to switch to fake
            )
            await self._redis.ping()
            logger.info("Connected to Real Redis", url=settings.REDIS_URL)
        except Exception:
            # This is expected for local users without a Redis server.
            logger.info("No external Redis server found. Using In-Memory Cache (Stand-alone Mode).")
            from fakeredis import aioredis
            self._redis = aioredis.FakeRedis(decode_responses=True)

    async def close(self):
        if self._redis:
            await self._redis.close()

    async def exists(self, key: str) -> bool:
        return await self._redis.exists(key)

    async def get(self, key: str):
        return await self._redis.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        await self._redis.set(key, value, ex=ex)

    async def is_token_seen(self, chain: str, address: str) -> bool:
        """Checks if a token has been processed recently using a Bloom filter or simple key check."""
        # Simple key check for MVP. Key: "seen:{chain}:{address}"
        key = f"seen:{chain}:{address}"
        return await self.exists(key)

    async def mark_token_seen(self, chain: str, address: str, ttl: int = 86400):
        """Marks a token as seen to prevent reprocessing."""
        key = f"seen:{chain}:{address}"
        # Store a simple '1' with a TTL (default 24h)
        await self.set(key, "1", ex=ttl)

redis_client = RedisClient()
