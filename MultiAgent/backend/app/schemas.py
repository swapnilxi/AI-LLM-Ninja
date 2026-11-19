"""Pydantic request/response schemas (with input limits as a safeguard)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["owner", "admin", "member", "viewer"]
TargetType = Literal["agent", "team", "workflow"]
Style = Literal["sequential", "parallel", "supervisor", "router", "round_robin"]
Effort = Literal["low", "medium", "high", "xhigh", "max"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth / users
class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=256)
    org_name: str | None = Field(default=None, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserOut(ORM):
    id: str
    email: str
    name: str
    is_superadmin: bool
    created_at: datetime
    last_login_at: datetime | None = None


class UpdateMeIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    current_password: str | None = Field(default=None, max_length=256)
    new_password: str | None = Field(default=None, min_length=8, max_length=256)


class OrgOut(ORM):
    id: str
    name: str
    slug: str
    context: str
    settings: dict[str, Any]
    created_at: datetime


class OrgWithRole(OrgOut):
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    orgs: list[OrgWithRole]


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    context: str | None = Field(default=None, max_length=20000)
    settings: dict[str, Any] | None = None


class MemberOut(BaseModel):
    id: str
    user_id: str
    email: str
    name: str
    role: str
    created_at: datetime


class MemberAdd(BaseModel):
    email: EmailStr
    role: Role = "member"
    name: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=256)


class MemberUpdate(BaseModel):
    role: Role


class ProviderIn(BaseModel):
    api_key: str | None = Field(default=None, max_length=500)
    base_url: str | None = Field(default=None, max_length=500)


class SecretIn(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: str = Field(min_length=1, max_length=10000)
    description: str = Field(default="", max_length=300)


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: Role = "member"
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


# ---------------------------------------------------------------- projects
class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    context: str = Field(default="", max_length=50000)
    variables: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    context: str | None = Field(default=None, max_length=50000)
    variables: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None
    archived: bool | None = None


class ProjectOut(ORM):
    id: str
    org_id: str
    name: str
    description: str
    context: str
    variables: dict[str, Any]
    settings: dict[str, Any]
    archived: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------- library
class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    avatar: str = Field(default="bot", max_length=40, pattern=r"^[a-z0-9-]+$")
    color: str = Field(default="indigo", max_length=20)
    provider: str = Field(default="default", max_length=40)
    model: str = Field(default="", max_length=120)
    system_prompt: str = Field(default="", max_length=50000)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int = Field(default=8000, ge=256, le=128000)
    max_steps: int = Field(default=8, ge=1, le=30)
    effort: Effort = "medium"
    tool_ids: list[str] = Field(default_factory=list, max_length=100)
    skill_ids: list[str] = Field(default_factory=list, max_length=50)
    connection_ids: list[str] = Field(default_factory=list, max_length=50)
    settings: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=20)
    scope: Literal["org", "global"] = "org"


class AgentOut(ORM):
    id: str
    org_id: str | None
    name: str
    description: str
    avatar: str
    color: str
    provider: str
    model: str
    system_prompt: str
    temperature: float | None
    max_tokens: int
    max_steps: int
    effort: str
    tool_ids: list[str]
    skill_ids: list[str]
    connection_ids: list[str]
    settings: dict[str, Any]
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    instructions: str = Field(default="", max_length=50000)
    tool_ids: list[str] = Field(default_factory=list, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=20)
    command: str | None = Field(default=None, max_length=40)
    argument_hint: str = Field(default="", max_length=200)
    command_template: str = Field(default="", max_length=20000)
    scope: Literal["org", "global"] = "org"

    @field_validator("command")
    @classmethod
    def _cmd(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lstrip("/").lower()
        return v or None


class SkillImport(BaseModel):
    markdown: str = Field(min_length=1, max_length=60000)


class SkillInstall(BaseModel):
    command: str = Field(min_length=1, max_length=500)
    paths: list[str] | None = Field(default=None, max_length=200)


class SkillOut(ORM):
    id: str
    org_id: str | None
    name: str
    description: str
    instructions: str
    tool_ids: list[str]
    tags: list[str]
    command: str | None = None
    argument_hint: str | None = ""
    command_template: str | None = ""
    created_at: datetime
    updated_at: datetime


class ToolIn(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$")
    display_name: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=4000)
    kind: Literal["http", "agent"] = "http"
    category: str = Field(default="custom", max_length=40)
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}, "required": []})
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    scope: Literal["org", "global"] = "org"

    @field_validator("parameters")
    @classmethod
    def _params(cls, v: dict[str, Any]) -> dict[str, Any]:
        if v.get("type") != "object":
            raise ValueError("parameters must be a JSON schema with type 'object'")
        v.setdefault("properties", {})
        return v


class ToolOut(ORM):
    id: str
    org_id: str | None
    name: str
    display_name: str
    description: str
    kind: str
    builtin_key: str | None
    category: str
    parameters: dict[str, Any]
    config: dict[str, Any]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ToolTest(BaseModel):
    project_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class TeamMember(BaseModel):
    agent_id: str
    role: str = Field(default="", max_length=200)
    instructions: str = Field(default="", max_length=4000)


class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    style: Style = "sequential"
    members: list[TeamMember] = Field(default_factory=list, max_length=20)
    manager_agent_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    scope: Literal["org", "global"] = "org"


class TeamOut(ORM):
    id: str
    org_id: str | None
    name: str
    description: str
    style: str
    members: list[dict[str, Any]]
    manager_agent_id: str | None
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class WorkflowIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    graph: dict[str, Any] = Field(default_factory=lambda: {"nodes": [], "edges": []})
    input_fields: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    scope: Literal["org", "global"] = "org"


class WorkflowOut(ORM):
    id: str
    org_id: str | None
    name: str
    description: str
    graph: dict[str, Any]
    input_fields: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------- connectors
class ConnectionIn(BaseModel):
    connector_key: str = Field(max_length=40)
    name: str = Field(min_length=1, max_length=120)
    config: dict[str, Any] = Field(default_factory=dict)
    enabled_tools: list[str] = Field(default_factory=list)
    enabled: bool = True


class ConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    config: dict[str, Any] | None = None
    enabled_tools: list[str] | None = None
    enabled: bool | None = None


# ---------------------------------------------------------------- knowledge / memory
OwnerType = Literal["org", "project", "agent"]


class DocumentIn(BaseModel):
    owner_type: OwnerType
    owner_id: str
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=2_000_000)
    pinned: bool = False


class DocumentFromUrl(BaseModel):
    owner_type: OwnerType
    owner_id: str
    url: str = Field(max_length=2000)
    title: str | None = Field(default=None, max_length=255)
    pinned: bool = False


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, max_length=2_000_000)
    pinned: bool | None = None


class DocumentOut(ORM):
    id: str
    owner_type: str
    owner_id: str
    title: str
    source: str
    source_ref: str
    mime: str
    size: int
    chunk_count: int
    pinned: bool
    created_at: datetime
    updated_at: datetime


class DocumentFull(DocumentOut):
    content: str


class MemoryIn(BaseModel):
    scope: Literal["agent", "project"]
    agent_id: str | None = None
    project_id: str | None = None
    key: str = Field(default="", max_length=120)
    content: str = Field(min_length=1, max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class MemoryUpdate(BaseModel):
    key: str | None = Field(default=None, max_length=120)
    content: str | None = Field(default=None, max_length=4000)


class MemoryOut(ORM):
    id: str
    scope: str
    agent_id: str | None
    project_id: str | None
    key: str
    content: str
    tags: list[str]
    source: str
    run_id: str | None
    created_at: datetime


class LessonIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    title: str = Field(default="", max_length=120)


class LessonUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    title: str | None = Field(default=None, max_length=120)


class LessonOut(ORM):
    id: str
    agent_id: str
    status: str
    source: str
    title: str
    content: str
    rationale: str
    conversation_id: str | None
    message_id: str | None
    run_id: str | None
    memory_id: str | None
    created_at: datetime


class TrainingSettingsIn(BaseModel):
    auto_learn: bool


class ReflectIn(BaseModel):
    conversation_id: str | None = None


# ---------------------------------------------------------------- runs / chat / automations
class RunCreate(BaseModel):
    project_id: str
    target_type: TargetType
    target_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    wait: bool = False
    wait_timeout: int = Field(default=120, ge=1, le=600)


class RunOut(ORM):
    id: str
    project_id: str
    target_type: str
    target_id: str
    target_name: str
    status: str
    input: dict[str, Any]
    output: str
    error: str
    trigger: str
    automation_id: str | None
    conversation_id: str | None
    user_id: str | None
    usage: dict[str, Any]
    total_tokens: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunEventOut(ORM):
    id: int
    seq: int
    type: str
    agent: str
    node_id: str
    data: dict[str, Any]
    created_at: datetime


class ConversationIn(BaseModel):
    project_id: str
    target_type: Literal["agent", "team"]
    target_id: str
    title: str = Field(default="New chat", max_length=255)


class ConversationOut(ORM):
    id: str
    project_id: str
    target_type: str
    target_id: str
    title: str
    skill_ids: list[str] | None = None
    created_at: datetime
    updated_at: datetime


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)


class MessageOut(ORM):
    id: str
    role: str
    content: str
    run_id: str | None
    meta: dict[str, Any]
    created_at: datetime


class AutomationIn(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    target_type: TargetType
    target_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    trigger_type: Literal["schedule", "interval", "webhook", "manual"] = "manual"
    cron: str = Field(default="", max_length=120)
    interval_minutes: int = Field(default=0, ge=0, le=60 * 24 * 31)
    timezone: str = Field(default="UTC", max_length=64)
    enabled: bool = True


class AutomationUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    target_type: TargetType | None = None
    target_id: str | None = None
    input: dict[str, Any] | None = None
    trigger_type: Literal["schedule", "interval", "webhook", "manual"] | None = None
    cron: str | None = Field(default=None, max_length=120)
    interval_minutes: int | None = Field(default=None, ge=0, le=60 * 24 * 31)
    timezone: str | None = Field(default=None, max_length=64)
    enabled: bool | None = None


class AutomationOut(ORM):
    id: str
    project_id: str
    name: str
    description: str
    target_type: str
    target_id: str
    input: dict[str, Any]
    trigger_type: str
    cron: str
    interval_minutes: int
    timezone: str
    enabled: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_status: str
    run_count: int
    created_at: datetime
    webhook_url: str | None = None


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    skill_ids: list[str] | None = Field(default=None, max_length=20)


class FeedbackIn(BaseModel):
    feedback: Literal["up", "down"] | None = None
    note: str = Field(default="", max_length=1000)


class ExportIn(BaseModel):
    agent_ids: list[str] = Field(default_factory=list, max_length=200)
    skill_ids: list[str] = Field(default_factory=list, max_length=200)
    tool_ids: list[str] = Field(default_factory=list, max_length=200)
    team_ids: list[str] = Field(default_factory=list, max_length=200)
    workflow_ids: list[str] = Field(default_factory=list, max_length=200)
    include_dependencies: bool = True


class ImportIn(BaseModel):
    bundle: dict[str, Any]


# ---------------------------------------------------------------- tasks (to-dos)
TaskStatus = Literal["todo", "doing", "done"]
TaskPriority = Literal["low", "normal", "high"]


class TaskIn(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=255)
    notes: str = Field(default="", max_length=4000)
    context: str = Field(default="", max_length=8000)
    priority: TaskPriority = "normal"
    status: TaskStatus = "todo"
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)
    context: str | None = Field(default=None, max_length=8000)
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    due_at: datetime | None = None  # send null to clear (fields are applied with exclude_unset)


class TaskOut(ORM):
    id: str
    project_id: str
    title: str
    notes: str
    context: str
    status: str
    priority: str
    due_at: datetime | None
    completed_at: datetime | None
    source: str
    conversation_id: str | None
    message_id: str | None
    run_id: str | None
    created_at: datetime
    updated_at: datetime


class TaskItemIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    notes: str = Field(default="", max_length=4000)
    priority: TaskPriority = "normal"
    due_at: datetime | None = None


class TaskExtractIn(BaseModel):
    project_id: str
    text: str = Field(default="", max_length=20000)  # empty + message_id => use that chat message
    context: str = Field(default="", max_length=4000)  # extra background attached to every task ("context giver")
    hint: str = Field(default="", max_length=500)
    conversation_id: str | None = None
    message_id: str | None = None
    save: bool = False


class TaskBulkIn(BaseModel):
    project_id: str
    items: list[TaskItemIn] = Field(min_length=1, max_length=50)
    context: str = Field(default="", max_length=8000)
    conversation_id: str | None = None
    message_id: str | None = None
    source: Literal["chat", "text", "manual"] = "text"


class TaskRunIn(BaseModel):
    agent_id: str | None = None


# ---------------------------------------------------------------- AI scheduler
class ScheduleDraftIn(BaseModel):
    project_id: str
    text: str = Field(min_length=3, max_length=2000)
    timezone: str = Field(default="", max_length=64)
    agent_id: str | None = None


# ---------------------------------------------------------------- discover hub
class HubSkillInstall(BaseModel):
    pack_id: str | None = Field(default=None, max_length=80)  # a curated pack...
    source: str | None = Field(default=None, max_length=200)  # ...or a registry result: owner/repo + skill
    skill: str | None = Field(default=None, max_length=120)
    project_id: str | None = None  # also attach to this project (project-level skill)


class HubMcpInstall(BaseModel):
    server_id: str = Field(max_length=80)
    token: str = Field(default="", max_length=4000)
    name: str = Field(default="", max_length=120)
    project_id: str | None = None


class HubKnowledgeInstall(BaseModel):
    item_id: str = Field(max_length=80)
    project_id: str
    pinned: bool = False
