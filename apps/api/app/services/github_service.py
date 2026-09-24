import time
from pathlib import Path

import httpx
import jwt

from app.core.config import settings


GITHUB_API_URL = "https://api.github.com"
GITHUB_TOKEN_URL = (
    "https://github.com/login/oauth/access_token"
)
GITHUB_API_VERSION = "2026-03-10"


class GitHubService:

    def _load_private_key(self) -> str:
        return Path(
            settings.github_private_key_path
        ).read_text()

    def create_app_jwt(self) -> str:
        now = int(time.time())

        payload = {
            "iat": now - 60,
            "exp": now + (9 * 60),
            "iss": str(settings.github_app_id),
        }

        return jwt.encode(
            payload,
            self._load_private_key(),
            algorithm="RS256",
        )

    def get_installation_url(self) -> str:
        return (
            "https://github.com/apps/"
            "ai-integration-engineer/installations/new"
        )

    async def exchange_code(
        self,
        code: str,
    ) -> dict:

        async with httpx.AsyncClient() as client:
            response = await client.post(
                GITHUB_TOKEN_URL,
                params={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": settings.github_redirect_uri,
                },
                headers={
                    "Accept": "application/json",
                },
            )

        response.raise_for_status()

        data = response.json()

        if "error" in data:
            raise ValueError(
                data.get(
                    "error_description",
                    data["error"],
                )
            )

        return data

    async def get_user(
        self,
        access_token: str,
    ) -> dict:

        return await self._get(
            "/user",
            access_token,
        )

    async def get_user_installations(
        self,
        access_token: str,
    ) -> dict:

        return await self._get(
            "/user/installations",
            access_token,
        )

    async def create_installation_access_token(
        self,
        installation_id: int,
    ) -> dict:
        """
        Generate a short-lived access token for
        a GitHub App installation.
        """

        app_jwt = self.create_app_jwt()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_URL}/app/installations/"
                f"{installation_id}/access_tokens",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {app_jwt}",
                    "X-GitHub-Api-Version": GITHUB_API_VERSION,
                },
            )

        response.raise_for_status()

        return response.json()

    async def get_installation_repositories(
        self,
        installation_token: str,
    ) -> dict:
        """
        Get repositories accessible to the GitHub App
        installation.
        """

        return await self._get_installation(
            "/installation/repositories",
            installation_token,
        )

    async def get_repository_contents(
        self,
        installation_token: str,
        owner: str,
        repo: str,
        path: str = "",
        ref: str | None = None,
    ) -> list | dict:
        """
        Get repository contents from GitHub.

        Returns either:
        - a list when path points to a directory
        - a dict when path points to a file
        """

        params = {}

        if ref:
            params["ref"] = ref

        return await self._get_installation(
            f"/repos/{owner}/{repo}/contents/{path}",
            installation_token,
            params=params,
        )

    async def get_branch(
        self,
        installation_token: str,
        owner: str,
        repo: str,
        branch: str,
    ) -> dict:
        """
        Get a Git reference for a branch.
        """

        return await self._get_installation(
            f"/repos/{owner}/{repo}/git/ref/heads/{branch}",
            installation_token,
        )

    async def create_branch(
        self,
        installation_token: str,
        owner: str,
        repo: str,
        branch_name: str,
        source_branch: str,
    ) -> dict:
        """
        Create a new branch from an existing source branch.
        """

        source_ref = await self.get_branch(
            installation_token=installation_token,
            owner=owner,
            repo=repo,
            branch=source_branch,
        )

        source_sha = source_ref["object"]["sha"]

        return await self._post_installation(
            f"/repos/{owner}/{repo}/git/refs",
            installation_token,
            json={
                "ref": f"refs/heads/{branch_name}",
                "sha": source_sha,
            },
        )

    async def create_or_update_file(
        self,
        installation_token: str,
        owner: str,
        repo: str,
        path: str,
        content: str,
        branch: str,
        message: str,
        sha: str | None = None,
    ) -> dict:
        """
        Create or update a file on a repository branch.

        If sha is provided, GitHub treats this as an update.
        If sha is omitted, GitHub creates a new file.
        """

        import base64

        payload = {
            "message": message,
            "content": base64.b64encode(
                content.encode("utf-8")
            ).decode("ascii"),
            "branch": branch,
        }

        if sha:
            payload["sha"] = sha

        return await self._put_installation(
            f"/repos/{owner}/{repo}/contents/{path}",
            installation_token,
            json=payload,
        )

    async def get_file(
        self,
        installation_token: str,
        owner: str,
        repo: str,
        path: str,
        branch: str,
    ) -> dict:
        """
        Get a file from a specific repository branch.

        GitHub returns the file SHA which is required when
        updating an existing file.
        """

        return await self._get_installation(
            f"/repos/{owner}/{repo}/contents/{path}",
            installation_token,
            params={"ref": branch},
        )

    async def create_pull_request(
        self,
        installation_token: str,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> dict:
        """
        Create a pull request.
        """

        return await self._post_installation(
            f"/repos/{owner}/{repo}/pulls",
            installation_token,
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
            },
        )

    async def _post_installation(
        self,
        path: str,
        installation_token: str,
        json: dict,
    ) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_URL}{path}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": (
                        f"Bearer {installation_token}"
                    ),
                    "X-GitHub-Api-Version": GITHUB_API_VERSION,
                },
                json=json,
            )

        response.raise_for_status()

        return response.json()

    async def _put_installation(
        self,
        path: str,
        installation_token: str,
        json: dict,
    ) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{GITHUB_API_URL}{path}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": (
                        f"Bearer {installation_token}"
                    ),
                    "X-GitHub-Api-Version": GITHUB_API_VERSION,
                },
                json=json,
            )

        response.raise_for_status()

        return response.json()

    async def _get(
        self,
        path: str,
        access_token: str,
    ) -> dict:

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_URL}{path}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": (
                        f"Bearer {access_token}"
                    ),
                    "X-GitHub-Api-Version": GITHUB_API_VERSION,
                },
            )

        response.raise_for_status()

        return response.json()

    async def _get_installation(
        self,
        path: str,
        installation_token: str,
        params: dict | None = None,
    ) -> dict | list:

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_URL}{path}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": (
                        f"Bearer {installation_token}"
                    ),
                    "X-GitHub-Api-Version": GITHUB_API_VERSION,
                },
                params=params,
            )

        response.raise_for_status()

        return response.json()