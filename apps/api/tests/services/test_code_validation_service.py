import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.code_validation_service import CodeValidationService


@pytest.fixture
def service():
    return CodeValidationService()


@pytest.fixture
def repo(tmp_path):
    package = {
        "name": "test-project",
        "scripts": {"test": "vitest run"},
    }
    (tmp_path / "package.json").write_text(json.dumps(package))
    return tmp_path


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lockfile,expected_install,expected_test",
    [
        (
            "package-lock.json",
            "npm ci --ignore-scripts --no-audit --no-fund",
            "npm test",
        ),
        (
            "yarn.lock",
            "corepack yarn install --immutable --mode=skip-builds",
            "corepack yarn test",
        ),
        (
            "pnpm-lock.yaml",
            "corepack pnpm install --frozen-lockfile --ignore-scripts",
            "corepack pnpm test",
        ),
    ],
)
async def test_uses_matching_package_manager(
    service,
    repo,
    lockfile,
    expected_install,
    expected_test,
):
    (repo / lockfile).write_text("")

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        b"Tests passed",
        b"",
    )
    mock_process.returncode = 0

    with patch(
        "app.services.code_validation_service.asyncio.create_subprocess_exec",
        return_value=mock_process,
    ) as run:
        result = await service._run_node_validation(str(repo))

    assert result["status"] == "passed"

    command = run.call_args.args
    shell_script = command[-1]

    assert expected_install in shell_script
    assert expected_test in shell_script
    assert "--runInBand" not in shell_script


@pytest.mark.asyncio
async def test_returns_failed_when_tests_fail(service, repo):
    (repo / "package-lock.json").write_text("")

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        b"Tests failed",
        b"AssertionError",
    )
    mock_process.returncode = 1

    with patch(
        "app.services.code_validation_service.asyncio.create_subprocess_exec",
        return_value=mock_process,
    ):
        result = await service._run_node_validation(str(repo))

    assert result["status"] == "failed"
    assert result["passed"] is False
    assert result["exit_code"] == 1
    assert "AssertionError" in result["stderr"]


@pytest.mark.asyncio
async def test_skips_when_package_json_is_missing(service, tmp_path):
    result = await service._run_node_validation(str(tmp_path))

    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_skips_when_test_script_is_missing(service, tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "test-project", "scripts": {}})
    )

    result = await service._run_node_validation(str(tmp_path))

    assert result["status"] == "skipped"
