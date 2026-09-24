from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.agent_execution_service import (
    AgentExecutionService,
)


@pytest.mark.asyncio
async def test_executes_changes_and_creates_pull_request():
    repository_context_service = AsyncMock()

    repository_context_service.get_repository_context.return_value = {
        "owner": "acme",
        "name": "payments-api",
        "default_branch": "main",
        "url": "https://github.com/acme/payments-api",
        "installation_id": 123,
        "files": [],
    }

    github_service = AsyncMock()

    github_service.create_installation_access_token.return_value = {
        "token": "installation-token",
    }

    github_service.create_pull_request.return_value = {
        "number": 42,
        "html_url": (
            "https://github.com/acme/payments-api/pull/42"
        ),
    }

    github_code_executor = AsyncMock()

    github_code_executor.execute.return_value = {
        "branch_name": "agent/test-run",
        "changes_applied": 1,
        "commits": [
            {
                "file_path": "src/payment.py",
                "commit_sha": "commit-123",
            }
        ],
    }

    db = MagicMock()
    db.flush = AsyncMock()

    service = AgentExecutionService(
        repository_context_service=(
            repository_context_service
        ),
        github_service=github_service,
        github_code_executor=github_code_executor,
    )

    from uuid import UUID

    project_id = UUID(
        "00000000-0000-0000-0000-000000000001"
    )

    user_id = UUID(
        "00000000-0000-0000-0000-000000000002"
    )

    agent_run_id = UUID(
        "00000000-0000-0000-0000-000000000003"
    )

    result = await service.execute(
        db=db,
        project_id=project_id,
        user_id=user_id,
        agent_run_id=agent_run_id,
        user_request="Integrate Stripe payments",
        code_changes=[
            {
                "file_path": "src/payment.py",
                "action": "modify",
                "new_content": (
                    "import stripe\n\n"
                    "def pay():\n"
                    "    return True\n"
                ),
            }
        ],
    )

    assert result["pull_request"]["github_pr_id"] == "42"

    assert result["pull_request"]["branch_name"] == (
        f"agent/{agent_run_id}"
    )

    assert result["pull_request"]["pr_url"] == (
        "https://github.com/acme/payments-api/pull/42"
    )

    assert result["pull_request"]["status"] == "OPEN"

    repository_context_service.get_repository_context.assert_awaited()

    github_service.create_installation_access_token.assert_awaited_once_with(
        installation_id=123
    )

    github_code_executor.execute.assert_awaited_once_with(
        installation_token="installation-token",
        owner="acme",
        repo="payments-api",
        source_branch="main",
        branch_name=f"agent/{agent_run_id}",
        code_changes=[
            {
                "file_path": "src/payment.py",
                "action": "modify",
                "new_content": (
                    "import stripe\n\n"
                    "def pay():\n"
                    "    return True\n"
                ),
            }
        ],
    )

    github_service.create_pull_request.assert_awaited_once()

    db.add.assert_called_once()

    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_rejects_execution_without_code_changes():
    repository_context_service = AsyncMock()
    github_service = AsyncMock()
    github_code_executor = AsyncMock()
    db = MagicMock()

    service = AgentExecutionService(
        repository_context_service=(
            repository_context_service
        ),
        github_service=github_service,
        github_code_executor=github_code_executor,
    )

    from uuid import uuid4

    with pytest.raises(
        ValueError,
        match="no code changes generated",
    ):
        await service.execute(
            db=db,
            project_id=uuid4(),
            user_id=uuid4(),
            agent_run_id=uuid4(),
            user_request="Integrate Stripe",
            code_changes=[],
        )

    repository_context_service.get_repository_context.assert_not_awaited()
    github_code_executor.execute.assert_not_awaited()
    github_service.create_pull_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejects_missing_installation_token():
    repository_context_service = AsyncMock()

    repository_context_service.get_repository_context.return_value = {
        "owner": "acme",
        "name": "payments-api",
        "default_branch": "main",
        "url": "https://github.com/acme/payments-api",
        "installation_id": 123,
        "files": [],
    }

    github_service = AsyncMock()

    github_service.create_installation_access_token.return_value = {}

    github_code_executor = AsyncMock()

    db = MagicMock()

    service = AgentExecutionService(
        repository_context_service=(
            repository_context_service
        ),
        github_service=github_service,
        github_code_executor=github_code_executor,
    )

    from uuid import uuid4

    with pytest.raises(
        ValueError,
        match="installation token",
    ):
        await service.execute(
            db=db,
            project_id=uuid4(),
            user_id=uuid4(),
            agent_run_id=uuid4(),
            user_request="Integrate Stripe",
            code_changes=[
                {
                    "file_path": "src/payment.py",
                    "new_content": "print('hello')\n",
                }
            ],
        )

    github_code_executor.execute.assert_not_awaited()
    github_service.create_pull_request.assert_not_awaited()
