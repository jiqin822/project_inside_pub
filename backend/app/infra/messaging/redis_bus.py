"""Redis message bus."""
import asyncio
import json
from typing import Awaitable, Callable, Optional
from app.settings import settings

# Try redis.asyncio (redis 4.2+), fallback for older versions
try:
    import redis.asyncio as redis
    REDIS_ASYNC_AVAILABLE = True
except (ImportError, AttributeError):
    # Fallback: try to use sync redis with asyncio wrapper or raise helpful error
    try:
        import redis
        REDIS_ASYNC_AVAILABLE = False
        if not hasattr(redis, 'asyncio'):
            raise ImportError(
                f"redis.asyncio not available in redis {redis.__version__}. "
                f"Please upgrade: pip install --upgrade 'redis[hiredis]>=5.0.1'"
            )
    except ImportError:
        raise ImportError("redis package not installed. Install with: pip install 'redis[hiredis]>=5.0.1'")


class RedisBus:
    """Redis message bus for pub/sub and queue."""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._queue_redis: Optional[redis.Redis] = None

    async def connect(self):
        """Connect to Redis."""
        self._redis = await redis.from_url(settings.redis_url, decode_responses=True)
        self._queue_redis = await redis.from_url(settings.redis_queue_url, decode_responses=True)

    async def disconnect(self):
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
        if self._queue_redis:
            await self._queue_redis.close()

    async def publish(self, channel: str, message: dict):
        """Publish a message to a channel."""
        if not self._redis:
            await self.connect()
        await self._redis.publish(channel, json.dumps(message))

    async def subscribe_forever(
        self, channel: str, handler: Callable[[dict], Awaitable[None]]
    ) -> None:
        """Subscribe to a channel and call handler for each message. Runs until cancelled."""
        if not self._redis:
            await self.connect()
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message" and msg.get("data"):
                    try:
                        data = json.loads(msg["data"])
                        await handler(data)
                    except Exception:
                        pass
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def enqueue_job(self, queue_name: str, job_data: dict):
        """Enqueue a job."""
        if not self._queue_redis:
            await self.connect()
        await self._queue_redis.lpush(queue_name, json.dumps(job_data))

    async def get_job(self, queue_name: str) -> Optional[dict]:
        """Get a job from queue (blocking)."""
        if not self._queue_redis:
            await self.connect()
        result = await self._queue_redis.brpop(queue_name, timeout=1)
        if result:
            _, data = result
            return json.loads(data)
        return None

    async def set_rate_limit(self, key: str, value: str, ttl: int):
        """Set a rate limit key with TTL."""
        if not self._redis:
            await self.connect()
        await self._redis.setex(key, ttl, value)

    async def get_rate_limit(self, key: str) -> Optional[str]:
        """Get a rate limit key."""
        if not self._redis:
            await self.connect()
        return await self._redis.get(key)

    async def increment_rate_limit(self, key: str, ttl: int) -> int:
        """Increment rate limit counter."""
        if not self._redis:
            await self.connect()
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, ttl)
        return count


# Global instance
redis_bus = RedisBus()
