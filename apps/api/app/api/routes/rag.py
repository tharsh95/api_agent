import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Project
from app.services.rag_service import RAGService


router = APIRouter(
    prefix="/projects",
    tags=["rag"],
)

rag_service = RAGService()


class RAGRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=5000,
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
    )


@router.post("/{project_id}/ask")
async def ask_project(
    project_id: uuid.UUID,
    payload: RAGRequest,
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

    try:
        return await rag_service.answer(
            db=db,
            project_id=project_id,
            question=payload.question,
            top_k=payload.top_k,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc