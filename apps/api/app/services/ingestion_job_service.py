import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.ingestion_job import IngestionJob
from app.services.ingestion_service import IngestionService


class IngestionJobService:
    def __init__(self):
        self.ingestion_service = IngestionService()

    async def create_job(
        self,
        db,
        project_id: uuid.UUID,
    ) -> IngestionJob:
        job = IngestionJob(
            project_id=project_id,
            status="queued",
        )

        db.add(job)
        await db.commit()
        await db.refresh(job)

        return job

    async def run_job(
        self,
        job_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(IngestionJob).where(
                    IngestionJob.id == job_id,
                )
            )

            job = result.scalar_one_or_none()

            if not job:
                return

            try:
                job.status = "running"
                job.started_at = datetime.now(
                    timezone.utc
                )

                await db.commit()

                result = (
                    await self.ingestion_service
                    .sync_repository(
                        db=db,
                        project_id=project_id,
                        user_id=user_id,
                    )
                )

                job.status = "completed"
                job.files_added = result["added"]
                job.files_updated = result["updated"]
                job.files_deleted = result["deleted"]
                job.files_unchanged = result["unchanged"]
                job.completed_at = datetime.now(
                    timezone.utc
                )

            except Exception as exc:
                job.status = "failed"
                job.error = str(exc)[:2000]
                job.completed_at = datetime.now(
                    timezone.utc
                )

            await db.commit()