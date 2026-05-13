from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUser, DBSession
from app.core.rate_limiter import check_rate_limit
from app.schemas.agent import GenerateRequest, GenerateResponse, NeedsClarificationResponse
from app.services.generation.pipeline import run_pipeline

router = APIRouter()


@router.post(
    "/generate",
    summary="Generate an AI agent from a plain-English description",
    response_model=GenerateResponse | NeedsClarificationResponse,
)
async def generate_agent(
    body: GenerateRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    # user_id always comes from the verified JWT — never from the request body.
    user_id = str(current_user.id)

    retry_after = check_rate_limit(user_id)
    if retry_after is not None:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded.", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    result = await run_pipeline(
        description=body.description,
        clarifications=body.clarifications,
        user_id=user_id,
        db=db,
    )
    return result
