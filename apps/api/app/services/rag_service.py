from openai import AsyncOpenAI

from app.core.config import settings
from app.services.embedding_service import EmbeddingService
from app.services.vector_search_service import VectorSearchService


class RAGService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key
        )

        self.model = "gpt-4.1-mini"

        self.embedding_service = EmbeddingService()
        self.vector_search_service = VectorSearchService()

    async def answer(
        self,
        db,
        project_id,
        question: str,
        top_k: int = 5,
    ) -> dict:

        question = question.strip()

        if not question:
            raise ValueError(
                "Question cannot be empty"
            )

        # 1. Embed the user's question.
        embeddings = (
            await self.embedding_service.generate_embeddings(
                [question]
            )
        )

        if not embeddings:
            raise RuntimeError(
                "Failed to generate query embedding"
            )

        query_embedding = embeddings[0]

        # 2. Retrieve relevant chunks.
        chunks = await self.vector_search_service.search(
            db=db,
            project_id=project_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )

        if not chunks:
            return {
                "answer": (
                    "I couldn't find relevant information "
                    "in this project's repository."
                ),
                "sources": [],
            }

        # 3. Build context.
        context_parts = []

        for index, chunk in enumerate(chunks, start=1):
            path = chunk.get("path") or "unknown"

            context_parts.append(
                f"[Source {index}: {path}]\n"
                f"{chunk['content']}"
            )

        context = "\n\n---\n\n".join(
            context_parts
        )

        # 4. Ask the LLM using only retrieved context.
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a codebase assistant. "
                        "Answer using only the provided repository context. "
                        "Do not invent facts. "
                        "Do not treat a partial retrieved chunk as proof that "
                        "the underlying source file is incomplete or missing "
                        "functionality. "
                        "Distinguish between facts explicitly supported by the "
                        "context and information that cannot be determined. "
                        "Do not infer absence from missing context. "
                        "If the retrieved context is insufficient, say so. "
                        "When possible, identify the source file path."
                    )
                },
                {
                    "role": "user",
                    "content": f"""
                        Question: {question}\n\nRepository context:\n{context}\n\nAnswer only from the repository context above.\n\nDistinguish explicitly between:\n- currently implemented functionality\n- planned/future functionality\n- information that cannot be determined from the context.\n""",
                },
            ],
        )

        answer = response.choices[0].message.content

        return {
            "answer": answer,
            "sources": [
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "path": chunk.get("path"),
                    "repository": chunk.get("repository"),
                    "score": chunk.get("score"),
                }
    for chunk in chunks
    ],
        }