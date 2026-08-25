import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.api.routes.rag import RAGRequest, ask_project
from app.main import app


@pytest.mark.asyncio
async def test_rag_requires_authentication():
    project_id = uuid.uuid4()

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/projects/{project_id}/ask",
            json={
                "question": "What does this project do?",
                "top_k": 5,
            },
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "No authenticated user found"}

@pytest.mark.asyncio
async def test_rag_rejects_project_owned_by_another_user():
    authenticated_user_id = uuid.uuid4()
    project_id = uuid.uuid4()

    request = MagicMock()
    request.session = {
        "user_id": str(authenticated_user_id),
    }

    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = None

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=fake_result,
    )

    with pytest.raises(HTTPException) as exc_info:
        await ask_project(
            project_id=project_id,
            payload=RAGRequest(
                question="What does this project do?",
                top_k=5,
            ),
            request=request,
            db=db,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Project not found"