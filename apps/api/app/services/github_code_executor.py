from app.services.github_service import GitHubService


class GitHubCodeExecutor:
    """
    Applies generated code changes to a new GitHub branch.

    Each file update through GitHub's Contents API creates a commit
    on the target branch.
    """

    def __init__(
        self,
        github_service=None,
    ):
        self.github_service = (
            github_service
            or GitHubService()
        )

    async def execute(
        self,
        installation_token: str,
        owner: str,
        repo: str,
        source_branch: str,
        branch_name: str,
        code_changes: list[dict],
    ) -> dict:
        if not code_changes:
            raise ValueError(
                "Cannot execute code changes: no changes provided."
            )

        await self.github_service.create_branch(
            installation_token=installation_token,
            owner=owner,
            repo=repo,
            branch_name=branch_name,
            source_branch=source_branch,
        )

        commits = []

        for change in code_changes:
            file_path = change.get("file_path")
            new_content = change.get("new_content")
            action = change.get("action", "modify")

            if not file_path:
                raise ValueError(
                    "Code change is missing file_path."
                )

            if new_content is None:
                raise ValueError(
                    f"Code change for {file_path} "
                    "is missing new_content."
                )

            if action not in ("create", "modify"):
                raise ValueError(
                    f"Unsupported action '{action}' for {file_path}."
                )

            file_sha = None

            if action == "modify":
                file_data = await self.github_service.get_file(
                    installation_token=installation_token,
                    owner=owner,
                    repo=repo,
                    path=file_path,
                    branch=branch_name,
                )

                file_sha = file_data.get("sha")

                if not file_sha:
                    raise ValueError(
                        f"GitHub did not return a SHA for {file_path}."
                    )

            result = await self.github_service.create_or_update_file(
                installation_token=installation_token,
                owner=owner,
                repo=repo,
                path=file_path,
                content=new_content,
                branch=branch_name,
                message=self._build_commit_message(change),
                sha=file_sha,
            )

            commits.append({
                "file_path": file_path,
                "commit_sha": result.get("commit", {}).get("sha"),
            })

        return {
            "branch_name": branch_name,
            "changes_applied": len(commits),
            "commits": commits,
        }

    @staticmethod
    def _build_commit_message(change: dict) -> str:
        file_path = change.get("file_path", "repository file")

        if change.get("action") == "create":
            return f"test: add {file_path}"

        return f"feat: update {file_path}"
