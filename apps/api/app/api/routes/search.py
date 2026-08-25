import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Project
from app.services.embedding_service import EmbeddingService
from app.services.vector_search_service import VectorSearchService
from pydantic import BaseModel, Field, field_validator


router = APIRouter(
    prefix="/projects",
    tags=["search"],
)

embedding_service = EmbeddingService()
vector_search_service = VectorSearchService()




class SearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=5000,
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "Query cannot be empty"
            )

        return value


@router.post("/{project_id}/search")
async def search_project(
    project_id: uuid.UUID,
    payload: SearchRequest,
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

    # Verify project ownership.
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
    
    # Convert query into the same vector space as the chunks.
    query = payload.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty",
        )

    embeddings = await embedding_service.generate_embeddings(
    [query]
)

    if not embeddings:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate query embedding",
        )

    query_embedding = embeddings[0]

    results = await vector_search_service.search(
        db=db,
        project_id=project_id,
        query=query,
        query_embedding=query_embedding,
        top_k=payload.top_k,
)

    return {
        "query": payload.query,
        "results": results,
    }