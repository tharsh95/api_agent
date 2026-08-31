import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.agent_service import AgentService


router = APIRouter(
    prefix="/projects",
    tags=["agent"],
)

agent_service = AgentService()


class AgentRequest(BaseModel):
    request: str = Field(
        min_length=1,
        max_length=5000,
    )


@router.post("/{project_id}/agent")
async def run_project_agent(
    project_id: uuid.UUID,
    payload: AgentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="No authenticated user found",
        )

    try:
        authenticated_user_id = uuid.UUID(
            user_id
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid authenticated user",
        ) from exc

    try:
        return await agent_service.run(
            db=db,
            project_id=project_id,
            user_id=authenticated_user_id,
            user_request=payload.request,
        )

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

@router.post("/{project_id}/agent/{agent_run_id}/confirm")
async def confirm_agent_run(
    project_id: uuid.UUID,
    agent_run_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="No authenticated user found",
        )

    try:
        authenticated_user_id = uuid.UUID(
            user_id
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid authenticated user",
        ) from exc

    return await agent_service.confirm(
        db=db,
        project_id=project_id,
        user_id=authenticated_user_id,
        agent_run_id=agent_run_id,
    )