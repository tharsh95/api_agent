from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.knowledge_source import KnowledgeSource


class VectorSearchService:

    async def search(
        self,
        db: AsyncSession,
        project_id,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:

        distance = DocumentChunk.embedding.cosine_distance(
            query_embedding
        )

        result = await db.execute(
            select(
                DocumentChunk,
                Document,
                distance.label("distance"),
            )
            .join(
                Document,
                Document.id == DocumentChunk.document_id,
            )
            .join(
                KnowledgeSource,
                KnowledgeSource.id == Document.knowledge_source_id,
            )
            .where(
                KnowledgeSource.project_id == project_id,
                DocumentChunk.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(top_k)
        )

        rows = result.all()

        return [
            {
                "chunk_id": str(chunk.id),
                "document_id": str(document.id),
                "path": chunk.metadata_.get("path"),
                "repository": chunk.metadata_.get("repository"),
                "content": chunk.content,
                "score": round(1 - distance_value, 6),
                "metadata": chunk.metadata_,
            }
            for chunk, document, distance_value in rows
        ]