import pytest
import uuid
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from db.base_class import Base


@pytest.fixture(scope="function")
def test_db_url():
    return f"sqlite+aiosqlite:///test_{uuid.uuid4().hex}.db"


@pytest.fixture(scope="function")
async def test_engine(test_db_url):
    engine = create_async_engine(test_db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
def test_session_maker(test_engine):
    return sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest.fixture
async def db_session(test_session_maker) -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        yield session
        await session.rollback()
