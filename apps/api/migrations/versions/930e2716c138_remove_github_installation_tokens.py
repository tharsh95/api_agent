from alembic import op


revision = "930e2716c138"
down_revision = "8299b259a2ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column(
        "github_installations",
        "access_token_encrypted",
    )
    op.drop_column(
        "github_installations",
        "refresh_token_encrypted",
    )
    op.drop_column(
        "github_installations",
        "access_token_expires_at",
    )
    op.drop_column(
        "github_installations",
        "refresh_token_expires_at",
    )


def downgrade() -> None:
    # Recreate the original columns if this migration is rolled back.
    from sqlalchemy import Column, DateTime, Text

    op.add_column(
        "github_installations",
        Column(
            "access_token_encrypted",
            Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "github_installations",
        Column(
            "refresh_token_encrypted",
            Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "github_installations",
        Column(
            "access_token_expires_at",
            DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "github_installations",
        Column(
            "refresh_token_expires_at",
            DateTime(timezone=True),
            nullable=True,
        ),
    )