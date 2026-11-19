import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://app:app@localhost:5432/app",
)

engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one database session per request."""
    async with SessionLocal() as session:
        yield session
