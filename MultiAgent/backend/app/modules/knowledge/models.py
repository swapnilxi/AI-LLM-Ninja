"""Database models for the knowledge module."""
from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import TimestampMixin, _id
from app.core.db import Base


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_owner", "org_id", "owner_type", "owner_id"),)
    id: Mapped[str] = _id("doc")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    owner_type: Mapped[str] = mapped_column(String(20))  # org | project | agent
    owner_id: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(20), default="text")  # text | upload | url
    source_ref: Mapped[str] = mapped_column(String(1000), default="")
    mime: Mapped[str] = mapped_column(String(100), default="text/plain")
    size: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)  # always injected into the prompt
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (Index("ix_chunks_owner", "org_id", "owner_type", "owner_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[str] = mapped_column(String(32))
    owner_type: Mapped[str] = mapped_column(String(20))
    owner_id: Mapped[str] = mapped_column(String(32))
    idx: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)


class Memory(TimestampMixin, Base):
    __tablename__ = "memories"
    __table_args__ = (Index("ix_memories_scope", "org_id", "scope", "agent_id", "project_id"),)
    id: Mapped[str] = _id("mmr")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(20))  # agent | project
    agent_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    key: Mapped[str] = mapped_column(String(120), default="")
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(20), default="agent")  # agent | user
    run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
