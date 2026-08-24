class ChunkingService:
    def __init__(
        self,
        chunk_size: int = 1200,
        chunk_overlap: int = 200,
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, content: str) -> list[str]:
        if not content.strip():
            return []

        chunks = []

        start = 0
        content_length = len(content)

        while start < content_length:
            end = min(
                start + self.chunk_size,
                content_length,
            )

            chunk = content[start:end].strip()

            if chunk:
                chunks.append(chunk)

            if end >= content_length:
                break

            start = end - self.chunk_overlap

        return chunks