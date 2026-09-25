import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_installation import GitHubInstallation
from app.models.project import Project
from app.models.repository import Repository
from app.services.github_content_service import GitHubContentService
from app.services.github_service import GitHubService


class RepositoryContextService:

    PROFILE_PATHS = {
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "requirements.txt",
        "pyproject.toml",
        "poetry.lock",
        "Pipfile",
        "Pipfile.lock",
        "pytest.ini",
        "tsconfig.json",
        "Dockerfile",
        "docker-compose.yml",
        "prisma/schema.prisma",
    }

    MAX_FILES = 100
    MAX_FILE_SIZE = 100_000

    SKIP_DIRECTORIES = {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        ".next",
    }

    def __init__(self):
        self.github_service = GitHubService()

    async def get_repository_context(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> dict:

        # 1. Verify project ownership
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
        )

        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(
                status_code=404,
                detail="Project not found",
            )

        # 2. Get repository
        result = await db.execute(
            select(Repository).where(
                Repository.project_id == project.id,
            )
        )

        repository = result.scalar_one_or_none()

        if not repository:
            raise HTTPException(
                status_code=404,
                detail="Repository not found",
            )

        # 3. Get GitHub installation
        result = await db.execute(
            select(GitHubInstallation).where(
                GitHubInstallation.user_id == user_id,
            )
        )

        installation = result.scalar_one_or_none()

        if not installation:
            raise HTTPException(
                status_code=404,
                detail="GitHub installation not found",
            )

        # 4. Create short-lived installation token
        token_data = await self.github_service.create_installation_access_token(
            installation.installation_id
        )

        installation_token = token_data.get("token")

        if not installation_token:
            raise HTTPException(
                status_code=502,
                detail="GitHub installation token was not returned",
            )

        # 5. Fetch profile files
        files = []

        for path in self.PROFILE_PATHS:
            try:
                contents = await self.github_service.get_repository_contents(
                    installation_token=installation_token,
                    owner=repository.owner,
                    repo=repository.name,
                    path=path,
                    ref=repository.default_branch,
                )

            except Exception:
                # The profile file may not exist
                continue

            if not isinstance(contents, dict):
                continue

            if contents.get("type") != "file":
                continue

            encoded_content = contents.get("content")

            if not encoded_content:
                continue

            content = GitHubContentService.decode_file_content(
                encoded_content
            )

            if content is None:
                continue

            if len(content) > self.MAX_FILE_SIZE:
                continue

            files.append(
                {
                    "path": path,
                    "content": content,
                }
            )

        return {
            "owner": repository.owner,
            "name": repository.name,
            "default_branch": repository.default_branch,
            "url": repository.url,
            "installation_id": installation.installation_id,
            "files": files,
        }

    async def _fetch_repository_files(
        self,
        installation_token: str,
        owner: str,
        repo: str,
        ref: str,
    ) -> list[dict]:

        files: list[dict] = []
        visited_paths: set[str] = set()

        async def walk(path: str) -> None:
            # Stop once we reach the maximum number of files
            if len(files) >= self.MAX_FILES:
                return

            # Prevent visiting the same path twice
            if path in visited_paths:
                return

            visited_paths.add(path)

            try:
                contents = (
                    await self.github_service.get_repository_contents(
                        installation_token=installation_token,
                        owner=owner,
                        repo=repo,
                        path=path,
                        ref=ref,
                    )
                )
            except Exception:
                return

            # Directory response
            if isinstance(contents, list):

                for item in contents:
                    if len(files) >= self.MAX_FILES:
                        return

                    item_path = item.get("path")
                    item_type = item.get("type")

                    if not item_path:
                        continue

                    # Check every component of the path
                    parts = set(item_path.split("/"))

                    if parts.intersection(self.SKIP_DIRECTORIES):
                        continue

                    if item_type in {"dir", "file"}:
                        await walk(item_path)

                return

            # File response
            if not isinstance(contents, dict):
                return

            if contents.get("type") != "file":
                return

            encoded_content = contents.get("content")

            if not encoded_content:
                return

            content = GitHubContentService.decode_file_content(
                encoded_content
            )

            if content is None:
                return

            if len(content) > self.MAX_FILE_SIZE:
                return

            files.append(
                {
                    "path": path,
                    "content": content,
                }
            )

        # Start traversal from repository root
        await walk("")

        return files