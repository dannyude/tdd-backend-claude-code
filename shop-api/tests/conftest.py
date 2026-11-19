import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.db.base import Base
from app.db.session import get_session
from app.main import app

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5433/test"
)


@pytest.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    async with engine.connect() as conn:
        trans = await conn.begin()
        maker = async_sessionmaker(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        async with maker() as s:
            yield s
        await trans.rollback()


@pytest.fixture
async def client(session):
    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
