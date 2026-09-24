from unittest.mock import AsyncMock

import pytest

from app.services.github_code_executor import (
    GitHubCodeExecutor,
)


@pytest.mark.asyncio
async def test_executes_generated_code_changes():
    github_service = AsyncMock()

    github_service.create_branch.return_value = {
        "ref": "refs/heads/agent/stripe-integration",
    }

    github_service.get_file.side_effect = [
        {
            "path": "src/payment.py",
            "sha": "payment-file-sha",
        },
        {
            "path": "tests/test_payment.py",
            "sha": "test-file-sha",
        },
    ]

    github_service.create_or_update_file.side_effect = [
        {
            "content": {
                "path": "src/payment.py",
            },
            "commit": {
                "sha": "commit-1",
            },
        },
        {
            "content": {
                "path": "tests/test_payment.py",
            },
            "commit": {
                "sha": "commit-2",
            },
        },
    ]

    executor = GitHubCodeExecutor(
        github_service=github_service,
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
            "diff": "--- payment diff ---",
        },
        {
            "file_path": "tests/test_payment.py",
            "action": "modify",
            "original_content": (
                "def test_pay():\n"
                "    pass\n"
            ),
            "new_content": (
                "def test_pay():\n"
                "    assert True\n"
            ),
            "diff": "--- test diff ---",
        },
    ]

    result = await executor.execute(
        installation_token="installation-token",
        owner="acme",
        repo="payments-api",
        source_branch="main",
        branch_name="agent/stripe-integration",
        code_changes=code_changes,
    )

    assert result["branch_name"] == (
        "agent/stripe-integration"
    )

    assert result["changes_applied"] == 2

    assert result["commits"] == [
        {
            "file_path": "src/payment.py",
            "commit_sha": "commit-1",
        },
        {
            "file_path": "tests/test_payment.py",
            "commit_sha": "commit-2",
        },
    ]

    github_service.create_branch.assert_awaited_once_with(
        installation_token="installation-token",
        owner="acme",
        repo="payments-api",
        branch_name="agent/stripe-integration",
        source_branch="main",
    )

    assert github_service.get_file.await_count == 2

    github_service.get_file.assert_any_await(
        installation_token="installation-token",
        owner="acme",
        repo="payments-api",
        path="src/payment.py",
        branch="agent/stripe-integration",
    )

    github_service.get_file.assert_any_await(
        installation_token="installation-token",
        owner="acme",
        repo="payments-api",
        path="tests/test_payment.py",
        branch="agent/stripe-integration",
    )

    github_service.create_or_update_file.assert_any_await(
        installation_token="installation-token",
        owner="acme",
        repo="payments-api",
        path="src/payment.py",
        content=(
            "import stripe\n\n"
            "def pay():\n"
            "    return True\n"
        ),
        branch="agent/stripe-integration",
        message="feat: update src/payment.py",
        sha="payment-file-sha",
    )

    github_service.create_or_update_file.assert_any_await(
        installation_token="installation-token",
        owner="acme",
        repo="payments-api",
        path="tests/test_payment.py",
        content=(
            "def test_pay():\n"
            "    assert True\n"
        ),
        branch="agent/stripe-integration",
        message="feat: update tests/test_payment.py",
        sha="test-file-sha",
    )


@pytest.mark.asyncio
async def test_rejects_empty_code_changes():
    github_service = AsyncMock()

    executor = GitHubCodeExecutor(
        github_service=github_service,
    )

    with pytest.raises(
        ValueError,
        match="no changes provided",
    ):
        await executor.execute(
            installation_token="installation-token",
            owner="acme",
            repo="payments-api",
            source_branch="main",
            branch_name="agent/test",
            code_changes=[],
        )

    github_service.create_branch.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejects_missing_file_path():
    github_service = AsyncMock()

    executor = GitHubCodeExecutor(
        github_service=github_service,
    )

    with pytest.raises(
        ValueError,
        match="missing file_path",
    ):
        await executor.execute(
            installation_token="installation-token",
            owner="acme",
            repo="payments-api",
            source_branch="main",
            branch_name="agent/test",
            code_changes=[
                {
                    "new_content": "print('hello')\n",
                }
            ],
        )

    github_service.create_branch.assert_awaited_once()


@pytest.mark.asyncio
async def test_rejects_missing_new_content():
    github_service = AsyncMock()

    executor = GitHubCodeExecutor(
        github_service=github_service,
    )

    with pytest.raises(
        ValueError,
        match="missing new_content",
    ):
        await executor.execute(
            installation_token="installation-token",
            owner="acme",
            repo="payments-api",
            source_branch="main",
            branch_name="agent/test",
            code_changes=[
                {
                    "file_path": "src/payment.py",
                }
            ],
        )

    github_service.create_branch.assert_awaited_once()


@pytest.mark.asyncio
async def test_rejects_missing_github_file_sha():
    github_service = AsyncMock()

    github_service.create_branch.return_value = {
        "ref": "refs/heads/agent/test",
    }

    github_service.get_file.return_value = {
        "path": "src/payment.py",
    }

    executor = GitHubCodeExecutor(
        github_service=github_service,
    )

    with pytest.raises(
        ValueError,
        match="did not return a SHA",
    ):
        await executor.execute(
            installation_token="installation-token",
            owner="acme",
            repo="payments-api",
            source_branch="main",
            branch_name="agent/test",
            code_changes=[
                {
                    "file_path": "src/payment.py",
                    "new_content": "print('hello')\n",
                }
            ],
        )

    github_service.create_or_update_file.assert_not_awaited()
