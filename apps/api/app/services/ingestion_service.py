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

    async def sync_repository(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> dict:
        # Reuse the existing ingestion flow for the entire repository.
        #
        # The important difference is that we also compare the files
        # currently on GitHub against the documents stored in the DB.

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

        # 4. Get knowledge source
        result = await db.execute(
            select(KnowledgeSource).where(
                KnowledgeSource.project_id == project.id,
                KnowledgeSource.source_type == "repository",
                KnowledgeSource.provider == "github",
            )
        )

        knowledge_source = result.scalar_one_or_none()

        if not knowledge_source:
            raise HTTPException(
                status_code=404,
                detail="Knowledge source not found",
            )

        # 5. Get current repository tree from GitHub
        contents = await self.github_service.get_repository_contents(
            installation_token=installation_token,
            owner=repository.owner,
            repo=repository.name,
            path="",
            ref=repository.default_branch,
        )

        current_files: dict[str, str] = {}

        async def collect_files(
            items: list[dict],
        ) -> None:
            for item in items:
                item_path = item.get("path")
                item_type = item.get("type")

                if not item_path:
                    continue

                if item_type == "file":
                    sha = item.get("sha")

                    if sha:
                        current_files[item_path] = sha

                elif item_type == "dir":
                    directory_contents = (
                        await self.github_service
                        .get_repository_contents(
                            installation_token=installation_token,
                            owner=repository.owner,
                            repo=repository.name,
                            path=item_path,
                            ref=repository.default_branch,
                        )
                    )

                    if isinstance(directory_contents, list):
                        await collect_files(directory_contents)

        if isinstance(contents, list):
            await collect_files(contents)

        # 6. Get documents currently stored
        result = await db.execute(
            select(Document).where(
                Document.knowledge_source_id
                == knowledge_source.id
            )
        )

        existing_documents = result.scalars().all()

        existing_by_path = {
            document.github_path: document
            for document in existing_documents
            if document.github_path
        }

        added = 0
        updated = 0
        deleted = 0
        unchanged = 0

        # 7. Delete documents whose files disappeared from GitHub
        for path, document in existing_by_path.items():
            if path not in current_files:
                await db.delete(document)
                deleted += 1

        await db.flush()

        # 8. Ingest new/changed files
        for path, github_sha in current_files.items():
            existing_document = existing_by_path.get(path)

            if (
                existing_document
                and existing_document.github_sha == github_sha
            ):
                unchanged += 1
                continue

            contents = await self.github_service.get_repository_contents(
                installation_token=installation_token,
                owner=repository.owner,
                repo=repository.name,
                path=path,
                ref=repository.default_branch,
            )

            if not isinstance(contents, dict):
                continue

            if contents.get("type") != "file":
                continue

            encoded_content = contents.get("content")

            if not encoded_content:
                continue

            encoded_content = encoded_content.replace("\n", "")

            try:
                decoded_content = base64.b64decode(
                    encoded_content
                ).decode("utf-8")
            except (
                binascii.Error,
                UnicodeDecodeError,
            ):
                continue

            if existing_document:
                await db.delete(existing_document)
                await db.flush()
                updated += 1
            else:
                added += 1

            document = Document(
                knowledge_source_id=knowledge_source.id,
                title=path,
                content=decoded_content,
                github_path=path,
                github_sha=github_sha,
            )

            db.add(document)
            await db.flush()

            chunks = self.chunking_service.split(
                decoded_content
            )

            for chunk_index, chunk_content in enumerate(chunks):
                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=chunk_index,
                        content=chunk_content,
                        metadata_={
                            "source": "github",
                            "path": path,
                            "sha": github_sha,
                            "repository": (
                                f"{repository.owner}/"
                                f"{repository.name}"
                            ),
                            "branch": repository.default_branch,
                        },
                    )
                )

        await db.commit()

        return {
            "status": "completed",
            "project_id": str(project.id),
            "repository": (
                f"{repository.owner}/{repository.name}"
            ),
            "added": added,
            "updated": updated,
            "deleted": deleted,
            "unchanged": unchanged,
        }