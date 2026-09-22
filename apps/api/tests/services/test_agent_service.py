from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from fastapi import HTTPException

from app.services.agent_service import AgentService


@pytest.mark.asyncio
async def test_agent_service_passes_repository_context():

    repository = {
        "owner": "acme",
        "name": "payments-api",
        "default_branch": "main",
        "url": "https://github.com/acme/payments-api",
        "files": [
            {
                "path": "package.json",
                "content": "{}",
            }
        ],
    }

    repository_context_service = MagicMock()

    repository_context_service.get_repository_context = (
        AsyncMock(
            return_value=repository
        )
    )

    graph = MagicMock()

    graph.ainvoke = AsyncMock(
        return_value={
            "status": "plan_created",
            "repository_profile": {
                "language": "TypeScript",
                "framework": "Next.js",
            },
            "integration_candidates": [
                {
                    "file": "package.json",
                    "reason": "Stripe dependency",
                    "confidence": 0.9,
                }
            ],
            "integration_plan": {
                "request": "Integrate Stripe payments",
                "files_to_modify": [
                    "package.json",
                ],
                "dependencies": [
                    "stripe",
                ],
                "steps": [
                    {
                        "file": "package.json",
                        "action": "Add Stripe dependency.",
                    }
                ],
                "requires_confirmation": True,
            },
        }
    )

    service = AgentService(
        repository_context_service=(
            repository_context_service
        ),
        graph_instance=graph,
    )

    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    result = await service.run(
        db=db,
        project_id="project-123",
        user_id="user-123",
        user_request="Integrate Stripe payments",
    )

    # Repository context was fetched correctly.
    repository_context_service \
        .get_repository_context \
        .assert_awaited_once_with(
            db=db,
            project_id="project-123",
            user_id="user-123",
        )

    # Graph was invoked.
    graph.ainvoke.assert_awaited_once()

    state = graph.ainvoke.call_args.args[0]

    assert state["project_id"] == "project-123"

    assert state["user_request"] == (
        "Integrate Stripe payments"
    )

    assert state["repository"] == repository

    # API response returned by AgentService.
    assert result["project_id"] == "project-123"

    assert result["status"] == "plan_created"

    assert result["repository_profile"][
        "language"
    ] == "TypeScript"

    assert len(
        result["integration_candidates"]
    ) == 1

    assert result["integration_candidates"][0][
        "file"
    ] == "package.json"

    assert result["integration_plan"][
        "dependencies"
    ] == ["stripe"]

    assert result["integration_plan"][
        "files_to_modify"
    ] == ["package.json"]

    assert result["requires_confirmation"] is True

@pytest.mark.asyncio
async def test_agent_service_saves_awaiting_confirmation_status():

    repository = {
        "owner": "acme",
        "name": "payments-api",
        "default_branch": "main",
        "url": "https://github.com/acme/payments-api",
        "files": [],
    }

    repository_context_service = MagicMock()

    repository_context_service.get_repository_context = (
        AsyncMock(return_value=repository)
    )

    graph = MagicMock()

    graph.ainvoke = AsyncMock(
        return_value={
            "status": "awaiting_confirmation",
            "repository_profile": {},
            "integration_candidates": [],
            "integration_plan": {
                "request": "Integrate Stripe payments",
                "files_to_modify": [],
                "dependencies": ["stripe"],
                "steps": [],
                "requires_confirmation": True,
            },
            "confirmation_required": True,
            "confirmed": False,
        }
    )

    service = AgentService(
        repository_context_service=(
            repository_context_service
        ),
        graph_instance=graph,
    )

    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    result = await service.run(
        db=db,
        project_id="project-123",
        user_id="user-123",
        user_request="Integrate Stripe payments",
    )

    assert result["status"] == "awaiting_confirmation"

    agent_run = db.add.call_args.args[0]

    assert agent_run.status == "AWAITING_CONFIRMATION"
    assert agent_run.completed_at is  None

    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()

@pytest.mark.asyncio
async def test_agent_service_confirms_agent_run():

    project_id = uuid.uuid4()
    user_id = uuid.uuid4()
    agent_run_id = uuid.uuid4()

    integration_plan = {
        "request": "Integrate Stripe payments",
        "files_to_modify": ["package.json"],
        "dependencies": ["stripe"],
        "steps": [
            {
                "type": "dependency",
                "dependency": "stripe",
            }
        ],
        "requires_confirmation": True,
    }

    agent_run = MagicMock()
    agent_run.id = agent_run_id
    agent_run.project_id = project_id
    agent_run.user_request = "Integrate Stripe payments"
    agent_run.status = "AWAITING_CONFIRMATION"
    agent_run.integration_plan = integration_plan

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = agent_run

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=query_result
    )
    db.commit = AsyncMock()

    execution_graph = MagicMock()
    execution_graph.ainvoke = AsyncMock(
        return_value={
            "status": "changes_generated",
            "confirmed": True,
            "code_changes": [
                {
                    "type": "dependency",
                    "dependency": "stripe",
                    "action": "add",
                }
            ],
            "integration_plan": integration_plan,
        }
    )

    repository_context_service = MagicMock()
    repository_context_service.get_repository_context = (
        AsyncMock()
    )

    service = AgentService(
        repository_context_service=(
            repository_context_service
        ),
        execution_graph_instance=execution_graph,
    )

    result = await service.confirm(
        db=db,
        project_id=project_id,
        user_id=user_id,
        agent_run_id=agent_run_id,
    )

    assert result["agent_run_id"] == str(agent_run_id)
    assert result["status"] == "changes_generated"
    assert result["confirmed"] is True

    assert result["code_changes"] == [
        {
            "type": "dependency",
            "dependency": "stripe",
            "action": "add",
        }
    ]

    assert result["integration_plan"] == integration_plan

    assert agent_run.status == "COMPLETED"

    db.execute.assert_awaited_once()
    db.commit.assert_awaited_once()

    execution_graph.ainvoke.assert_awaited_once()

    called_state = (
        execution_graph.ainvoke.await_args.args[0]
    )

    assert called_state["integration_plan"] == (
        integration_plan
    )

    assert called_state["confirmed"] is True
    assert called_state["status"] == "confirmed"

    repository_context_service \
        .get_repository_context \
        .assert_not_awaited()
@pytest.mark.asyncio
async def test_agent_service_rejects_confirmation_for_completed_run():

    project_id = uuid.uuid4()
    user_id = uuid.uuid4()
    agent_run_id = uuid.uuid4()

    agent_run = MagicMock()
    agent_run.id = agent_run_id
    agent_run.project_id = project_id
    agent_run.status = "completed"

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = agent_run

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=query_result
    )

    service = AgentService(
        repository_context_service=MagicMock(),
        graph_instance=MagicMock(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.confirm(
            db=db,
            project_id=project_id,
            user_id=user_id,
            agent_run_id=agent_run_id,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Agent run is not awaiting confirmation"
    )

@pytest.mark.asyncio
async def test_agent_service_confirmation_executes_saved_plan():

    project_id = uuid.uuid4()
    user_id = uuid.uuid4()
    agent_run_id = uuid.uuid4()

    integration_plan = {
        "request": "Integrate Stripe payments",
        "files_to_modify": ["package.json"],
        "dependencies": ["stripe"],
        "steps": [
            {
                "type": "dependency",
                "dependency": "stripe",
            },
            {
                "type": "modify_file",
                "file": "package.json",
                "purpose": "Update this file for the requested integration",
            },
        ],
        "requires_confirmation": True,
    }

    agent_run = MagicMock()
    agent_run.id = agent_run_id
    agent_run.project_id = project_id
    agent_run.user_request = (
        "Integrate Stripe payments"
    )
    agent_run.status = "AWAITING_CONFIRMATION"
    agent_run.integration_plan = integration_plan

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = (
        agent_run
    )

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=query_result
    )
    db.commit = AsyncMock()

    execution_graph = MagicMock()
    execution_graph.ainvoke = AsyncMock(
        return_value={
            "status": "changes_generated",
            "confirmed": True,
            "code_changes": [
                {
                    "type": "dependency",
                    "dependency": "stripe",
                    "action": "add",
                },
                {
                    "type": "file",
                    "file": "package.json",
                    "action": "modify",
                    "purpose": (
                        "Update this file for the requested integration"
                    ),
                },
            ],
            "integration_plan": integration_plan,
        }
    )

    repository_context_service = MagicMock()
    repository_context_service.get_repository_context = (
        AsyncMock()
    )

    service = AgentService(
        repository_context_service=(
            repository_context_service
        ),
        execution_graph_instance=execution_graph,
    )

    result = await service.confirm(
        db=db,
        project_id=project_id,
        user_id=user_id,
        agent_run_id=agent_run_id,
    )

    assert result["status"] == "changes_generated"
    assert result["confirmed"] is True

    assert result["code_changes"] == [
        {
            "type": "dependency",
            "dependency": "stripe",
            "action": "add",
        },
        {
            "type": "file",
            "file": "package.json",
            "action": "modify",
            "purpose": (
                "Update this file for the requested integration"
            ),
        },
    ]

    assert agent_run.status == "COMPLETED"

    execution_graph.ainvoke.assert_awaited_once()

    called_state = (
        execution_graph.ainvoke.await_args.args[0]
    )

    assert called_state["integration_plan"] == (
        integration_plan
    )

    assert called_state["confirmed"] is True

    assert called_state["repository"] == {}

    assert called_state["repository_profile"] == {}

    assert called_state["integration_candidates"] == []

    repository_context_service \
        .get_repository_context \
        .assert_not_awaited()