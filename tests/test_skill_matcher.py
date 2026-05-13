import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import AgentCategory, SkillSourceRegistry
from app.models.skill import Skill
from app.services.generation.skill_matcher import match_skills


def _make_skill(
    name: str,
    tags: list[str],
    install_count: int = 0,
    source_registry: str = SkillSourceRegistry.AGENTFORGE,
    category: str = AgentCategory.DEVELOPMENT,
) -> Skill:
    skill = Skill.__new__(Skill)
    skill.id = uuid.uuid4()
    skill.name = name
    skill.slug = name.lower().replace(" ", "-")
    skill.description = f"Description for {name}"
    skill.content = f"Content for {name}"
    skill.tags = tags
    skill.install_count = install_count
    skill.source_registry = source_registry
    skill.category = category
    skill.is_active = True
    return skill


def _mock_db(first_result: list[Skill], second_result: list[Skill] | None = None) -> AsyncMock:
    """Return an AsyncSession mock whose execute() yields supplied skill lists."""

    def _make_scalars(skills: list[Skill]):
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = skills
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        return mock_result

    db = AsyncMock()
    if second_result is None:
        db.execute = AsyncMock(return_value=_make_scalars(first_result))
    else:
        db.execute = AsyncMock(
            side_effect=[_make_scalars(first_result), _make_scalars(second_result)]
        )
    return db


class TestMatchSkills:
    async def test_cache_hit_returns_matching_skills(self):
        skills = [
            _make_skill("Code Reviewer", ["code", "review", "analysis"], install_count=100),
            _make_skill("Test Runner", ["testing", "code"], install_count=50),
        ]
        db = _mock_db(skills)

        result = await match_skills(["code", "analysis"], AgentCategory.DEVELOPMENT, db)

        assert len(result) >= 2
        names = [s.name for s in result]
        assert "Code Reviewer" in names

    async def test_cache_miss_calls_fetch_from_registry(self):
        db = _mock_db([])  # DB returns nothing

        with patch(
            "app.services.generation.skill_matcher.fetch_from_registry",
            new=AsyncMock(return_value=[]),
        ) as mock_fetch:
            await match_skills(["web", "search"], AgentCategory.RESEARCH, db)

        mock_fetch.assert_awaited_once()

    async def test_fallback_baseline_when_registry_returns_empty(self):
        baseline = [
            _make_skill("Web Research", ["research", "web"], source_registry=SkillSourceRegistry.AGENTFORGE),
            _make_skill("Task Planning", ["planning"], source_registry=SkillSourceRegistry.AGENTFORGE),
        ]
        db = _mock_db([], baseline)  # First call: no matches; second: baseline

        with patch(
            "app.services.generation.skill_matcher.fetch_from_registry",
            new=AsyncMock(return_value=[]),
        ):
            result = await match_skills(["anything"], AgentCategory.MARKETING, db)

        assert len(result) >= 2
        for skill in result:
            assert skill.source_registry == SkillSourceRegistry.AGENTFORGE

    async def test_higher_tag_overlap_ranked_above_lower_overlap(self):
        low_overlap = _make_skill("Low", ["code"], install_count=0)
        high_overlap = _make_skill("High", ["code", "review", "analysis"], install_count=0)
        db = _mock_db([low_overlap, high_overlap])

        result = await match_skills(["code", "review", "analysis"], AgentCategory.DEVELOPMENT, db)

        assert result[0].name == "High"

    async def test_install_count_breaks_tie_in_scoring(self):
        skill_a = _make_skill("Skill A", ["code"], install_count=1000)
        skill_b = _make_skill("Skill B", ["code"], install_count=0)
        db = _mock_db([skill_b, skill_a])  # B first in DB, A should win on score

        result = await match_skills(["code"], AgentCategory.DEVELOPMENT, db)

        assert result[0].name == "Skill A"

    async def test_result_capped_at_six(self):
        many_skills = [
            _make_skill(f"Skill {i}", ["code", "review"], install_count=i)
            for i in range(10)
        ]
        db = _mock_db(many_skills)

        result = await match_skills(["code", "review"], AgentCategory.DEVELOPMENT, db)

        assert len(result) <= 6

    async def test_empty_keywords_skips_tag_query_and_uses_fallback(self):
        baseline = [
            _make_skill("Web Research", ["research"], source_registry=SkillSourceRegistry.AGENTFORGE),
            _make_skill("Task Planning", ["planning"], source_registry=SkillSourceRegistry.AGENTFORGE),
        ]
        db = _mock_db(baseline)

        with patch(
            "app.services.generation.skill_matcher.fetch_from_registry",
            new=AsyncMock(return_value=[]),
        ):
            result = await match_skills([], AgentCategory.DEVELOPMENT, db)

        assert len(result) >= 2
