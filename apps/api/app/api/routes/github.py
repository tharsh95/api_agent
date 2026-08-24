from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.github_installation import GitHubInstallation
from app.models.project import Project
from app.models.repository import Repository
from app.models.user import User
from app.services.github_service import GitHubService


router = APIRouter(
    prefix="/github",
    tags=["github"],
)

github_service = GitHubService()


class RepositorySelectRequest(BaseModel):
    github_repo_id: int


@router.get("/repositories")
async def get_repositories(
    db: AsyncSession = Depends(get_db),
):
    # Temporary development user.
    # Replace with real application authentication later.
    result = await db.execute(
        select(User).where(
            User.github_id == "66423396"
        )
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="GitHub user is not connected",
        )

    result = await db.execute(
        select(GitHubInstallation).where(
            GitHubInstallation.user_id == user.id
        )
    )

    installation = result.scalar_one_or_none()

    if not installation:
        raise HTTPException(
            status_code=404,
            detail="GitHub installation not found",
        )

    token_data = (
        await github_service.create_installation_access_token(
            installation.installation_id
        )
    )

    installation_token = token_data.get("token")

    if not installation_token:
        raise HTTPException(
            status_code=502,
            detail="GitHub installation token was not returned",
        )

    github_response = (
        await github_service.get_installation_repositories(
            installation_token
        )
    )

    repositories = []

    for repo in github_response.get(
        "repositories",
        [],
    ):
        repositories.append(
            {
                "id": repo["id"],
                "name": repo["name"],
                "full_name": repo["full_name"],
                "owner": repo["owner"]["login"],
                "default_branch": repo.get(
                    "default_branch"
                ),
                "private": repo["private"],
                "html_url": repo["html_url"],
            }
        )

    return {
        "repositories": repositories,
        "total": len(repositories),
    }


@router.post("/repositories/select")
async def select_repository(
    payload: RepositorySelectRequest,
    db: AsyncSession = Depends(get_db),
):
    # Temporary development user.
    result = await db.execute(
        select(User).where(
            User.github_id == "66423396"
        )
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="GitHub user is not connected",
        )

    # Find GitHub installation
    result = await db.execute(
        select(GitHubInstallation).where(
            GitHubInstallation.user_id == user.id
        )
    )

    installation = result.scalar_one_or_none()

    if not installation:
        raise HTTPException(
            status_code=404,
            detail="GitHub installation not found",
        )

    # Generate installation token
    token_data = (
        await github_service.create_installation_access_token(
            installation.installation_id
        )
    )

    installation_token = token_data.get("token")

    if not installation_token:
        raise HTTPException(
            status_code=502,
            detail="GitHub installation token was not returned",
        )

    # Get repositories directly from GitHub
    github_response = (
        await github_service.get_installation_repositories(
            installation_token
        )
    )

    github_repository = next(
        (
            repo
            for repo in github_response.get(
                "repositories",
                []
            )
            if repo["id"] == payload.github_repo_id
        ),
        None,
    )

    if not github_repository:
        raise HTTPException(
            status_code=404,
            detail=(
                "Repository was not found or is not "
                "accessible by the GitHub App"
            ),
        )

    # Check if this repository is already connected
    result = await db.execute(
        select(Repository).where(
            Repository.github_repo_id
            == str(github_repository["id"])
        )
    )

    existing_repository = (
        result.scalar_one_or_none()
    )

    if existing_repository:
        raise HTTPException(
            status_code=409,
            detail="Repository is already connected",
        )

    # Create Project
    project = Project(
        user_id=user.id,
        name=github_repository["name"],
        description=(
            f"GitHub repository "
            f"{github_repository['full_name']}"
        ),
    )

    db.add(project)

    await db.flush()

    # Create Repository
    repository = Repository(
        project_id=project.id,
        github_repo_id=str(
            github_repository["id"]
        ),
        owner=github_repository["owner"]["login"],
        name=github_repository["name"],
        default_branch=(
            github_repository.get("default_branch")
            or "main"
        ),
        url=github_repository["html_url"],
    )

    db.add(repository)

    await db.commit()

    return {
        "status": "connected",
        "project": {
            "id": str(project.id),
            "name": project.name,
            "description": project.description,
        },
        "repository": {
            "id": str(repository.id),
            "github_repo_id": (
                repository.github_repo_id
            ),
            "owner": repository.owner,
            "name": repository.name,
            "default_branch": (
                repository.default_branch
            ),
            "url": repository.url,
        },
    }