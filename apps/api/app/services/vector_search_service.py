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
        query: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:

        distance = DocumentChunk.embedding.cosine_distance(
            query_embedding
        )

        candidate_limit = max(
            top_k * 4,
            20,
        )

        result = await db.execute(
            select(
                DocumentChunk,
                Document,
                distance.label("distance"),
            )
            .join(
                Document,
                Document.id
                == DocumentChunk.document_id,
            )
            .join(
                KnowledgeSource,
                KnowledgeSource.id
                == Document.knowledge_source_id,
            )
            .where(
                KnowledgeSource.project_id
                == project_id,
                DocumentChunk.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(candidate_limit)
        )

        rows = result.all()

        query_terms = set(
            query.lower()
            .replace("-", "_")
            .split()
        ) if query else set()

        ranked_results = []

        for (
            chunk,
            document,
            distance_value,
        ) in rows:

            path = (
                chunk.metadata_.get("path")
                or document.github_path
                or ""
            )

            original_score = (
                1 - distance_value
            )

            normalized_path = (
                path.lower()
                .replace("/", " ")
                .replace("_", " ")
                .replace("-", " ")
                .replace(".", " ")
            )

            path_terms = set(
                normalized_path.split()
            )

            matching_terms = (
                query_terms.intersection(
                    path_terms
                )
            )

            filename_boost = min(
                len(matching_terms) * 0.05,
                0.15,
            )

            final_score = (
                original_score
                + filename_boost
            )

            ranked_results.append(
                (
                    final_score,
                    original_score,
                    chunk,
                    document,
                    path,
                )
            )

        ranked_results.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            {
                "chunk_id": str(chunk.id),
                "document_id": str(
                    document.id
                ),
                "path": path,
                "repository": (
                    chunk.metadata_.get(
                        "repository"
                    )
                ),
                "content": chunk.content,
                "score": round(
                    original_score,
                    6,
                ),
                "rerank_score": round(
                    final_score,
                    6,
                ),
                "metadata": chunk.metadata_,
            }
            for (
                final_score,
                original_score,
                chunk,
                document,
                path,
            ) in ranked_results[:top_k]
        ]