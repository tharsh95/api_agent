import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.vector_search_service import VectorSearchService


def make_row(
    path: str,
    distance: float,
):
    chunk = SimpleNamespace(
        id=uuid.uuid4(),
        content=f"content for {path}",
        metadata_={
            "path": path,
            "repository": "owner/repo",
            "sha": "test-sha",
            "branch": "main",
        },
    )

    document = SimpleNamespace(
        id=uuid.uuid4(),
        github_path=path,
    )

    return (
        chunk,
        document,
        distance,
    )


@pytest.mark.asyncio
async def test_search_returns_top_k_results():
    service = VectorSearchService()

    db = MagicMock()

    rows = [
        make_row("loaders/memgraph_loader.py", 0.1),
        make_row("README.md", 0.2),
        make_row("Makefile", 0.3),
    ]

    result = MagicMock()
    result.all.return_value = rows

    db.execute = AsyncMock(return_value=result)

    output = await service.search(
        db=db,
        project_id=uuid.uuid4(),
        query_embedding=[0.1] * 1536,
        query="Memgraph loader",
        top_k=2,
    )

    assert len(output) == 2
    assert output[0]["path"] == "loaders/memgraph_loader.py"


@pytest.mark.asyncio
async def test_search_applies_path_boost():
    service = VectorSearchService()

    db = MagicMock()

    rows = [
        make_row("README.md", 0.10),
        make_row("loaders/memgraph_loader.py", 0.12),
    ]

    result = MagicMock()
    result.all.return_value = rows

    db.execute = AsyncMock(return_value=result)

    output = await service.search(
        db=db,
        project_id=uuid.uuid4(),
        query_embedding=[0.1] * 1536,
        query="Memgraph loader",
        top_k=2,
    )

    assert output[0]["path"] == (
        "loaders/memgraph_loader.py"
    )

    assert output[0]["rerank_score"] > (
        output[1]["rerank_score"]
    )


@pytest.mark.asyncio
async def test_search_returns_source_metadata():
    service = VectorSearchService()

    db = MagicMock()

    rows = [
        make_row("loaders/memgraph_loader.py", 0.1),
    ]

    result = MagicMock()
    result.all.return_value = rows

    db.execute = AsyncMock(return_value=result)

    output = await service.search(
        db=db,
        project_id=uuid.uuid4(),
        query_embedding=[0.1] * 1536,
        query="Memgraph loader",
        top_k=5,
    )

    item = output[0]

    assert item["path"] == (
        "loaders/memgraph_loader.py"
    )
    assert item["repository"] == "owner/repo"
    assert item["metadata"]["sha"] == "test-sha"
    assert item["metadata"]["branch"] == "main"
    assert "score" in item
    assert "rerank_score" in item
