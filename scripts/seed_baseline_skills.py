"""Seed the database with baseline AgentForge skills.

These skills are the fallback when external registries (skills.sh, openclaw)
are unreachable. They cover broad, domain-agnostic capabilities so every
generated agent has at least 2 matched skills.

Usage:
    uv run python scripts/seed_baseline_skills.py
"""

import asyncio
import os
import sys

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.enums import SkillSourceRegistry
from app.models.skill import Skill

_BASELINE_SKILLS: list[dict] = [
    {
        "name": "Web Research",
        "slug": "agentforge-web-research",
        "description": "Search the web, retrieve URLs, and synthesise information from multiple sources into a structured summary.",
        "content": (
            "## Web Research\n\n"
            "Performs targeted web searches, fetches page content, deduplicates sources, "
            "and returns a concise summary with citations.\n\n"
            "### Inputs\n- `query` (str): the search query\n- `max_sources` (int, default 5)\n\n"
            "### Outputs\n- `summary` (str): synthesised answer\n- `sources` (list[str]): URLs used"
        ),
        "category": None,
        "tags": ["research", "search", "web", "information", "retrieval", "synthesis"],
        "source_registry": SkillSourceRegistry.AGENTFORGE,
        "source_url": None,
        "source_author": "AgentForge",
        "install_count": 0,
    },
    {
        "name": "Structured Communication",
        "slug": "agentforge-structured-communication",
        "description": "Draft, format, and send structured communications including emails, reports, and Slack messages.",
        "content": (
            "## Structured Communication\n\n"
            "Composes clear, audience-appropriate written communications.\n\n"
            "### Inputs\n- `audience` (str): target recipient description\n"
            "- `intent` (str): the goal of the message\n"
            "- `format` (str): email | report | slack | markdown\n\n"
            "### Outputs\n- `draft` (str): formatted message ready to send"
        ),
        "category": None,
        "tags": ["communication", "email", "writing", "reporting", "messaging", "draft"],
        "source_registry": SkillSourceRegistry.AGENTFORGE,
        "source_url": None,
        "source_author": "AgentForge",
        "install_count": 0,
    },
    {
        "name": "Data Analysis",
        "slug": "agentforge-data-analysis",
        "description": "Analyse structured datasets, identify patterns, compute statistics, and produce actionable insights.",
        "content": (
            "## Data Analysis\n\n"
            "Accepts tabular or JSON data and returns descriptive statistics, trend detection, "
            "and a plain-language insight summary.\n\n"
            "### Inputs\n- `data` (list[dict] | str): dataset or CSV string\n"
            "- `question` (str): the analytical question to answer\n\n"
            "### Outputs\n- `insights` (str): key findings\n- `statistics` (dict): computed metrics"
        ),
        "category": None,
        "tags": ["analysis", "data", "statistics", "insights", "trends", "patterns"],
        "source_registry": SkillSourceRegistry.AGENTFORGE,
        "source_url": None,
        "source_author": "AgentForge",
        "install_count": 0,
    },
    {
        "name": "Task Planning",
        "slug": "agentforge-task-planning",
        "description": "Break a high-level goal into an ordered, dependency-aware list of executable sub-tasks.",
        "content": (
            "## Task Planning\n\n"
            "Decomposes a complex goal into a dependency-ordered task graph with estimated "
            "effort and required resources for each node.\n\n"
            "### Inputs\n- `goal` (str): the high-level objective\n"
            "- `constraints` (list[str], optional): time, budget, or resource constraints\n\n"
            "### Outputs\n- `tasks` (list[dict]): ordered sub-tasks with fields "
            "`id`, `description`, `depends_on`, `effort_hours`"
        ),
        "category": None,
        "tags": ["planning", "tasks", "decomposition", "workflow", "scheduling", "organisation"],
        "source_registry": SkillSourceRegistry.AGENTFORGE,
        "source_url": None,
        "source_author": "AgentForge",
        "install_count": 0,
    },
]


async def seed(session: AsyncSession) -> None:
    inserted = 0
    skipped = 0
    for skill_data in _BASELINE_SKILLS:
        result = await session.execute(
            select(Skill).where(Skill.slug == skill_data["slug"])
        )
        existing = result.scalar_one_or_none()
        if existing:
            skipped += 1
            print(f"  SKIP  {skill_data['slug']} (already exists)")
            continue

        skill = Skill(**skill_data)
        session.add(skill)
        inserted += 1
        print(f"  INSERT {skill_data['slug']}")

    await session.commit()
    print(f"\nDone — {inserted} inserted, {skipped} skipped.")


async def main() -> None:
    print("Seeding baseline AgentForge skills…\n")
    engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
