import json
import logging

from fastapi import HTTPException, status
from openai import APIStatusError, APITimeoutError, AsyncOpenAI, AuthenticationError, BadRequestError, NotFoundError

from app.core.config import settings
from app.services.generation.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            timeout=9.0,
        )
    return _client


async def call_llm(context: str) -> dict:
    """Send context to the LLM and return the parsed JSON response.

    Raises HTTP 502 on upstream timeout or 5xx error.
    Hard timeout: 9 seconds (enforced by the AsyncOpenAI client).
    """
    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            response_format={"type": "json_object"},
        )
        raw_content = response.choices[0].message.content or "{}"
        return json.loads(raw_content)
    except APITimeoutError as exc:
        logger.warning("LLM request timed out")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM upstream timed out",
        ) from exc
    except AuthenticationError as exc:
        logger.error("OpenRouter API key is invalid or missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM service is misconfigured — check OPENROUTER_API_KEY",
        ) from exc
    except NotFoundError as exc:
        logger.error("OpenRouter model not found: %s", settings.OPENROUTER_MODEL)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM model '{settings.OPENROUTER_MODEL}' not found on OpenRouter — check OPENROUTER_MODEL",
        ) from exc
    except BadRequestError as exc:
        logger.error("OpenRouter bad request for model %s: %s", settings.OPENROUTER_MODEL, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM rejected the request for model '{settings.OPENROUTER_MODEL}' — check OPENROUTER_MODEL",
        ) from exc
    except APIStatusError as exc:
        if exc.status_code >= 500:
            logger.warning("LLM upstream returned %s", exc.status_code)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM upstream error",
            ) from exc
        # 4xx errors not already handled above (e.g. 402 payment required)
        logger.error("LLM upstream returned unexpected %s: %s", exc.status_code, exc.message)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM upstream error ({exc.status_code}): {exc.message}",
        ) from exc
    except json.JSONDecodeError as exc:
        logger.warning("LLM returned non-JSON content")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM returned invalid JSON",
        ) from exc
