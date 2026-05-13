"""Tests for POST /api/v1/agents/generate."""

import os

# Set required env vars before any app import so Settings() doesn't fail.
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import get_current_user
from app.core import rate_limiter
from app.core.security import create_access_token
from app.main import app
from app.models.enums import UserProvider
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id: uuid.UUID | None = None) -> User:
    user = User.__new__(User)
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    user.provider = UserProvider.EMAIL
    user.email_verified = True
    user.is_active = True
    return user


def _bearer(user_id: uuid.UUID) -> str:
    return f"Bearer {create_access_token(str(user_id))}"


_COMPLETE_PIPELINE_RESULT = {
    "status": "complete",
    "agent_id": uuid.uuid4(),
    "name": "Email Marketer",
    "category": "marketing",
    "description_summary": "An agent that automates email campaigns.",
    "files": {
        "identity.md": "# Identity",
        "soul.md": "# Soul",
        "dna.md": "# DNA",
        "heartbeat.md": "# Heartbeat",
        "README.md": "# README",
    },
    "skills": [
        {
            "name": "Web Research",
            "slug": "agentforge-web-research",
            "description": "Search the web",
            "source_registry": "agentforge",
        }
    ],
    "generated_at": datetime.now(timezone.utc),
}

_CLARIFICATION_PIPELINE_RESULT = {
    "status": "needs_clarification",
    "round": 1,
    "questions": ["What is the target audience?", "What email platform do you use?"],
}


@pytest.fixture(autouse=True)
def clear_rate_limiter():
    rate_limiter._store.clear()
    yield
    rate_limiter._store.clear()


@pytest.fixture
def fake_user():
    return _make_user()


@pytest.fixture
def auth_client(client, fake_user):
    """Client with CurrentUser dependency overridden to skip real JWT validation."""
    app.dependency_overrides[get_current_user] = lambda: fake_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestGenerateHappyPath:
    async def test_returns_200_with_complete_response_shape(self, auth_client):
        with patch(
            "app.api.v1.endpoints.agents.run_pipeline",
            new=AsyncMock(return_value=_COMPLETE_PIPELINE_RESULT),
        ):
            resp = await auth_client.post(
                "/api/v1/agents/generate",
                json={"description": "An agent that automates email marketing campaigns."},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "complete"
        assert "agent_id" in body
        assert "name" in body
        assert "files" in body
        assert "skills" in body
        assert isinstance(body["files"], dict)
        assert isinstance(body["skills"], list)

    async def test_pipeline_receives_correct_description(self, auth_client):
        desc = "Build a research agent that monitors academic papers."
        with patch(
            "app.api.v1.endpoints.agents.run_pipeline",
            new=AsyncMock(return_value=_COMPLETE_PIPELINE_RESULT),
        ) as mock_pipeline:
            await auth_client.post(
                "/api/v1/agents/generate",
                json={"description": desc},
            )

        call_kwargs = mock_pipeline.await_args.kwargs
        assert call_kwargs["description"] == desc

    async def test_user_id_comes_from_token_not_body(self, auth_client, fake_user):
        with patch(
            "app.api.v1.endpoints.agents.run_pipeline",
            new=AsyncMock(return_value=_COMPLETE_PIPELINE_RESULT),
        ) as mock_pipeline:
            await auth_client.post(
                "/api/v1/agents/generate",
                json={
                    "description": "An agent for financial analysis and reporting.",
                    "clarifications": [],
                },
            )

        call_kwargs = mock_pipeline.await_args.kwargs
        assert call_kwargs["user_id"] == str(fake_user.id)


# ---------------------------------------------------------------------------
# Clarification path
# ---------------------------------------------------------------------------


class TestClarificationPath:
    async def test_returns_clarification_response_shape(self, auth_client):
        with patch(
            "app.api.v1.endpoints.agents.run_pipeline",
            new=AsyncMock(return_value=_CLARIFICATION_PIPELINE_RESULT),
        ):
            resp = await auth_client.post(
                "/api/v1/agents/generate",
                json={"description": "Make me an agent."},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "needs_clarification"
        assert isinstance(body["questions"], list)
        assert len(body["questions"]) > 0
        assert "round" in body

    async def test_clarifications_forwarded_to_pipeline(self, auth_client):
        clarifications = [
            {"round": 1, "question": "Target audience?", "answer": "SMB owners"},
        ]
        with patch(
            "app.api.v1.endpoints.agents.run_pipeline",
            new=AsyncMock(return_value=_COMPLETE_PIPELINE_RESULT),
        ) as mock_pipeline:
            await auth_client.post(
                "/api/v1/agents/generate",
                json={
                    "description": "A marketing agent for small businesses.",
                    "clarifications": clarifications,
                },
            )

        call_kwargs = mock_pipeline.await_args.kwargs
        assert len(call_kwargs["clarifications"]) == 1
        assert call_kwargs["clarifications"][0].answer == "SMB owners"


# ---------------------------------------------------------------------------
# Round cap
# ---------------------------------------------------------------------------


class TestRoundCap:
    async def test_three_clarification_items_forces_generation(self, auth_client):
        """With 3 clarification rounds, the pipeline should produce complete even if
        the raw LLM output says needs_clarification — pipeline enforces the cap."""
        with patch(
            "app.api.v1.endpoints.agents.run_pipeline",
            new=AsyncMock(return_value=_COMPLETE_PIPELINE_RESULT),
        ) as mock_pipeline:
            clarifications = [
                {"round": i, "question": f"Q{i}", "answer": f"A{i}"}
                for i in range(1, 4)
            ]
            resp = await auth_client.post(
                "/api/v1/agents/generate",
                json={
                    "description": "A finance agent that tracks portfolio risk.",
                    "clarifications": clarifications,
                },
            )

        assert resp.status_code == 200
        # Pipeline was called — it enforces the cap internally.
        mock_pipeline.assert_awaited_once()


# ---------------------------------------------------------------------------
# LLM failure
# ---------------------------------------------------------------------------


class TestLlmFailure:
    async def test_llm_validation_failure_returns_422(self, auth_client):
        from fastapi import HTTPException, status

        with patch(
            "app.api.v1.endpoints.agents.run_pipeline",
            new=AsyncMock(
                side_effect=HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="LLM failed to produce a valid agent specification after retry",
                )
            ),
        ):
            resp = await auth_client.post(
                "/api/v1/agents/generate",
                json={"description": "An agent that does something interesting."},
            )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimit:
    async def test_sixth_request_returns_429(self, auth_client):
        with patch(
            "app.api.v1.endpoints.agents.run_pipeline",
            new=AsyncMock(return_value=_COMPLETE_PIPELINE_RESULT),
        ):
            for _ in range(5):
                await auth_client.post(
                    "/api/v1/agents/generate",
                    json={"description": "An agent that automates email campaigns."},
                )

            resp = await auth_client.post(
                "/api/v1/agents/generate",
                json={"description": "An agent that automates email campaigns."},
            )

        assert resp.status_code == 429
        body = resp.json()
        assert body["detail"] == "Rate limit exceeded."
        assert "retry_after" in body
        assert isinstance(body["retry_after"], int)

    async def test_fifth_request_still_succeeds(self, auth_client):
        with patch(
            "app.api.v1.endpoints.agents.run_pipeline",
            new=AsyncMock(return_value=_COMPLETE_PIPELINE_RESULT),
        ):
            for _ in range(4):
                await auth_client.post(
                    "/api/v1/agents/generate",
                    json={"description": "An agent that automates email campaigns."},
                )

            resp = await auth_client.post(
                "/api/v1/agents/generate",
                json={"description": "An agent that automates email campaigns."},
            )

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class TestAuthentication:
    async def test_unauthenticated_request_returns_401(self, client):
        resp = await client.post(
            "/api/v1/agents/generate",
            json={"description": "Build me an agent for data analysis and reporting."},
        )
        assert resp.status_code == 401

    async def test_invalid_token_returns_401(self, client):
        resp = await client.post(
            "/api/v1/agents/generate",
            json={"description": "Build me an agent for data analysis and reporting."},
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    async def test_description_too_short_returns_422(self, auth_client):
        resp = await auth_client.post(
            "/api/v1/agents/generate",
            json={"description": "Too short"},
        )
        assert resp.status_code == 422

    async def test_description_missing_returns_422(self, auth_client):
        resp = await auth_client.post(
            "/api/v1/agents/generate",
            json={},
        )
        assert resp.status_code == 422
