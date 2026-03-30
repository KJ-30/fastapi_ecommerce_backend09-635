import asyncio
import pytest
import pytest_asyncio
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from db.base_class import Base
from models.category import Category
from models.product import Product
from models.inventory import Inventory
from models.user import User
from models.sale import Sale
from models.sale_item import SaleItem


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_category(db_session: AsyncSession) -> Category:
    category = Category(
        category_name="Electronics",
        category_slug="electronics",
        created_at=datetime.utcnow(),
    )
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    return category


@pytest_asyncio.fixture
async def test_product(db_session: AsyncSession, test_category: Category) -> Product:
    product = Product(
        product_name="Test Product",
        description="A test product",
        category_id=test_category.id,
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


@pytest_asyncio.fixture
async def test_product_inactive(db_session: AsyncSession, test_category: Category) -> Product:
    product = Product(
        product_name="Inactive Product",
        description="An inactive test product",
        category_id=test_category.id,
        price=Decimal("49.99"),
        quantity=50,
        is_active=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest_asyncio.fixture
async def test_inventory(db_session: AsyncSession, test_product: Product) -> Inventory:
    inventory = Inventory(
        product_id=test_product.id,
        quantity=100,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(inventory)
    await db_session.commit()
    await db_session.refresh(inventory)
    return inventory


@pytest_asyncio.fixture
async def test_multiple_inventories(db_session: AsyncSession, test_product: Product) -> list[Inventory]:
    inventories = [
        Inventory(
            product_id=test_product.id,
            quantity=30,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        ),
        Inventory(
            product_id=test_product.id,
            quantity=40,
            created_at=datetime(2024, 2, 1),
            updated_at=datetime(2024, 2, 1),
        ),
        Inventory(
            product_id=test_product.id,
            quantity=30,
            created_at=datetime(2024, 3, 1),
            updated_at=datetime(2024, 3, 1),
        ),
    ]
    for inv in inventories:
        db_session.add(inv)
    await db_session.commit()
    for inv in inventories:
        await db_session.refresh(inv)
    return inventories


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        first_name="Test",
        last_name="User",
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=1,
        timezone="UTC",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_sale(db_session: AsyncSession, test_user: User) -> Sale:
    sale = Sale(
        user_id=test_user.id,
        total_amount=Decimal("199.98"),
        created_at=datetime.utcnow(),
    )
    db_session.add(sale)
    await db_session.commit()
    await db_session.refresh(sale)
    return sale


@pytest_asyncio.fixture
async def test_sale_item(db_session: AsyncSession, test_sale: Sale, test_product: Product) -> SaleItem:
    sale_item = SaleItem(
        sale_id=test_sale.id,
        product_id=test_product.id,
        quantity=2,
        price_per_unit=Decimal("99.99"),
    )
    db_session.add(sale_item)
    await db_session.commit()
    await db_session.refresh(sale_item)
    return sale_item
