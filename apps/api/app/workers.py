import asyncio
import uuid

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.ingestion_job import IngestionJob
from app.services.ingestion_job_service import (
    IngestionJobService,
)
from app.services.redis_queue_service import (
    RedisQueueService,
)


async def process_job(payload: dict) -> None:
    job_id = uuid.UUID(payload["job_id"])
    project_id = uuid.UUID(payload["project_id"])
    user_id = uuid.UUID(payload["user_id"])

    job_service = IngestionJobService()

    await job_service.run_job(
        job_id=job_id,
        project_id=project_id,
        user_id=user_id,
    )


async def worker() -> None:
    queue = RedisQueueService()

    print(
        f"Worker started. Listening on "
        f"'{queue.QUEUE_NAME}'"
    )

    try:
        while True:
            payload = await queue.dequeue(
                timeout=5
            )

            if not payload:
                continue

            try:
                print(
                    f"Processing ingestion job "
                    f"{payload['job_id']}"
                )

                await process_job(payload)

                print(
                    f"Completed ingestion job "
                    f"{payload['job_id']}"
                )

            except Exception as exc:
                print(
                    f"Worker error for job "
                    f"{payload.get('job_id')}: {exc}"
                )

    finally:
        await queue.close()


if __name__ == "__main__":
    asyncio.run(worker())