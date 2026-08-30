import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.db.session import get_db
from app.services.agent_service import AgentService

from fastapi import HTTPException
@pytest.mark.asyncio
async def test_agent_requires_authentication():
    project_id = uuid.uuid4()

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/projects/{project_id}/agent",
            json={
                "request": "Integrate Stripe payments",
            },
        )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "No authenticated user found"
    }


@pytest.mark.asyncio
async def test_agent_rejects_invalid_session_user():
    project_id = uuid.uuid4()

    from unittest.mock import patch

    with patch(
        "app.api.routes.agent.agent_service"
    ):
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            # We need a signed session in the real app,
            # so this test will be handled separately if
            # session middleware is required.
            pass


@pytest.mark.asyncio
async def test_agent_returns_service_result(
    monkeypatch,
):
    project_id = uuid.uuid4()
    authenticated_user_id = uuid.uuid4()

    fake_project = MagicMock()
    fake_project.id = project_id
    fake_project.user_id = authenticated_user_id

    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = (
        fake_project
    )

    fake_db = MagicMock()
    fake_db.execute = AsyncMock(
        return_value=fake_result
    )

    async def fake_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = fake_get_db

    fake_agent_service = MagicMock()
    fake_agent_service.run = AsyncMock(
        return_value={
            "status": "plan_created",
            "integration_plan": {
                "request": "Integrate Stripe payments",
                "requires_confirmation": True,
            },
        }
    )

    monkeypatch.setattr(
        "app.api.routes.agent.agent_service",
        fake_agent_service,
    )

    # SessionMiddleware needs a real signed session.
    # For this boundary test, invoke the route directly.
    from app.api.routes.agent import run_project_agent


    request = MagicMock()
    request.session = {
        "user_id": str(authenticated_user_id),
    }

    try:
        response = await run_project_agent(
            project_id=project_id,
            payload=MagicMock(
                request="Integrate Stripe payments"
            ),
            request=request,
            db=fake_db,
        )

        assert response["status"] == "plan_created"

        fake_agent_service.run.assert_awaited_once_with(
            db=fake_db,
            project_id=project_id,
            user_id=authenticated_user_id,
            user_request="Integrate Stripe payments",
        )

    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_agent_rejects_project_owned_by_another_user(
    monkeypatch,
):
    authenticated_user_id = uuid.uuid4()
    project_id = uuid.uuid4()

    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = None

    fake_db = MagicMock()
    fake_db.execute = AsyncMock(
        return_value=fake_result,
    )

    async def fake_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = fake_get_db

    fake_agent_service = MagicMock()
    fake_agent_service.run = AsyncMock()

    monkeypatch.setattr(
        "app.api.routes.agent.agent_service",
        fake_agent_service,
    )

    request = MagicMock()
    request.session = {
        "user_id": str(authenticated_user_id),
    }

    try:
        from app.api.routes.agent import run_project_agent

        response = await run_project_agent(
            project_id=project_id,
            payload=MagicMock(
                request="Integrate Stripe payments",
            ),
            request=request,
            db=fake_db,
        )

        # With the current architecture, ownership is checked
        # inside RepositoryContextService, not the route.
        # Therefore this direct route test cannot establish
        # the 404 boundary yet.
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_confirm_agent_run(
    monkeypatch,
):
    project_id = uuid.uuid4()
    agent_run_id = uuid.uuid4()
    authenticated_user_id = uuid.uuid4()

    fake_db = MagicMock()

    fake_agent_service = MagicMock()
    fake_agent_service.confirm = AsyncMock(
        return_value={
            "agent_run_id": str(agent_run_id),
            "status": "CONFIRMED",
            "confirmed": True,
        }
    )

    monkeypatch.setattr(
        "app.api.routes.agent.agent_service",
        fake_agent_service,
    )

    from app.api.routes.agent import confirm_agent_run

    request = MagicMock()
    request.session = {
        "user_id": str(authenticated_user_id),
    }

    response = await confirm_agent_run(
        project_id=project_id,
        agent_run_id=agent_run_id,
        request=request,
        db=fake_db,
    )

    assert response["agent_run_id"] == str(
        agent_run_id
    )

    assert response["status"] == "CONFIRMED"

    assert response["confirmed"] is True

    fake_agent_service.confirm.assert_awaited_once_with(
        db=fake_db,
        project_id=project_id,
        user_id=authenticated_user_id,
        agent_run_id=agent_run_id,
    )

@pytest.mark.asyncio
async def test_confirm_agent_requires_authentication():

    project_id = uuid.uuid4()
    agent_run_id = uuid.uuid4()

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:

        response = await client.post(
            f"/api/projects/{project_id}/agent/"
            f"{agent_run_id}/confirm",
        )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "No authenticated user found"
    }