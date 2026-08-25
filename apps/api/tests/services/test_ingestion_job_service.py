import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ingestion_job_service import (
    IngestionJobService,
)


@pytest.mark.asyncio
async def test_run_job_marks_job_failed():
    job_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()

    job = SimpleNamespace(
        id=job_id,
        project_id=project_id,
        status="queued",
        files_added=0,
        files_updated=0,
        files_deleted=0,
        files_unchanged=0,
        error=None,
        started_at=None,
        completed_at=None,
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = job

    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    service = IngestionJobService()

    service.ingestion_service.sync_repository = AsyncMock(
        side_effect=RuntimeError("GitHub API failed")
    )

    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock(return_value=db)
    session_context.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.services.ingestion_job_service.AsyncSessionLocal",
        return_value=session_context,
    ):
        await service.run_job(
            job_id=job_id,
            project_id=project_id,
            user_id=user_id,
        )

    assert job.status == "failed"
    assert job.error == "GitHub API failed"
    assert job.completed_at is not None