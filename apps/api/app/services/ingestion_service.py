import base64
import binascii
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.github_installation import GitHubInstallation
from app.models.knowledge_source import KnowledgeSource
from app.models.project import Project
from app.models.repository import Repository
from app.services.chunking_service import ChunkingService
from app.services.github_service import GitHubService


class IngestionService:
    def __init__(self):
        self.github_service = GitHubService()
        self.chunking_service = ChunkingService()

    async def ingest_files(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        paths: list[str],
    ) -> dict:

        # 1. Verify project belongs to user
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

        # 4. Generate fresh installation token
        token_data = (
            await self.github_service
            .create_installation_access_token(
                installation.installation_id
            )
        )

        installation_token = token_data.get("token")

        if not installation_token:
            raise HTTPException(
                status_code=502,
                detail="GitHub installation token was not returned",
            )

        # 5. Get/create knowledge source
        result = await db.execute(
            select(KnowledgeSource).where(
                KnowledgeSource.project_id == project.id,
                KnowledgeSource.source_type == "repository",
                KnowledgeSource.provider == "github",
            )
        )

        knowledge_source = result.scalar_one_or_none()

        if not knowledge_source:
            knowledge_source = KnowledgeSource(
                project_id=project.id,
                name=repository.name,
                source_type="repository",
                provider="github",
                source_url=repository.url,
            )

            db.add(knowledge_source)
            await db.flush()

        documents_created = 0
        chunks_created = 0

        # Empty paths means ingest the whole repository.
        if not paths:
            paths = [""]

        # Track files we've already visited.
        visited_paths: set[str] = set()

        async def ingest_path(
            file_path: str,
        ) -> None:
            nonlocal documents_created
            nonlocal chunks_created

            if file_path in visited_paths:
                return

            visited_paths.add(file_path)

            contents = (
                await self.github_service
                .get_repository_contents(
                    installation_token=installation_token,
                    owner=repository.owner,
                    repo=repository.name,
                    path=file_path,
                    ref=repository.default_branch,
                )
            )

            # Directory
            if isinstance(contents, list):
                for item in contents:
                    item_path = item.get("path")
                    item_type = item.get("type")

                    if not item_path:
                        continue

                    if item_type == "dir":
                        await ingest_path(item_path)

                    elif item_type == "file":
                        await ingest_path(item_path)

                return

            # Anything other than a file is invalid.
            if not isinstance(contents, dict):
                return

            if contents.get("type") != "file":
                return

            encoded_content = contents.get("content")

            if not encoded_content:
                return

            # GitHub sometimes returns whitespace/newline characters
            # around the base64 content.
            encoded_content = encoded_content.replace(
                "\n",
                "",
            )

            try:
                decoded_content = base64.b64decode(
                    encoded_content
                ).decode("utf-8")

            except (
                binascii.Error,
                UnicodeDecodeError,
            ):
                # Skip binary/non-UTF-8 files.
                return

            github_sha = contents.get("sha")

            result = await db.execute(
                select(Document).where(
                    Document.knowledge_source_id
                    == knowledge_source.id,
                    Document.github_path == file_path,
                )
            )

            existing_document = (
                result.scalar_one_or_none()
            )

            # File has not changed.
            if (
                existing_document
                and existing_document.github_sha
                == github_sha
            ):
                return

            # File changed.
            if existing_document:
                await db.delete(existing_document)
                await db.flush()

            document = Document(
                knowledge_source_id=knowledge_source.id,
                title=file_path,
                content=decoded_content,
                github_path=file_path,
                github_sha=github_sha,
            )

            db.add(document)
            await db.flush()

            documents_created += 1

            # Chunk document.
            chunks = self.chunking_service.split(
                decoded_content
            )

            for chunk_index, chunk_content in enumerate(
                chunks
            ):
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk_index,
                    content=chunk_content,
                    metadata_={
                        "source": "github",
                        "path": file_path,
                        "sha": github_sha,
                        "repository": (
                            f"{repository.owner}/"
                            f"{repository.name}"
                        ),
                        "branch": (
                            repository.default_branch
                        ),
                    },
                )

                db.add(chunk)
                chunks_created += 1

        # 6. Recursively ingest requested paths.
        for path in paths:
            await ingest_path(path)

        await db.commit()

        return {
            "status": "completed",
            "project_id": str(project.id),
            "repository": (
                f"{repository.owner}/"
                f"{repository.name}"
            ),
            "documents_created": documents_created,
            "chunks_created": chunks_created,
        }