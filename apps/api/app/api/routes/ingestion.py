import uuid
from fastapi import BackgroundTasks
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.ingestion import IngestFilesRequest
from app.services.ingestion_service import IngestionService
from sqlalchemy import select

from app.models.ingestion_job import IngestionJob
from app.models.project import Project
from app.services.ingestion_job_service import (
    IngestionJobService,
)

ingestion_job_service = IngestionJobService()
router = APIRouter(
    prefix="/projects",
    tags=["ingestion"],
)

ingestion_service = IngestionService()


@router.post("/{project_id}/ingest")
async def ingest_project_files(
    project_id: uuid.UUID,
    payload: IngestFilesRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="No authenticated user found",
        )

    try:
        authenticated_user_id = uuid.UUID(user_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid authenticated user",
        ) from exc

    return await ingestion_service.ingest_files(
        db=db,
        project_id=project_id,
        user_id=authenticated_user_id,
        paths=payload.paths,
    )

@router.post("/{project_id}/sync")
async def sync_project_repository(
    project_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="No authenticated user found",
        )

    try:
        authenticated_user_id = uuid.UUID(user_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid authenticated user",
        ) from exc

    return await ingestion_service.sync_repository(
        db=db,
        project_id=project_id,
        user_id=authenticated_user_id,
    )

@router.post("/{project_id}/ingestion-jobs")
async def create_ingestion_job(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="No authenticated user found",
        )

    try:
        authenticated_user_id = uuid.UUID(user_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid authenticated user",
        ) from exc

    job = await ingestion_job_service.create_job(
        db=db,
        project_id=project_id,
    )

    background_tasks.add_task(
        ingestion_job_service.run_job,
        job.id,
        project_id,
        authenticated_user_id,
    )

    return {
        "job_id": str(job.id),
        "status": job.status,
    }

@router.get(
    "/{project_id}/ingestion-jobs/{job_id}"
)
async def get_ingestion_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="No authenticated user found",
        )

    try:
        authenticated_user_id = uuid.UUID(user_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid authenticated user",
        ) from exc

    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == authenticated_user_id,
        )
    )

    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    result = await db.execute(
        select(IngestionJob).where(
            IngestionJob.id == job_id,
            IngestionJob.project_id == project_id,
        )
    )

    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Ingestion job not found",
        )

    return {
        "job_id": str(job.id),
        "status": job.status,
        "added": job.files_added,
        "updated": job.files_updated,
        "deleted": job.files_deleted,
        "unchanged": job.files_unchanged,
        "error": job.error,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }