import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inventory import InventoryService
from models.product import Product
from models.category import Category
from models.inventory import Inventory
from crud.schemas import ProductCreate, CategoryCreate


class TestInventoryIntegration:
    """Integration tests for InventoryService"""

    @pytest.fixture
    async def test_category(self, db_session: AsyncSession):
        from crud.category import category as category_crud
        
        category_create = CategoryCreate(category_name="Test Category", category_slug="test-category")
        category = await category_crud.create(db_session, obj_in=category_create)
        return category

    @pytest.fixture
    async def test_product(self, db_session: AsyncSession, test_category):
        from crud.product import product as product_crud
        
        product_create = ProductCreate(
            product_name="Test Product",
            description="Test Description",
            category_id=test_category.id,
            price=10.99,
            quantity=10,
            is_active=1
        )
        product = await product_crud.create(db_session, obj_in=product_create)
        return product

    @pytest.fixture
    async def inventory_service(self, db_session: AsyncSession):
        return InventoryService(db_session)

    @pytest.mark.asyncio
    async def test_should_add_and_retrieve_inventory_when_working_with_db(
        self, inventory_service, test_product
    ):
        inventory = await inventory_service.add_inventory(test_product.id, 10)
        
        assert inventory.id is not None
        assert inventory.product_id == test_product.id
        assert inventory.quantity == 10

    @pytest.mark.asyncio
    async def test_should_return_correct_total_quantity_when_multiple_inventories(
        self, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 5)
        await inventory_service.add_inventory(test_product.id, 10)
        
        total = await inventory_service.get_total_quantity(test_product.id)
        
        assert total == 15

    @pytest.mark.asyncio
    async def test_should_return_true_when_check_stock_availability_with_sufficient_stock(
        self, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 10)
        
        result = await inventory_service.check_stock_availability(test_product.id, 5)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_should_return_false_when_check_stock_availability_with_insufficient_stock(
        self, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 5)
        
        result = await inventory_service.check_stock_availability(test_product.id, 10)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_should_deduct_inventory_correctly_when_sufficient_stock(
        self, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 5)
        await inventory_service.add_inventory(test_product.id, 10)
        
        result = await inventory_service.deduct_inventory(test_product.id, 7)
        
        assert result is True
        
        total = await inventory_service.get_total_quantity(test_product.id)
        assert total == 8  # 15 - 7

    @pytest.mark.asyncio
    async def test_should_not_deduct_when_insufficient_stock(
        self, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 5)
        
        result = await inventory_service.deduct_inventory(test_product.id, 10)
        
        assert result is False
        
        total = await inventory_service.get_total_quantity(test_product.id)
        assert total == 5

    @pytest.mark.asyncio
    async def test_should_update_inventory_quantity_when_update_inventory(
        self, inventory_service, test_product
    ):
        inventory = await inventory_service.add_inventory(test_product.id, 10)
        
        updated = await inventory_service.update_inventory(inventory.id, 20)
        
        assert updated is not None
        assert updated.quantity == 20

    @pytest.mark.asyncio
    async def test_should_return_none_when_update_inventory_with_invalid_id(
        self, inventory_service
    ):
        updated = await inventory_service.update_inventory(999, 20)
        
        assert updated is None

    @pytest.mark.asyncio
    async def test_should_return_inventories_when_get_by_product_id(
        self, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 5)
        await inventory_service.add_inventory(test_product.id, 10)
        
        inventories = await inventory_service.get_inventory_by_product_id(test_product.id)
        
        assert len(inventories) == 2
        assert all(inv.product_id == test_product.id for inv in inventories)

    @pytest.mark.asyncio
    async def test_should_return_empty_when_get_by_nonexistent_product_id(
        self, inventory_service
    ):
        inventories = await inventory_service.get_inventory_by_product_id(999)
        
        assert len(inventories) == 0

    @pytest.mark.asyncio
    async def test_should_return_low_stock_products_when_below_threshold(
        self, inventory_service, db_session, test_category
    ):
        from crud.product import product as product_crud
        
        product1_create = ProductCreate(
            product_name="Low Stock Product",
            description="Low Stock",
            category_id=test_category.id,
            price=10.99,
            quantity=3,
            is_active=1
        )
        product2_create = ProductCreate(
            product_name="High Stock Product",
            description="High Stock",
            category_id=test_category.id,
            price=20.99,
            quantity=20,
            is_active=1
        )
        await product_crud.create(db_session, obj_in=product1_create)
        await product_crud.create(db_session, obj_in=product2_create)
        
        low_stock = await inventory_service.get_low_stock_products(5)
        
        assert len(low_stock) >= 1
        assert any(p.quantity <= 5 for p in low_stock)

    @pytest.mark.asyncio
    async def test_should_deduct_in_fifo_order_when_multiple_inventories(
        self, inventory_service, test_product, db_session
    ):
        inv1 = await inventory_service.add_inventory(test_product.id, 5)
        inv2 = await inventory_service.add_inventory(test_product.id, 10)
        
        result = await inventory_service.deduct_inventory(test_product.id, 7)
        
        assert result is True
        
        inventories = await inventory_service.get_inventory_by_product_id(test_product.id)
        inventories.sort(key=lambda x: x.created_at)
        
        assert inventories[0].quantity == 0
        assert inventories[1].quantity == 8

    @pytest.mark.asyncio
    async def test_should_deduct_entire_inventory_when_exact_amount(
        self, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 10)
        
        result = await inventory_service.deduct_inventory(test_product.id, 10)
        
        assert result is True
        
        total = await inventory_service.get_total_quantity(test_product.id)
        assert total == 0
