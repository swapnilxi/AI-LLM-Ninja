"""Database models.

Tenancy model
-------------
Organization (tenant) ─┬─ Membership ── User
                       ├─ Project ── (Conversations, Runs, Automations, project Documents/Memory)
                       ├─ ProviderCredential / Secret / ApiKey / Connection (app connectors)
                       └─ Library resources (Agent, Skill, Tool, Team, Workflow)

Library resources are *project independent*: ``org_id`` is the owning tenant, or
NULL for the global (platform-wide) library that every org can use. A run always
executes inside (org, project) and receives that context at runtime.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from .db import Base


class UTCDateTime(TypeDecorator):
    """Stores UTC; always returns timezone-aware datetimes (SQLite drops tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
            if dialect.name == "sqlite":
                value = value.replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def _id(prefix: str):
    return mapped_column(String(32), primary_key=True, default=lambda: new_id(prefix))


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


# --------------------------------------------------------------------------- identity / tenancy
class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = _id("usr")
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[str] = _id("org")
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    context: Mapped[str] = mapped_column(Text, default="")  # org-wide instructions/policies for every agent
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id"),)
    id: Mapped[str] = _id("mem")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="member")  # owner|admin|member|viewer


class ApiKey(TimestampMixin, Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = _id("key")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(20), default="member")
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ProviderCredential(TimestampMixin, Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (UniqueConstraint("org_id", "provider"),)
    id: Mapped[str] = _id("prv")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    api_key_enc: Mapped[str] = mapped_column(Text, default="")
    base_url: Mapped[str] = mapped_column(String(500), default="")
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Secret(TimestampMixin, Base):
    __tablename__ = "secrets"
    __table_args__ = (UniqueConstraint("org_id", "name"),)
    id: Mapped[str] = _id("sec")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    value_enc: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(String(300), default="")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    id: Mapped[str] = _id("prj")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[str] = mapped_column(Text, default="")  # project brief injected into every agent
    variables: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # settings: web_access, browser_render_js, allowed_domains, blocked_domains, memory_enabled,
    #           shared_tool_ids, connection_ids, default_agent_id
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


# --------------------------------------------------------------------------- library (project independent)
class Agent(TimestampMixin, Base):
    __tablename__ = "agents"
    id: Mapped[str] = _id("agt")
    org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    avatar: Mapped[str] = mapped_column(String(40), default="bot")  # icon key (flat icon set)
    color: Mapped[str] = mapped_column(String(20), default="indigo")
    provider: Mapped[str] = mapped_column(String(40), default="default")
    model: Mapped[str] = mapped_column(String(120), default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[int] = mapped_column(Integer, default=8000)
    max_steps: Mapped[int] = mapped_column(Integer, default=8)
    effort: Mapped[str] = mapped_column(String(10), default="medium")
    tool_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    skill_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    connection_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    # settings: browser_enabled, memory_enabled, knowledge_enabled, show_thinking, render_js
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Skill(TimestampMixin, Base):
    __tablename__ = "skills"
    id: Mapped[str] = _id("skl")
    org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    tool_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Slash command: "/command args" in chat, API, automations or webhooks applies this skill to the run.
    command: Mapped[str | None] = mapped_column(String(40), nullable=True)
    argument_hint: Mapped[str] = mapped_column(String(200), default="", server_default="")
    # Optional prompt template for the command; {{ args }} is what the user typed after the command.
    command_template: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Tool(TimestampMixin, Base):
    __tablename__ = "tools"
    id: Mapped[str] = _id("tool")
    org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(64))  # function name exposed to the model
    display_name: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(20), default="http")  # builtin | http | agent
    builtin_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str] = mapped_column(String(40), default="custom")
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # JSON schema
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Connection(TimestampMixin, Base):
    """An installed app connector (GitHub, Slack, Notion, MCP server, ...) for an org."""

    __tablename__ = "connections"
    id: Mapped[str] = _id("con")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    connector_key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    config_enc: Mapped[str] = mapped_column(Text, default="")  # encrypted JSON (tokens etc.)
    public_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # non-secret fields
    enabled_tools: Mapped[list[str]] = mapped_column(JSON, default=list)  # empty = all
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Team(TimestampMixin, Base):
    __tablename__ = "teams"
    id: Mapped[str] = _id("team")
    org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    style: Mapped[str] = mapped_column(String(20), default="sequential")
    members: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)  # [{agent_id, role, instructions}]
    manager_agent_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Workflow(TimestampMixin, Base):
    __tablename__ = "workflows"
    id: Mapped[str] = _id("wf")
    org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    graph: Mapped[dict[str, Any]] = mapped_column(JSON, default=lambda: {"nodes": [], "edges": []})
    input_fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)  # [{name,label,type,default}]
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


# --------------------------------------------------------------------------- knowledge & memory
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


class Lesson(TimestampMixin, Base):
    """A proposed (or taught) lesson for an agent. Approved lessons become agent memories."""

    __tablename__ = "lessons"
    __table_args__ = (Index("ix_lessons_agent", "org_id", "agent_id", "status"),)
    id: Mapped[str] = _id("lsn")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    agent_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | approved | rejected
    source: Mapped[str] = mapped_column(String(20), default="auto")  # user | feedback | auto
    title: Mapped[str] = mapped_column(String(120), default="")
    content: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text, default="")
    conversation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    memory_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


# --------------------------------------------------------------------------- execution
class Automation(TimestampMixin, Base):
    __tablename__ = "automations"
    id: Mapped[str] = _id("auto")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    target_type: Mapped[str] = mapped_column(String(20))  # agent | team | workflow
    target_id: Mapped[str] = mapped_column(String(32))
    input: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    trigger_type: Mapped[str] = mapped_column(String(20), default="manual")  # schedule | interval | webhook | manual
    cron: Mapped[str] = mapped_column(String(120), default="")
    interval_minutes: Mapped[int] = mapped_column(Integer, default=0)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    webhook_token_enc: Mapped[str] = mapped_column(Text, default="")
    webhook_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_status: Mapped[str] = mapped_column(String(20), default="")
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"
    id: Mapped[str] = _id("cnv")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(32))
    target_type: Mapped[str] = mapped_column(String(20))  # agent | team
    target_id: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255), default="New chat")
    skill_ids: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")  # extra skills for this chat


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = _id("msg")
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (Index("ix_runs_org_created", "org_id", "created_at"),)
    id: Mapped[str] = _id("run")
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(20))  # agent | team | workflow
    target_id: Mapped[str] = mapped_column(String(32))
    target_name: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|succeeded|failed|cancelled
    input: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    trigger: Mapped[str] = mapped_column(String(20), default="manual")
    automation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class RunEvent(Base):
    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(40))
    agent: Mapped[str] = mapped_column(String(120), default="")
    node_id: Mapped[str] = mapped_column(String(64), default="")
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_org_created", "org_id", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(40), default="")
    target_id: Mapped[str] = mapped_column(String(64), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
