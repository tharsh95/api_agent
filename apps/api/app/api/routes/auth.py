import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.services.github_service import GitHubService

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

github_service = GitHubService()

from urllib.parse import urlencode

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.services.github_service import GitHubService


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

github_service = GitHubService()


@router.get("/github")
async def github_authorize():
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_redirect_uri,
    }

    authorization_url = (
        "https://github.com/login/oauth/authorize?"
        + urlencode(params)
    )

    return RedirectResponse(
        authorization_url
    )
    
@router.get("/github/callback")
async def github_callback(
    code: str | None = None,
):
    if not code:
        raise HTTPException(
            status_code=400,
            detail="Missing GitHub authorization code",
        )

    token_data = await github_service.exchange_code(
        code
    )

    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="GitHub access token was not returned",
        )

    github_user = await github_service.get_user(
        access_token
    )

    installations = (
        await github_service.get_user_installations(
            access_token
        )
    )

    return {
        "github_user": github_user,
        "installations": installations,
    }
    