import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ingestion_service import IngestionService


@pytest.fixture
def service():
    return IngestionService()


@pytest.fixture
def project_id():
    return uuid.uuid4()


@pytest.fixture
def user_id():
    return uuid.uuid4()


def make_execute_result(value):
    result = MagicMock()

    result.scalar_one_or_none.return_value = value

    if isinstance(value, list):
        result.scalars.return_value.all.return_value = value
    else:
        result.scalars.return_value.all.return_value = []

    return result


def setup_common_objects(project_id):
    project = SimpleNamespace(
        id=project_id,
    )

    repository = SimpleNamespace(
        project_id=project_id,
        owner="test-owner",
        name="test-repo",
        default_branch="main",
    )

    installation = SimpleNamespace(
        installation_id=123,
    )

    knowledge_source = SimpleNamespace(
        id=uuid.uuid4(),
        project_id=project_id,
    )

    return (
        project,
        repository,
        installation,
        knowledge_source,
    )


def setup_db(
    project,
    repository,
    installation,
    knowledge_source,
    existing_documents,
):
    db = MagicMock()

    db.execute = AsyncMock(
        side_effect=[
            make_execute_result(project),
            make_execute_result(repository),
            make_execute_result(installation),
            make_execute_result(knowledge_source),
            make_execute_result(existing_documents),
        ]
    )

    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.delete = AsyncMock()

    return db


@pytest.mark.asyncio
async def test_sync_repository_unchanged_file(
    service,
    project_id,
    user_id,
):
    (
        project,
        repository,
        installation,
        knowledge_source,
    ) = setup_common_objects(project_id)

    existing_document = SimpleNamespace(
        id=uuid.uuid4(),
        github_path="README.md",
        github_sha="same-sha",
    )

    db = setup_db(
        project,
        repository,
        installation,
        knowledge_source,
        [existing_document],
    )

    service.github_service.create_installation_access_token = (
        AsyncMock(
            return_value={
                "token": "installation-token"
            }
        )
    )

    service.github_service.get_repository_contents = (
        AsyncMock(
            return_value=[
                {
                    "path": "README.md",
                    "type": "file",
                    "sha": "same-sha",
                }
            ]
        )
    )

    result = await service.sync_repository(
        db=db,
        project_id=project_id,
        user_id=user_id,
    )

    assert result["added"] == 0
    assert result["updated"] == 0
    assert result["deleted"] == 0
    assert result["unchanged"] == 1

    db.delete.assert_not_called()


@pytest.mark.asyncio
async def test_sync_repository_added_file(
    service,
    project_id,
    user_id,
):
    (
        project,
        repository,
        installation,
        knowledge_source,
    ) = setup_common_objects(project_id)

    db = setup_db(
        project,
        repository,
        installation,
        knowledge_source,
        [],
    )

    service.github_service.create_installation_access_token = (
        AsyncMock(
            return_value={
                "token": "installation-token"
            }
        )
    )

    service.github_service.get_repository_contents = (
        AsyncMock(
            side_effect=[
                [
                    {
                        "path": "README.md",
                        "type": "file",
                        "sha": "new-sha",
                    }
                ],
                {
                    "type": "file",
                    "path": "README.md",
                    "sha": "new-sha",
                    "content": "SGVsbG8=",
                },
            ]
        )
    )

    service.chunking_service.split = MagicMock(
        return_value=["Hello"]
    )

    result = await service.sync_repository(
        db=db,
        project_id=project_id,
        user_id=user_id,
    )

    assert result["added"] == 1
    assert result["updated"] == 0
    assert result["deleted"] == 0
    assert result["unchanged"] == 0


@pytest.mark.asyncio
async def test_sync_repository_updated_file(
    service,
    project_id,
    user_id,
):
    (
        project,
        repository,
        installation,
        knowledge_source,
    ) = setup_common_objects(project_id)

    existing_document = SimpleNamespace(
        id=uuid.uuid4(),
        github_path="README.md",
        github_sha="old-sha",
    )

    db = setup_db(
        project,
        repository,
        installation,
        knowledge_source,
        [existing_document],
    )

    service.github_service.create_installation_access_token = (
        AsyncMock(
            return_value={
                "token": "installation-token"
            }
        )
    )

    service.github_service.get_repository_contents = (
        AsyncMock(
            side_effect=[
                [
                    {
                        "path": "README.md",
                        "type": "file",
                        "sha": "new-sha",
                    }
                ],
                {
                    "type": "file",
                    "path": "README.md",
                    "sha": "new-sha",
                    "content": "VXBkYXRlZA==",
                },
            ]
        )
    )

    service.chunking_service.split = MagicMock(
        return_value=["Updated"]
    )

    result = await service.sync_repository(
        db=db,
        project_id=project_id,
        user_id=user_id,
    )

    assert result["added"] == 0
    assert result["updated"] == 1
    assert result["deleted"] == 0
    assert result["unchanged"] == 0

    db.delete.assert_called_once_with(
        existing_document
    )


@pytest.mark.asyncio
async def test_sync_repository_deleted_file(
    service,
    project_id,
    user_id,
):
    (
        project,
        repository,
        installation,
        knowledge_source,
    ) = setup_common_objects(project_id)

    existing_document = SimpleNamespace(
        id=uuid.uuid4(),
        github_path="README.md",
        github_sha="old-sha",
    )

    db = setup_db(
        project,
        repository,
        installation,
        knowledge_source,
        [existing_document],
    )

    service.github_service.create_installation_access_token = (
        AsyncMock(
            return_value={
                "token": "installation-token"
            }
        )
    )

    service.github_service.get_repository_contents = (
        AsyncMock(
            return_value=[]
        )
    )

    result = await service.sync_repository(
        db=db,
        project_id=project_id,
        user_id=user_id,
    )

    assert result["added"] == 0
    assert result["updated"] == 0
    assert result["deleted"] == 1
    assert result["unchanged"] == 0

    db.delete.assert_called_once_with(
        existing_document
    )