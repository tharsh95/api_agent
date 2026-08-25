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

        # 1. Embed the user's question
        embeddings = await self.embedding_service.generate_embeddings(
            [question]
        )

        if not embeddings:
            raise RuntimeError(
                "Failed to generate query embedding"
            )

        query_embedding = embeddings[0]

        # 2. Retrieve relevant chunks
        chunks = await self.vector_search_service.search(
            db=db,
            project_id=project_id,
            query_embedding=query_embedding,
            query=question,
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

        # 3. Build context with source metadata
        context_parts = []

        for index, chunk in enumerate(chunks, start=1):
            path = chunk.get("path") or "unknown"
            repository = chunk.get("repository") or "unknown"

            metadata = chunk.get("metadata") or {}

            branch = metadata.get("branch") or "unknown"
            sha = metadata.get("sha") or "unknown"

            context_parts.append(
                f"[Source {index}]\n"
                f"Repository: {repository}\n"
                f"File: {path}\n"
                f"Branch: {branch}\n"
                f"SHA: {sha}\n"
                f"Content:\n"
                f"{chunk['content']}"
            )

        context = "\n\n---\n\n".join(context_parts)

        # 4. Ask the LLM using only retrieved context
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": """
You are a repository-aware codebase assistant.

Answer the user's question using only the retrieved repository
context provided to you.

Rules:

1. Treat each [Source] as independent evidence.

2. Never invent code, files, functions, dependencies,
   configuration, behavior, or implementation details.

3. Do not assume that information from one file applies to
   another file or another database.

4. Prefer direct source-code evidence over README or documentation
   when answering implementation questions.

5. Use README/documentation for project-level descriptions,
   architecture, setup, and documented behavior.

6. If the retrieved context is insufficient to answer a question,
   explicitly say that the available repository context is
   insufficient.

7. Do not conclude that something does not exist merely because
   it was not present in the retrieved chunks.

8. If sources disagree, explicitly mention the disagreement.

9. When possible, mention the exact source file responsible for
   the behavior being described.

10. Keep the answer focused and avoid repeating the same
    information unnecessarily.
""",
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n\n"
                        f"Repository context:\n{context}\n\n"
                        "Answer the question using only the "
                        "repository context above."
                    ),
                },
            ],
        )

        answer = response.choices[0].message.content

        return {
            "answer": answer,
            "sources": [
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "document_id": chunk.get("document_id"),
                    "path": chunk.get("path"),
                    "repository": chunk.get("repository"),
                    "sha": (
                        chunk.get("metadata") or {}
                    ).get("sha"),
                    "branch": (
                        chunk.get("metadata") or {}
                    ).get("branch"),
                    "score": chunk.get("score"),
                    "github_url": (
                        f"https://github.com/"
                        f"{chunk.get('repository')}/blob/"
                        f"{(chunk.get('metadata') or {}).get('branch', 'main')}/"
                        f"{chunk.get('path')}"
                    ),
                }
                for chunk in chunks
            ],
        }