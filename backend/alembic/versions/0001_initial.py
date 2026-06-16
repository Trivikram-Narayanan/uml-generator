"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id",            sa.String(),  primary_key=True),
        sa.Column("email",         sa.String(255), nullable=False, unique=True),
        sa.Column("username",      sa.String(80),  nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active",     sa.Boolean(),   default=True),
        sa.Column("onboarded",     sa.Boolean(),   default=False),
        sa.Column("created_at",    sa.DateTime(),  nullable=True),
        sa.Column("updated_at",    sa.DateTime(),  nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "workspaces",
        sa.Column("id",         sa.String(), primary_key=True),
        sa.Column("name",       sa.String(120), nullable=False),
        sa.Column("owner_id",   sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "workspace_members",
        sa.Column("id",           sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id",      sa.String(), sa.ForeignKey("users.id",      ondelete="CASCADE"), nullable=False),
        sa.Column("role",         sa.String(20), default="member"),
        sa.Column("invited_at",   sa.DateTime(), nullable=True),
        sa.UniqueConstraint("workspace_id", "user_id"),
    )

    op.create_table(
        "tags",
        sa.Column("id",      sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name",    sa.String(60), nullable=False),
        sa.Column("color",   sa.String(20), default="#4f8ef7"),
        sa.UniqueConstraint("user_id", "name"),
    )
    op.create_index("ix_tags_user_id", "tags", ["user_id"])

    op.create_table(
        "diagrams",
        sa.Column("id",            sa.String(),  primary_key=True),
        sa.Column("user_id",       sa.String(),  sa.ForeignKey("users.id",       ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id",  sa.String(),  sa.ForeignKey("workspaces.id",  ondelete="SET NULL"), nullable=True),
        sa.Column("title",         sa.String(255), nullable=False, default="Untitled"),
        sa.Column("description",   sa.Text(),    nullable=False),
        sa.Column("diagram_type",  sa.String(50), nullable=False),
        sa.Column("plantuml_code", sa.Text(),    nullable=False),
        sa.Column("impl_code",     sa.Text(),    nullable=True),
        sa.Column("impl_language", sa.String(50), nullable=True),
        sa.Column("llm_backend",   sa.String(50), nullable=True),
        sa.Column("is_public",     sa.Boolean(), default=False),
        sa.Column("folder",        sa.String(120), nullable=True),
        sa.Column("thumb_score",   sa.Float(),   default=0.0),
        sa.Column("version",       sa.Integer(), default=1),
        sa.Column("created_at",    sa.DateTime(), nullable=True),
        sa.Column("updated_at",    sa.DateTime(), nullable=True),
    )
    op.create_index("ix_diagrams_user_id",      "diagrams", ["user_id"])
    op.create_index("ix_diagrams_workspace_id", "diagrams", ["workspace_id"])

    op.create_table(
        "diagram_tags",
        sa.Column("diagram_id", sa.String(), sa.ForeignKey("diagrams.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id",     sa.String(), sa.ForeignKey("tags.id",     ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "diagram_versions",
        sa.Column("id",            sa.String(), primary_key=True),
        sa.Column("diagram_id",    sa.String(), sa.ForeignKey("diagrams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version",       sa.Integer(), nullable=False),
        sa.Column("plantuml_code", sa.Text(),    nullable=False),
        sa.Column("impl_code",     sa.Text(),    nullable=True),
        sa.Column("impl_language", sa.String(50), nullable=True),
        sa.Column("change_note",   sa.String(255), nullable=True),
        sa.Column("created_at",    sa.DateTime(),  nullable=True),
    )
    op.create_index("ix_diagram_versions_diagram_id", "diagram_versions", ["diagram_id"])

    op.create_table(
        "diagram_feedback",
        sa.Column("id",         sa.String(), primary_key=True),
        sa.Column("diagram_id", sa.String(), sa.ForeignKey("diagrams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id",    sa.String(), sa.ForeignKey("users.id",    ondelete="CASCADE"), nullable=False),
        sa.Column("score",      sa.Integer(), nullable=False),
        sa.Column("correction", sa.Text(),    nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("diagram_id", "user_id"),
    )
    op.create_index("ix_diagram_feedback_diagram_id", "diagram_feedback", ["diagram_id"])

    op.create_table(
        "templates",
        sa.Column("id",            sa.String(), primary_key=True),
        sa.Column("title",         sa.String(255), nullable=False),
        sa.Column("description",   sa.Text(),      nullable=False),
        sa.Column("diagram_type",  sa.String(50),  nullable=False),
        sa.Column("plantuml_code", sa.Text(),      nullable=False),
        sa.Column("category",      sa.String(80),  nullable=True),
        sa.Column("is_builtin",    sa.Boolean(),   default=False),
        sa.Column("use_count",     sa.Integer(),   default=0),
        sa.Column("created_at",    sa.DateTime(),  nullable=True),
    )


def downgrade() -> None:
    for table in ["templates","diagram_feedback","diagram_versions",
                  "diagram_tags","diagrams","tags","workspace_members",
                  "workspaces","users"]:
        op.drop_table(table)
