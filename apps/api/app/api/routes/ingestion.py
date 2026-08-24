import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.ingestion import IngestFilesRequest
from app.services.ingestion_service import IngestionService


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