from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AgentLiteral = Literal["claude_code", "codex", "cursor", "grok", "grok_bot"]
PriorityLiteral = Literal["low", "medium", "high", "urgent"]


class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    agent: AgentLiteral = "cursor"
    priority: PriorityLiteral = "medium"
    project_path: str = ""


class TaskCreate(TaskBase):
    column_id: int
    position: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    agent: AgentLiteral | None = None
    priority: PriorityLiteral | None = None
    project_path: str | None = None
    column_id: int | None = None
    position: int | None = None


class TaskMove(BaseModel):
    column_id: int
    position: int


class TaskOut(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    column_id: int
    position: int
    source: str = "manual"
    external_key: str | None = None
    live: bool = False
    last_seen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ColumnCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = "#64748b"
    position: int | None = None


class ColumnUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = None
    position: int | None = None


class ColumnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    position: int
    color: str
    created_at: datetime
    tasks: list[TaskOut] = []


class BoardOut(BaseModel):
    columns: list[ColumnOut]
    hidden_projects: list[str] = []


class HiddenProjectIn(BaseModel):
    path: str = Field(max_length=500)


class HiddenProjectsOut(BaseModel):
    paths: list[str]
