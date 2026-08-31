from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select

from agent.app.graph.builder import build_graph

from app.models.agent_run import AgentRun
from app.models.project import Project
from app.services.repository_context_service import (
    RepositoryContextService,
)

class AgentService:

    def __init__(
        self,
        repository_context_service=None,
        graph_instance=None,
    ):
        self.repository_context_service = (
            repository_context_service
            or RepositoryContextService()
        )

        self.graph = (
            graph_instance
            or build_graph()
        )

    async def run(
        self,
        db,
        project_id,
        user_id,
        user_request,
    ) -> dict:

        repository = (
        await self.repository_context_service
        .get_repository_context(
            db=db,
            project_id=project_id,
            user_id=user_id,
        )
    )

        agent_run = AgentRun(
            project_id=project_id,
            user_request=user_request,
            status="RUNNING",
            started_at=datetime.now(timezone.utc),
        )

        db.add(agent_run)
        await db.flush()

        initial_state = {
            "project_id": str(project_id),
            "user_request": user_request,
            "repository": repository,
            "repository_profile": {},
            "integration_candidates": [],
            "integration_plan": None,
            "confirmation_required": True,
            "confirmed": False,
            "status": "started",
            "error": None,
        }

        try:
            result = await self.graph.ainvoke(
                initial_state
            )

            if result["status"] == "awaiting_confirmation":
                agent_run.status = "AWAITING_CONFIRMATION"
                agent_run.completed_at = None
            else:
                agent_run.status = "COMPLETED"
                agent_run.completed_at = datetime.now(
                    timezone.utc
                )

            await db.commit()

        except Exception:
            agent_run.status = "FAILED"
            agent_run.completed_at = datetime.now(
                timezone.utc
            )

            await db.commit()
            raise

        return {
        "project_id": str(project_id),
        "agent_run_id": str(agent_run.id),
        "status": result["status"],
        "repository_profile": result.get(
            "repository_profile",
            {},
        ),
        "integration_candidates": result.get(
            "integration_candidates",
            [],
        ),
        "integration_plan": result.get(
            "integration_plan"
        ),
        "requires_confirmation": (
            result.get("integration_plan", {})
            .get(
                "requires_confirmation",
                False,
            )
        ),
        "confirmation_required": result.get(
            "confirmation_required",
            True,
        ),
        "confirmed": result.get(
            "confirmed",
            False,
        ),
    }

    async def confirm(
        self,
        db,
        project_id,
        user_id,
        agent_run_id,
    ) -> dict:
        result = await db.execute(
            select(AgentRun).join(
                Project,
                AgentRun.project_id == Project.id,
            ).where(
                AgentRun.id == agent_run_id,
                AgentRun.project_id == project_id,
                Project.user_id == user_id,
            )
        )
        agent_run = result.scalar_one_or_none()

        if not agent_run:
            raise HTTPException(
                status_code=404,
                detail="Agent run not found",
            )

        if agent_run.status != "AWAITING_CONFIRMATION":
            raise HTTPException(
                status_code=400,
                detail="Agent run is not awaiting confirmation",
            )

        agent_run.status = "CONFIRMED"
        await db.commit()

        return {
            "agent_run_id": str(agent_run.id),
            "status": agent_run.status,
            "confirmed": True,
        }