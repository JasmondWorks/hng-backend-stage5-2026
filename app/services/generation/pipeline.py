import asyncio
import logging
import uuid

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.agent_clarification import AgentClarification
from app.models.agent_file import AgentFile
from app.models.agent_skill import AgentSkill
from app.models.enums import AgentCategory, AgentStatus, AgentVisibility
from app.schemas.agent import AgentDraft, ClarificationItem
from app.services.generation.context_assembler import assemble
from app.services.generation.file_assembler import assemble_files
from app.services.generation.llm_client import call_llm
from app.services.generation.sanitiser import sanitise
from app.services.generation.skill_matcher import match_skills

logger = logging.getLogger(__name__)

_MAX_CLARIFICATION_ROUNDS = 3


def _make_slug(name: str) -> str:
    base = name.lower().replace(" ", "-")
    # Strip non-alphanumeric/hyphen characters
    base = "".join(c for c in base if c.isalnum() or c == "-")
    return f"{base}-{uuid.uuid4().hex[:8]}"


async def _parse_draft(raw: dict) -> AgentDraft:
    """Validate LLM output. Raises ValidationError on failure."""
    return AgentDraft.model_validate(raw)


async def run_pipeline(
    description: str,
    clarifications: list[ClarificationItem],
    user_id: str,
    db: AsyncSession,
) -> dict:
    """Orchestrate the full agent generation pipeline.

    Returns either a needs_clarification dict or a complete generation dict.
    """
    # Stage 1 — sanitise
    clean_description = sanitise(description)

    # Stage 2 — assemble context; round count derived from clarification list length
    round_count = len(clarifications)
    context = assemble(clean_description, clarifications)

    # Stage 3 — call LLM
    raw = await call_llm(context)

    # Stage 4 — clarification gate: return early if more info needed
    if raw.get("status") == "needs_clarification" and round_count < _MAX_CLARIFICATION_ROUNDS:
        return {
            "status": "needs_clarification",
            "round": raw.get("round", round_count + 1),
            "questions": raw.get("questions", []),
        }

    # Stage 5 — validate against AgentDraft schema
    draft: AgentDraft
    try:
        draft = await _parse_draft(raw)
    except ValidationError:
        # Stage 6 — retry once with a stricter prompt suffix
        logger.warning("LLM output failed validation — retrying with stricter prompt")
        strict_context = context + "\n\nRespond with valid JSON only. No markdown."
        raw2 = await call_llm(strict_context)
        try:
            draft = await _parse_draft(raw2)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="LLM failed to produce a valid agent specification after retry",
            ) from exc

    # Stage 8 — match skills
    keywords = draft.skills_keywords or []
    category_str = draft.category or "development"
    skills = await match_skills(keywords, category_str, db)

    # Stage 9 — assemble files (asyncio.gather structured for future parallelism)
    files, _ = await asyncio.gather(
        assemble_files(draft, skills),
        asyncio.sleep(0),
    )

    # Stage 10 — single DB transaction
    slug = _make_slug(draft.name or "agent")
    agent = Agent(
        user_id=uuid.UUID(user_id),
        name=draft.name or "Unnamed Agent",
        slug=slug,
        category=AgentCategory(category_str),
        description_summary=draft.description_summary or "",
        visibility=AgentVisibility.PRIVATE,
        status=AgentStatus.GENERATED,
        clarification_rounds=round_count,
    )
    db.add(agent)
    await db.flush()  # Populate agent.id without committing

    for filename, content in files.items():
        db.add(AgentFile(agent_id=agent.id, filename=filename, content=content))

    for item in clarifications:
        db.add(
            AgentClarification(
                agent_id=agent.id,
                round=item.round,
                question=item.question,
                answer=item.answer,
            )
        )

    for skill in skills:
        db.add(AgentSkill(agent_id=agent.id, skill_id=skill.id))

    await db.commit()
    await db.refresh(agent)

    # Stage 11 — return response dict
    return {
        "status": "complete",
        "agent_id": agent.id,
        "name": agent.name,
        "category": str(agent.category),
        "description_summary": agent.description_summary,
        "files": files,
        "skills": [
            {
                "name": s.name,
                "slug": s.slug,
                "description": s.description,
                "source_registry": str(s.source_registry),
            }
            for s in skills
        ],
        "generated_at": agent.created_at,
    }
