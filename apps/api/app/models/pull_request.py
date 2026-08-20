import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    github_pr_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    branch_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    pr_url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="OPEN",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    agent_run = relationship(
        "AgentRun",
        back_populates="pull_request",
    )