"""Create sessions and traceable browser steps."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("persona_name", sa.String(80), nullable=False),
        sa.Column("task_id", sa.String(20), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','technical_error','cancelled')",
            name="ck_sessions_status",
        ),
        sa.CheckConstraint("task_id = 'T02'", name="ck_sessions_task"),
    )
    op.create_index("ix_sessions_status", "sessions", ["status"])
    op.create_table(
        "steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("screenshot_before", sa.Text(), nullable=True),
        sa.Column("screenshot_after", sa.Text(), nullable=True),
        sa.UniqueConstraint("session_id", "step_no", name="uq_steps_session_number"),
        sa.CheckConstraint("step_no > 0", name="ck_steps_number"),
        sa.CheckConstraint("status IN ('succeeded','technical_error')", name="ck_steps_status"),
    )
    op.create_index("ix_steps_session_id", "steps", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_steps_session_id", table_name="steps")
    op.drop_table("steps")
    op.drop_index("ix_sessions_status", table_name="sessions")
    op.drop_table("sessions")
