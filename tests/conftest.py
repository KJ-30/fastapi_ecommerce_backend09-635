import asyncio
from typing import AsyncGenerator, Generator
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from db.base_class import Base
from db.session import AsyncSessionMaker


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def sample_category(db_session: AsyncSession):
    from models.category import Category
    from datetime import datetime
    
    category = Category(
        category_name="Electronics",
        category_slug="electronics",
        created_at=datetime.utcnow(),
    )
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    return category


@pytest_asyncio.fixture(scope="function")
async def sample_product(db_session: AsyncSession, sample_category):
    from models.product import Product
    from datetime import datetime
    
    product = Product(
        product_name="Test Product",
        description="A test product",
        category_id=sample_category.id,
        price=Decimal("99.99"),
        quantity=100,
        is_active=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest_asyncio.fixture(scope="function")
async def sample_inventory(db_session: AsyncSession, sample_product):
    from models.inventory import Inventory
    from datetime import datetime
    
    inventory = Inventory(
        product_id=sample_product.id,
        quantity=50,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(inventory)
    await db_session.commit()
    await db_session.refresh(inventory)
    return inventory


@pytest_asyncio.fixture(scope="function")
async def sample_user(db_session: AsyncSession):
    from models.user import User
    from datetime import datetime
    
    user = User(
        first_name="Test",
        last_name="User",
        email="test@example.com",
        hashed_password="hashed_password_123",
        is_active=1,
        timezone="UTC",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
