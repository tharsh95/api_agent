from openai import AsyncOpenAI

from app.core.config import settings


class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key
        )

        self.model = "text-embedding-3-small"
        self.dimensions = 1536

    async def generate_embeddings(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        if not texts:
            return []

        if any(not text.strip() for text in texts):
            raise ValueError(
                "Cannot generate embeddings for empty text"
            )

        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )

        # The API returns items with indexes.
        ordered = sorted(
            response.data,
            key=lambda item: item.index,
        )

        return [
            item.embedding
            for item in ordered
        ]