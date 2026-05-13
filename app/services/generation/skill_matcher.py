import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SkillSourceRegistry
from app.models.skill import Skill

logger = logging.getLogger(__name__)

_MIN_SKILLS = 2
_MAX_SKILLS = 6


async def fetch_from_registry(keywords: list[str], category: str) -> list[Skill]:
    """Stub: fetch skills from external registries (skills.sh, openclaw).

    Not yet implemented — logs intent and returns an empty list.
    """
    logger.info(
        "External registry fetch requested for category=%s keywords=%s — not implemented",
        category,
        keywords,
    )
    return []


async def match_skills(
    keywords: list[str], category: str, db: AsyncSession
) -> list[Skill]:
    """Return 2–6 skills that best match the given keywords and category.

    Scoring: (tag_overlap_count × 2) + (install_count / 1000)
    Falls back to the external registry stub, then to agentforge baseline skills.
    """
    skills: list[Skill] = []

    if keywords:
        result = await db.execute(
            select(Skill).where(
                Skill.tags.overlap(keywords),
                Skill.category == category,
                Skill.is_active.is_(True),
            )
        )
        skills = list(result.scalars().all())

        kw_set = set(keywords)

        def _score(skill: Skill) -> float:
            overlap = len(set(skill.tags or []) & kw_set)
            return overlap * 2 + (skill.install_count / 1000)

        skills.sort(key=_score, reverse=True)
        skills = skills[:_MAX_SKILLS]

    if len(skills) < _MIN_SKILLS:
        registry_results = await fetch_from_registry(keywords, category)
        seen = {s.id for s in skills}
        for s in registry_results:
            if s.id not in seen and len(skills) < _MAX_SKILLS:
                skills.append(s)
                seen.add(s.id)

    if len(skills) < _MIN_SKILLS:
        result = await db.execute(
            select(Skill)
            .where(
                Skill.source_registry == SkillSourceRegistry.AGENTFORGE,
                Skill.is_active.is_(True),
            )
            .limit(_MAX_SKILLS)
        )
        baseline = list(result.scalars().all())
        seen = {s.id for s in skills}
        for s in baseline:
            if s.id not in seen and len(skills) < _MAX_SKILLS:
                skills.append(s)

    return skills[:_MAX_SKILLS]
