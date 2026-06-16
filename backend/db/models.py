"""
db/models.py  –  All ORM models
Tables: users, workspaces, workspace_members, diagrams,
        diagram_versions, diagram_feedback, tags, diagram_tags,
        templates
"""
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Boolean, DateTime,
    ForeignKey, Integer, Float, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id            = Column(String, primary_key=True, default=_uuid)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    username      = Column(String(80),  unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active     = Column(Boolean, default=True)
    onboarded     = Column(Boolean, default=False)   # first-run done
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    diagrams        = relationship("Diagram", back_populates="owner",
                                   cascade="all, delete-orphan", lazy="dynamic",
                                   foreign_keys="Diagram.user_id")
    workspace_memberships = relationship("WorkspaceMember", back_populates="user",
                                          cascade="all, delete-orphan")


# ── Workspaces ────────────────────────────────────────────────────────────────

class Workspace(Base):
    __tablename__ = "workspaces"
    id         = Column(String, primary_key=True, default=_uuid)
    name       = Column(String(120), nullable=False)
    owner_id   = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    members  = relationship("WorkspaceMember", back_populates="workspace",
                             cascade="all, delete-orphan")
    diagrams = relationship("Diagram", back_populates="workspace",
                             cascade="all, delete-orphan", lazy="dynamic")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)
    id           = Column(String, primary_key=True, default=_uuid)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id      = Column(String, ForeignKey("users.id",  ondelete="CASCADE"), nullable=False)
    role         = Column(String(20), default="member")   # owner | member | viewer
    invited_at   = Column(DateTime, default=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="members")
    user      = relationship("User",      back_populates="workspace_memberships")


# ── Tags ──────────────────────────────────────────────────────────────────────

class Tag(Base):
    __tablename__ = "tags"
    id      = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name    = Column(String(60), nullable=False)
    color   = Column(String(20), default="#4f8ef7")
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    diagram_tags = relationship("DiagramTag", back_populates="tag",
                                 cascade="all, delete-orphan")


class DiagramTag(Base):
    __tablename__ = "diagram_tags"
    diagram_id = Column(String, ForeignKey("diagrams.id", ondelete="CASCADE"),
                         primary_key=True)
    tag_id     = Column(String, ForeignKey("tags.id",     ondelete="CASCADE"),
                         primary_key=True)

    diagram = relationship("Diagram", back_populates="tags")
    tag     = relationship("Tag",     back_populates="diagram_tags")


# ── Diagrams ──────────────────────────────────────────────────────────────────

class Diagram(Base):
    __tablename__ = "diagrams"
    id             = Column(String, primary_key=True, default=_uuid)
    user_id        = Column(String, ForeignKey("users.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    workspace_id   = Column(String, ForeignKey("workspaces.id", ondelete="SET NULL"),
                             nullable=True, index=True)
    title          = Column(String(255), nullable=False, default="Untitled Diagram")
    description    = Column(Text, nullable=False)
    diagram_type   = Column(String(50), nullable=False)
    plantuml_code  = Column(Text, nullable=False)
    impl_code      = Column(Text, nullable=True)
    impl_language  = Column(String(50), nullable=True)
    llm_backend    = Column(String(50), nullable=True)   # which backend generated it
    is_public      = Column(Boolean, default=False)
    folder         = Column(String(120), nullable=True)  # simple folder path
    thumb_score    = Column(Float, default=0.0)           # avg feedback score
    version        = Column(Integer, default=1)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner     = relationship("User",      back_populates="diagrams",
                              foreign_keys=[user_id])
    workspace = relationship("Workspace", back_populates="diagrams")
    versions  = relationship("DiagramVersion",  back_populates="diagram",
                              cascade="all, delete-orphan",
                              order_by="desc(DiagramVersion.created_at)")
    feedback  = relationship("DiagramFeedback", back_populates="diagram",
                              cascade="all, delete-orphan")
    tags      = relationship("DiagramTag", back_populates="diagram",
                              cascade="all, delete-orphan")


# ── Versions ──────────────────────────────────────────────────────────────────

class DiagramVersion(Base):
    __tablename__ = "diagram_versions"
    id            = Column(String, primary_key=True, default=_uuid)
    diagram_id    = Column(String, ForeignKey("diagrams.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    version       = Column(Integer, nullable=False)
    plantuml_code = Column(Text, nullable=False)
    impl_code     = Column(Text, nullable=True)
    impl_language = Column(String(50), nullable=True)
    change_note   = Column(String(255), nullable=True)   # "Fixed login flow", "Added cache"
    created_at    = Column(DateTime, default=datetime.utcnow)

    diagram = relationship("Diagram", back_populates="versions")


# ── Feedback ──────────────────────────────────────────────────────────────────

class DiagramFeedback(Base):
    __tablename__ = "diagram_feedback"
    id          = Column(String, primary_key=True, default=_uuid)
    diagram_id  = Column(String, ForeignKey("diagrams.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    user_id     = Column(String, ForeignKey("users.id",    ondelete="CASCADE"),
                          nullable=False)
    score       = Column(Integer, nullable=False)   # 1 = thumbs up, -1 = thumbs down
    correction  = Column(Text, nullable=True)        # user's correction text
    created_at  = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("diagram_id", "user_id"),)

    diagram = relationship("Diagram", back_populates="feedback")


# ── Templates ─────────────────────────────────────────────────────────────────

class Template(Base):
    __tablename__ = "templates"
    id            = Column(String, primary_key=True, default=_uuid)
    title         = Column(String(255), nullable=False)
    description   = Column(Text, nullable=False)
    diagram_type  = Column(String(50), nullable=False)
    plantuml_code = Column(Text, nullable=False)
    category      = Column(String(80), nullable=True)   # Auth, E-commerce, etc.
    is_builtin    = Column(Boolean, default=False)
    use_count     = Column(Integer, default=0)
    created_at    = Column(DateTime, default=datetime.utcnow)
