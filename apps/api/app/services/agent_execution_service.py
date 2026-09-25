from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pull_request import PullRequest
from app.services.github_code_executor import GitHubCodeExecutor
from app.services.github_service import GitHubService
from app.services.repository_context_service import (
    RepositoryContextService,
)


class AgentExecutionService:
    """
    Executes generated code changes against GitHub and creates
    a pull request for the completed execution.
    """

    def __init__(
        self,
        repository_context_service=None,
        github_service=None,
        github_code_executor=None,
    ):
        self.repository_context_service = (
            repository_context_service
            or RepositoryContextService()
        )

        self.github_service = (
            github_service
            or GitHubService()
        )

        self.github_code_executor = (
            github_code_executor
            or GitHubCodeExecutor(
                github_service=self.github_service,
            )
        )

    async def execute(
        self,
        db: AsyncSession,
        project_id: UUID,
        user_id: UUID,
        agent_run_id: UUID,
        user_request: str,
        code_changes: list[dict],
    ) -> dict:
        if not code_changes:
            raise ValueError(
                "Cannot execute agent run: no code changes generated."
            )

        repository = (
            await self.repository_context_service
            .get_repository_context(
                db=db,
                project_id=project_id,
                user_id=user_id,
            )
        )

        owner = repository["owner"]
        repo = repository["name"]
        default_branch = repository["default_branch"]

        installation_token = (
            await self._get_installation_token(
                db=db,
                project_id=project_id,
                user_id=user_id,
            )
        )

        branch_name = self._build_branch_name(
            agent_run_id=agent_run_id,
        )

        execution_result = (
            await self.github_code_executor.execute(
                installation_token=installation_token,
                owner=owner,
                repo=repo,
                source_branch=default_branch,
                branch_name=branch_name,
                code_changes=code_changes,
            )
        )

        pr_title = self._build_pr_title(
            user_request=user_request,
        )

        pr_body = self._build_pr_body(
            user_request=user_request,
            code_changes=code_changes,
        )

        github_pr = (
            await self.github_service.create_pull_request(
                installation_token=installation_token,
                owner=owner,
                repo=repo,
                title=pr_title,
                body=pr_body,
                head=branch_name,
                base=default_branch,
            )
        )

        pull_request = PullRequest(
            agent_run_id=agent_run_id,
            github_pr_id=str(
                github_pr["number"]
            ),
            branch_name=branch_name,
            pr_url=github_pr["html_url"],
            status="OPEN",
        )

        db.add(pull_request)
        await db.flush()

        return {
            "pull_request": {
                "id": str(pull_request.id),
                "github_pr_id": pull_request.github_pr_id,
                "branch_name": pull_request.branch_name,
                "pr_url": pull_request.pr_url,
                "status": pull_request.status,
            },
            "execution": execution_result,
        }

    async def _get_installation_token(
        self,
        db: AsyncSession,
        project_id: UUID,
        user_id: UUID,
    ) -> str:
        repository = (
            await self.repository_context_service
            .get_repository_context(
                db=db,
                project_id=project_id,
                user_id=user_id,
            )
        )

        installation_id = repository.get(
            "installation_id"
        )

        if installation_id is None:
            raise ValueError(
                "Repository context is missing GitHub installation ID."
            )

        token_data = (
            await self.github_service
            .create_installation_access_token(
                installation_id=int(
                    installation_id
                )
            )
        )

        token = token_data.get("token")

        if not token:
            raise ValueError(
                "GitHub did not return an installation token."
            )

        return token

    @staticmethod
    def _build_branch_name(
        agent_run_id: UUID,
    ) -> str:
        return f"agent/{agent_run_id}"

    @staticmethod
    def _build_pr_title(
        user_request: str,
    ) -> str:
        request = " ".join(
            user_request.strip().split()
        )

        if not request:
            return "feat: agent integration"

        return f"feat: {request[:100]}"

    @staticmethod
    def _build_pr_body(
        user_request: str,
        code_changes: list[dict],
    ) -> str:
        files = "\n".join(
            f"- `{change.get('file_path', 'unknown')}`"
            for change in code_changes
        )

        return (
            "## AI Integration Engineer\n\n"
            f"### Request\n{user_request}\n\n"
            "### Changed files\n"
            f"{files}\n\n"
            "This pull request was generated from an "
            "approved integration plan."
        )
