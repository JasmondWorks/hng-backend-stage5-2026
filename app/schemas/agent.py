import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ClarificationItem(BaseModel):
    round: int
    question: str
    answer: str


class GenerateRequest(BaseModel):
    description: str = Field(min_length=10, max_length=2000)
    clarifications: list[ClarificationItem] = []


class AgentDraft(BaseModel):
    """Internal schema used to validate the LLM's JSON output."""

    status: Literal["needs_clarification", "complete"]
    questions: list[str] | None = None
    round: int | None = None
    name: str | None = None
    category: Literal["marketing", "development", "research", "finance"] | None = None
    description_summary: str | None = Field(default=None, max_length=200)
    identity: str | None = None
    soul: str | None = None
    dna: str | None = None
    heartbeat: str | None = None
    skills_keywords: list[str] | None = None


class NeedsClarificationResponse(BaseModel):
    status: Literal["needs_clarification"]
    round: int
    questions: list[str]


class SkillOut(BaseModel):
    name: str
    slug: str
    description: str
    source_registry: str


class GenerateResponse(BaseModel):
    status: Literal["complete"]
    agent_id: uuid.UUID
    name: str
    category: str
    description_summary: str
    files: dict[str, str]
    skills: list[SkillOut]
    generated_at: datetime
