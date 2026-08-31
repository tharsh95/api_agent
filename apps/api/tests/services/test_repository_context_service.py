import base64
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.repository_context_service import (
    RepositoryContextService,
)


@pytest.mark.asyncio
async def test_get_repository_context():
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()

    repository = MagicMock()
    repository.id = uuid.uuid4()
    repository.project_id = project_id
    repository.owner = "acme"
    repository.name = "payments-api"
    repository.default_branch = "main"
    repository.url = (
        "https://github.com/acme/payments-api"
    )

    installation = MagicMock()
    installation.installation_id = 12345

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = (
        MagicMock(
            id=project_id,
            user_id=user_id,
        )
    )

    repository_result = MagicMock()
    repository_result.scalar_one_or_none.return_value = (
        repository
    )

    installation_result = MagicMock()
    installation_result.scalar_one_or_none.return_value = (
        installation
    )

    db = MagicMock()

    db.execute = AsyncMock(
        side_effect=[
            project_result,
            repository_result,
            installation_result,
        ]
    )

    github_service = AsyncMock()

    github_service.create_installation_access_token \
        = AsyncMock(
            return_value={
                "token": "fake-installation-token",
            }
        )

    encoded = base64.b64encode(
        b'{"name": "payments-api"}'
    ).decode()

    github_service.get_repository_contents = (
        AsyncMock(
            side_effect=lambda **kwargs: {
                "type": "file",
                "content": encoded,
            }
            if kwargs["path"] == "package.json"
            else {
                "type": "file",
                "content": base64.b64encode(
                    b"test content"
                ).decode(),
            }
        )
    )

    service = RepositoryContextService()
    service.github_service = github_service

    result = await service.get_repository_context(
        db=db,
        project_id=project_id,
        user_id=user_id,
    )

    assert result["owner"] == "acme"
    assert result["name"] == "payments-api"
    assert result["default_branch"] == "main"
    assert result["url"] == (
        "https://github.com/acme/payments-api"
    )

    assert len(result["files"]) > 0

    package_file = next(
        file
        for file in result["files"]
        if file["path"] == "package.json"
    )

    assert package_file["content"] == (
        '{"name": "payments-api"}'
    )

    github_service.create_installation_access_token \
        .assert_awaited_once_with(12345)