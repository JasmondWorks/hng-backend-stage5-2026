import re
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _async_db_url(url: str) -> str:
    """Normalise a PostgreSQL URL for SQLAlchemy's asyncpg dialect.

    Handles three common mismatches that occur when a URL is copied from
    Neon, Supabase, or similar cloud dashboards that default to the
    libpq/psycopg2 format:

    1. Scheme  — rewrite postgresql:// → postgresql+asyncpg://
    2. SSL     — rewrite sslmode=require → ssl=require  (asyncpg parameter name)
    3. channel_binding — strip; asyncpg does not accept this libpq-only parameter
    """
    # 1. Scheme
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    # 2. SSL parameter name
    url = url.replace("sslmode=", "ssl=")

    # 3. channel_binding — remove the whole key=value pair (with its & or ?)
    url = re.sub(r"[&?]channel_binding=[^&]*", "", url)
    url = re.sub(r"channel_binding=[^&]*&?", "", url)

    return url


_db_url = _async_db_url(str(settings.DATABASE_URL))

engine = create_async_engine(_db_url, echo=False)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
