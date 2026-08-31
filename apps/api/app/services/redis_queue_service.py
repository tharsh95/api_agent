import json

import redis.asyncio as redis

from app.core.config import settings


class RedisQueueService:
    QUEUE_NAME = "ingestion_jobs"

    def __init__(self):
        self.client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

    async def enqueue(
        self,
        job_id: str,
        project_id: str,
        user_id: str,
    ) -> None:
        payload = {
            "job_id": job_id,
            "project_id": project_id,
            "user_id": user_id,
        }

        await self.client.lpush(
            self.QUEUE_NAME,
            json.dumps(payload),
        )

    async def dequeue(
        self,
        timeout: int = 5,
    ) -> dict | None:
        result = await self.client.brpop(
            self.QUEUE_NAME,
            timeout=timeout,
        )

        if not result:
            return None

        _, payload = result

        return json.loads(payload)

    async def close(self) -> None:
        await self.client.aclose()