import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.github_installation import GitHubInstallation
from app.models.user import User
from app.services.github_service import GitHubService


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

github_service = GitHubService()


@router.get("/github")
async def github_authorize(request: Request):
    state = secrets.token_urlsafe(32)

    request.session["github_oauth_state"] = state

    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_redirect_uri,
        "state": state,
    }

    authorization_url = (
        "https://github.com/login/oauth/authorize?"
        + urlencode(params)
    )

    return RedirectResponse(authorization_url)


@router.get("/github/callback")
async def github_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    # ---------------------------------------------------------
    # 1. Validate OAuth callback parameters
    # ---------------------------------------------------------

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Missing GitHub authorization code",
        )

    if not state:
        raise HTTPException(
            status_code=400,
            detail="Missing OAuth state",
        )

    expected_state = request.session.pop(
        "github_oauth_state",
        None,
    )

    if not expected_state or not secrets.compare_digest(
        expected_state,
        state,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state",
        )

    # ---------------------------------------------------------
    # 2. Exchange authorization code for GitHub access token
    # ---------------------------------------------------------

    token_data = await github_service.exchange_code(
        code
    )

    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="GitHub access token was not returned",
        )

    # ---------------------------------------------------------
    # 3. Get authenticated GitHub user
    # ---------------------------------------------------------

    github_user = await github_service.get_user(
        access_token
    )

    github_user_id = github_user.get("id")

    if not github_user_id:
        raise HTTPException(
            status_code=400,
            detail="GitHub user ID was not returned",
        )

    # ---------------------------------------------------------
    # 4. Get GitHub App installations
    # ---------------------------------------------------------

    installations = (
        await github_service.get_user_installations(
            access_token
        )
    )

    installation_list = installations.get(
        "installations",
        [],
    )

    if not installation_list:
        raise HTTPException(
            status_code=403,
            detail=(
                "No GitHub App installation found "
                "for this user"
            ),
        )

    # ---------------------------------------------------------
    # 5. Find installation belonging to this GitHub account
    # ---------------------------------------------------------

    installation = next(
        (
            item
            for item in installation_list
            if item.get("account", {}).get("id")
            == github_user_id
        ),
        None,
    )

    if not installation:
        raise HTTPException(
            status_code=403,
            detail=(
                "No GitHub App installation belongs "
                "to this user"
            ),
        )

    installation_id = installation.get("id")

    if not installation_id:
        raise HTTPException(
            status_code=400,
            detail="GitHub installation ID was not returned",
        )

    # ---------------------------------------------------------
    # 6. Validate installation account
    # ---------------------------------------------------------

    account = installation.get("account") or {}

    if account.get("id") != github_user_id:
        raise HTTPException(
            status_code=403,
            detail="GitHub installation account mismatch",
        )

    account_login = account.get("login")

    if not account_login:
        raise HTTPException(
            status_code=400,
            detail="GitHub installation account login missing",
        )

    account_type = account.get(
        "type",
        "User",
    )

    # ---------------------------------------------------------
    # 7. Find or create local User
    # ---------------------------------------------------------

    github_id = str(github_user_id)

    result = await db.execute(
        select(User).where(
            User.github_id == github_id
        )
    )

    user = result.scalar_one_or_none()

    if user:
        user.github_username = github_user.get(
            "login"
        )

        user.email = github_user.get(
            "email"
        )

    else:
        user = User(
            github_id=github_id,
            github_username=github_user.get(
                "login"
            ),
            email=github_user.get(
                "email"
            ),
        )

        db.add(user)

        # Get generated UUID before creating
        # GitHubInstallation
        await db.flush()

    # ---------------------------------------------------------
    # 8. Find or create GitHub installation
    # ---------------------------------------------------------

    result = await db.execute(
        select(GitHubInstallation).where(
            GitHubInstallation.installation_id
            == installation_id
        )
    )

    github_installation = (
        result.scalar_one_or_none()
    )

    if github_installation:

        github_installation.user_id = user.id

        github_installation.account_login = (
            account_login
        )

        github_installation.account_type = (
            account_type
        )

    else:

        github_installation = GitHubInstallation(
            user_id=user.id,
            installation_id=installation_id,
            account_login=account_login,
            account_type=account_type,
        )

        db.add(github_installation)

    # ---------------------------------------------------------
    # 9. Persist changes
    # ---------------------------------------------------------

    await db.commit()
    request.session["user_id"] = str(user.id)
    # ---------------------------------------------------------
    # 10. Return safe response
    # ---------------------------------------------------------

    return {
        "status": "connected",
        "user": {
            "id": str(user.id),
            "github_id": user.github_id,
            "github_username": user.github_username,
        },
        "github_installation": {
            "id": str(github_installation.id),
            "installation_id": (
                github_installation.installation_id
            ),
            "account_login": (
                github_installation.account_login
            ),
            "account_type": (
                github_installation.account_type
            ),
        },
    }