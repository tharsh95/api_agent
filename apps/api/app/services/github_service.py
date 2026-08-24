import time
from pathlib import Path

import httpx
import jwt

from app.core.config import settings


GITHUB_API_URL = "https://api.github.com"
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"


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
            "iss": settings.github_app_id,
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
                data.get("error_description", data["error"])
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
                    "Authorization": f"Bearer {access_token}",
                    "X-GitHub-Api-Version": "2026-03-10",
                },
            )

        response.raise_for_status()

        return response.json()