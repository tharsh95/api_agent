import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.document_chunk import DocumentChunk
from app.models.project import Project
from app.models.repository import Repository
from app.services.embedding_service import EmbeddingService
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.knowledge_source import KnowledgeSource
from app.models.project import Project

router = APIRouter(
    prefix="/projects",
    tags=["embeddings"],
)

embedding_service = EmbeddingService()


@router.post("/{project_id}/embeddings")
async def generate_project_embeddings(
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

    # Verify project belongs to user.
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

    # Get chunks that don't have embeddings yet.
    result = await db.execute(
        select(DocumentChunk)
        .join(Document)
        .join(KnowledgeSource)
        .where(
            KnowledgeSource.project_id == project_id,
            DocumentChunk.embedding.is_(None),
        )
        .order_by(DocumentChunk.created_at, DocumentChunk.id)
    )

    chunks = result.scalars().all()

    if not chunks:
        return {
            "status": "completed",
            "message": "No chunks require embeddings",
            "chunks_processed": 0,
        }

    texts = [chunk.content for chunk in chunks]

    embeddings = await embedding_service.generate_embeddings(
        texts
    )

    if len(embeddings) != len(chunks):
        raise HTTPException(
            status_code=502,
            detail="Embedding count does not match chunk count",
        )

    for chunk, embedding in zip(
        chunks,
        embeddings,
    ):
        chunk.embedding = embedding

    await db.commit()

    return {
        "status": "completed",
        "chunks_processed": len(chunks),
        "embedding_dimensions": len(embeddings[0]),
    }