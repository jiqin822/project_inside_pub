"""Job queue interface."""
from typing import Protocol
from app.infra.messaging.redis_bus import redis_bus


class JobQueue(Protocol):
    """Job queue protocol."""

    async def enqueue(self, job_type: str, job_data: dict) -> None:
        """Enqueue a job."""
        ...


class RedisJobQueue:
    """Redis-based job queue."""

    async def enqueue(self, job_type: str, job_data: dict) -> None:
        """Enqueue a job."""
        await redis_bus.enqueue_job("jobs", {"type": job_type, "data": job_data})


# Global instance
job_queue = RedisJobQueue()
