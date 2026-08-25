import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.rag_service import RAGService


@pytest.fixture
def service():
    return RAGService()


@pytest.mark.asyncio
async def test_answer_empty_question(service):
    with pytest.raises(ValueError, match="Question cannot be empty"):
        await service.answer(
            db=MagicMock(),
            project_id=uuid.uuid4(),
            question="   ",
        )


@pytest.mark.asyncio
async def test_answer_no_chunks(service):
    project_id = uuid.uuid4()

    service.embedding_service.generate_embeddings = AsyncMock(
        return_value=[[0.1] * 1536]
    )

    service.vector_search_service.search = AsyncMock(
        return_value=[]
    )

    result = await service.answer(
        db=MagicMock(),
        project_id=project_id,
        question="What does this project do?",
    )

    assert result["sources"] == []
    assert "couldn't find relevant information" in result["answer"]


@pytest.mark.asyncio
async def test_answer_with_retrieved_context(service):
    project_id = uuid.uuid4()

    service.embedding_service.generate_embeddings = AsyncMock(
        return_value=[[0.1] * 1536]
    )

    service.vector_search_service.search = AsyncMock(
        return_value=[
            {
                "chunk_id": "chunk-1",
                "document_id": "document-1",
                "path": "loaders/memgraph_loader.py",
                "repository": "owner/repo",
                "content": "Uses CREATE for relationships.",
                "score": 0.91,
                "rerank_score": 0.96,
                "metadata": {
                    "sha": "abc123",
                    "branch": "main",
                },
            }
        ]
    )

    response = MagicMock()
    response.choices = [
        MagicMock(
            message=MagicMock(
                content="The Memgraph loader uses CREATE for relationships."
            )
        )
    ]

    service.client.chat.completions.create = AsyncMock(
        return_value=response
    )

    result = await service.answer(
        db=MagicMock(),
        project_id=project_id,
        question="How are relationships created?",
    )

    assert (
        result["answer"]
        == "The Memgraph loader uses CREATE for relationships."
    )

    assert len(result["sources"]) == 1

    source = result["sources"][0]

    assert source["path"] == "loaders/memgraph_loader.py"
    assert source["repository"] == "owner/repo"
    assert source["sha"] == "abc123"
    assert source["branch"] == "main"
    assert source["score"] == 0.91

    service.client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_answer_uses_requested_top_k(service):
    project_id = uuid.uuid4()

    service.embedding_service.generate_embeddings = AsyncMock(
        return_value=[[0.1] * 1536]
    )

    service.vector_search_service.search = AsyncMock(
        return_value=[]
    )

    await service.answer(
        db=MagicMock(),
        project_id=project_id,
        question="What does the loader do?",
        top_k=3,
    )

    service.vector_search_service.search.assert_awaited_once()

    call = service.vector_search_service.search.await_args

    assert call.kwargs["top_k"] == 3