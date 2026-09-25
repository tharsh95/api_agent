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

    repository_context_service \
        .get_repository_context \
        .assert_awaited_once_with(
            db=db,
            project_id="project-123",
            user_id="user-123",
        )

    graph.ainvoke.assert_awaited_once()

    state = graph.ainvoke.call_args.args[0]

    assert state["project_id"] == "project-123"

    assert state["user_request"] == (
        "Integrate Stripe payments"
    )

    assert state["repository"] == repository

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
    assert agent_run.completed_at is None

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

    repository = {
        "owner": "test-owner",
        "name": "test-repo",
        "default_branch": "main",
        "files": [
            {
                "path": "package.json",
                "content": '{"dependencies": {}}',
            }
        ],
    }

    repository_context_service.get_repository_context = (
        AsyncMock(
            return_value=repository
        )
    )

    agent_execution_service = MagicMock()
    agent_execution_service.execute = AsyncMock(
        return_value={
            "execution": {
                "branch_name": "agent/test",
                "changes_applied": 1,
                "commits": [],
            },
            "validation": {
                "status": "passed",
                "passed": True,
                "exit_code": 0,
                "stdout": "Tests passed",
                "stderr": "",
            },
            "pull_request": {
                "id": str(uuid.uuid4()),
                "github_pr_id": "42",
                "branch_name": "agent/test",
                "pr_url": "https://github.com/test-owner/test-repo/pull/42",
                "status": "OPEN",
            },
        }
    )

    service = AgentService(
        repository_context_service=(
            repository_context_service
        ),
        execution_graph_instance=execution_graph,
        agent_execution_service=agent_execution_service,
    )

    result = await service.confirm(
        db=db,
        project_id=project_id,
        user_id=user_id,
        agent_run_id=agent_run_id,
    )

    assert result["agent_run_id"] == str(agent_run_id)
    assert result["status"] == "COMPLETED"
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

    repository_context_service \
        .get_repository_context \
        .assert_awaited_once_with(
            db=db,
            project_id=project_id,
            user_id=user_id,
        )

    execution_graph.ainvoke.assert_awaited_once()

    called_state = (
        execution_graph.ainvoke.await_args.args[0]
    )

    assert called_state["integration_plan"] == (
        integration_plan
    )

    assert called_state["confirmed"] is True
    assert called_state["status"] == "confirmed"
    assert called_state["repository"] == repository


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
                "purpose": (
                    "Update this file for the requested integration"
                ),
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

    repository = {
        "owner": "test-owner",
        "name": "test-repo",
        "default_branch": "main",
        "files": [
            {
                "path": "package.json",
                "content": '{"dependencies": {}}',
            }
        ],
    }

    repository_context_service.get_repository_context = (
        AsyncMock(
            return_value=repository
        )
    )

    agent_execution_service = MagicMock()
    agent_execution_service.execute = AsyncMock(
        return_value={
            "execution": {
                "branch_name": "agent/test",
                "changes_applied": 1,
                "commits": [],
            },
            "validation": {
                "status": "passed",
                "passed": True,
                "exit_code": 0,
                "stdout": "Tests passed",
                "stderr": "",
            },
            "pull_request": {
                "id": str(uuid.uuid4()),
                "github_pr_id": "42",
                "branch_name": "agent/test",
                "pr_url": "https://github.com/test-owner/test-repo/pull/42",
                "status": "OPEN",
            },
        }
    )

    service = AgentService(
        repository_context_service=(
            repository_context_service
        ),
        execution_graph_instance=execution_graph,
        agent_execution_service=agent_execution_service,
    )

    result = await service.confirm(
        db=db,
        project_id=project_id,
        user_id=user_id,
        agent_run_id=agent_run_id,
    )

    assert result["status"] == "COMPLETED"
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

    assert called_state["repository"] == repository

    assert called_state["repository_profile"] == {}

    assert called_state["integration_candidates"] == []

    repository_context_service \
        .get_repository_context \
        .assert_awaited_once_with(
            db=db,
            project_id=project_id,
            user_id=user_id,
        )

@pytest.mark.asyncio
async def test_agent_service_confirmation_creates_pull_request():
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()
    agent_run_id = uuid.uuid4()

    integration_plan = {
        "request": "Integrate Stripe payments",
        "files_to_modify": ["src/payment.py"],
        "dependencies": ["stripe"],
        "steps": [
            {
                "type": "modify_file",
                "file": "src/payment.py",
                "purpose": "Integrate Stripe payments",
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

    repository = {
        "owner": "acme",
        "name": "payments-api",
        "default_branch": "main",
        "installation_id": 123,
        "files": [
            {
                "path": "src/payment.py",
                "content": (
                    "def pay():\n"
                    "    pass\n"
                ),
            }
        ],
    }

    repository_context_service = MagicMock()
    repository_context_service.get_repository_context = (
        AsyncMock(
            return_value=repository
        )
    )

    code_changes = [
        {
            "file_path": "src/payment.py",
            "action": "modify",
            "original_content": (
                "def pay():\n"
                "    pass\n"
            ),
            "new_content": (
                "import stripe\n\n"
                "def pay():\n"
                "    return True\n"
            ),
            "diff": "test-diff",
        }
    ]

    execution_graph = MagicMock()
    execution_graph.ainvoke = AsyncMock(
        return_value={
            "status": "changes_generated",
            "confirmed": True,
            "code_changes": code_changes,
            "integration_plan": integration_plan,
        }
    )

    agent_execution_service = MagicMock()
    agent_execution_service.execute = AsyncMock(
        return_value={
            "execution": {
                "branch_name": f"agent/{agent_run_id}",
                "changes_applied": 1,
                "commits": [
                    {
                        "file_path": "src/payment.py",
                        "commit_sha": "commit-123",
                    }
                ],
            },
            "validation": {
                "status": "passed",
                "passed": True,
                "exit_code": 0,
                "stdout": "Tests passed",
                "stderr": "",
            },
            "pull_request": {
                "id": str(uuid.uuid4()),
                "github_pr_id": "42",
                "branch_name": f"agent/{agent_run_id}",
                "pr_url": (
                    "https://github.com/"
                    "acme/payments-api/pull/42"
                ),
                "status": "OPEN",
            },
        }
    )

    service = AgentService(
        repository_context_service=(
            repository_context_service
        ),
        execution_graph_instance=execution_graph,
        agent_execution_service=(
            agent_execution_service
        ),
    )

    result = await service.confirm(
        db=db,
        project_id=project_id,
        user_id=user_id,
        agent_run_id=agent_run_id,
    )

    agent_execution_service.execute.assert_awaited_once_with(
        db=db,
        project_id=project_id,
        user_id=user_id,
        agent_run_id=agent_run_id,
        user_request="Integrate Stripe payments",
        code_changes=code_changes,
    )

    assert agent_run.status == "COMPLETED"
    assert agent_run.completed_at is not None

    assert result["pull_request"][
        "github_pr_id"
    ] == "42"

    assert result["pull_request"]["pr_url"] == (
        "https://github.com/"
        "acme/payments-api/pull/42"
    )

    assert result["execution"][
        "execution"
    ]["changes_applied"] == 1

    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_agent_service_confirmation_creates_pull_request():
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()
    agent_run_id = uuid.uuid4()

    integration_plan = {
        "request": "Integrate Stripe payments",
        "files_to_modify": ["src/payment.py"],
        "dependencies": ["stripe"],
        "steps": [
            {
                "type": "modify_file",
                "file": "src/payment.py",
                "purpose": "Integrate Stripe payments",
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

    repository = {
        "owner": "acme",
        "name": "payments-api",
        "default_branch": "main",
        "installation_id": 123,
        "files": [
            {
                "path": "src/payment.py",
                "content": (
                    "def pay():\n"
                    "    pass\n"
                ),
            }
        ],
    }

    repository_context_service = MagicMock()
    repository_context_service.get_repository_context = (
        AsyncMock(
            return_value=repository
        )
    )

    code_changes = [
        {
            "file_path": "src/payment.py",
            "action": "modify",
            "original_content": (
                "def pay():\n"
                "    pass\n"
            ),
            "new_content": (
                "import stripe\n\n"
                "def pay():\n"
                "    return True\n"
            ),
            "diff": "test-diff",
        }
    ]

    execution_graph = MagicMock()
    execution_graph.ainvoke = AsyncMock(
        return_value={
            "status": "changes_generated",
            "confirmed": True,
            "code_changes": code_changes,
            "integration_plan": integration_plan,
        }
    )

    agent_execution_service = MagicMock()
    agent_execution_service.execute = AsyncMock(
        return_value={
            "execution": {
                "branch_name": f"agent/{agent_run_id}",
                "changes_applied": 1,
                "commits": [
                    {
                        "file_path": "src/payment.py",
                        "commit_sha": "commit-123",
                    }
                ],
            },
            "validation": {
                "status": "passed",
                "passed": True,
                "exit_code": 0,
                "stdout": "Tests passed",
                "stderr": "",
            },
            "pull_request": {
                "id": str(uuid.uuid4()),
                "github_pr_id": "42",
                "branch_name": f"agent/{agent_run_id}",
                "pr_url": (
                    "https://github.com/"
                    "acme/payments-api/pull/42"
                ),
                "status": "OPEN",
            },
        }
    )

    service = AgentService(
        repository_context_service=(
            repository_context_service
        ),
        execution_graph_instance=execution_graph,
        agent_execution_service=(
            agent_execution_service
        ),
    )

    result = await service.confirm(
        db=db,
        project_id=project_id,
        user_id=user_id,
        agent_run_id=agent_run_id,
    )

    agent_execution_service.execute.assert_awaited_once_with(
        db=db,
        project_id=project_id,
        user_id=user_id,
        agent_run_id=agent_run_id,
        user_request="Integrate Stripe payments",
        code_changes=code_changes,
    )

    assert agent_run.status == "COMPLETED"
    assert agent_run.completed_at is not None

    assert result["pull_request"][
        "github_pr_id"
    ] == "42"

    assert result["pull_request"]["pr_url"] == (
        "https://github.com/"
        "acme/payments-api/pull/42"
    )

    assert result["execution"][
        "execution"
    ]["changes_applied"] == 1

    db.commit.assert_awaited_once()
