import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from app.services.payment import PaymentService
from app.services.inventory import InventoryService
from models.product import Product
from models.category import Category
from crud.schemas import ProductCreate, CategoryCreate


class TestPaymentIntegration:
    """Integration tests for PaymentService"""

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
            quantity=0,
            is_active=1
        )
        product = await product_crud.create(db_session, obj_in=product_create)
        return product

    @pytest.fixture
    async def test_product2(self, db_session: AsyncSession, test_category):
        from crud.product import product as product_crud
        
        product_create = ProductCreate(
            product_name="Test Product 2",
            description="Test Description 2",
            category_id=test_category.id,
            price=29.99,
            quantity=0,
            is_active=1
        )
        product = await product_crud.create(db_session, obj_in=product_create)
        return product

    @pytest.fixture
    async def payment_service(self, db_session: AsyncSession):
        return PaymentService(db_session)

    @pytest.fixture
    async def inventory_service(self, db_session: AsyncSession):
        return InventoryService(db_session)

    @pytest.mark.asyncio
    async def test_should_process_single_item_successfully_when_valid_data(
        self, payment_service, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 10)
        
        result = await payment_service.process_single_item(test_product.id, 5)
        
        assert result["success"] is True
        assert result["item"]["product_id"] == test_product.id
        assert result["item"]["quantity"] == 5
        assert result["amount"] == Decimal("54.95")

    @pytest.mark.asyncio
    async def test_should_fail_when_process_single_item_with_insufficient_stock(
        self, payment_service, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 5)
        
        result = await payment_service.process_single_item(test_product.id, 10)
        
        assert result["success"] is False
        assert result["reason"] == "Insufficient stock"

    @pytest.mark.asyncio
    async def test_should_fail_when_process_single_item_with_inactive_product(
        self, payment_service, db_session, test_category
    ):
        from crud.product import product as product_crud
        
        product_create = ProductCreate(
            product_name="Inactive Product",
            description="Inactive",
            category_id=test_category.id,
            price=10.99,
            quantity=10,
            is_active=0
        )
        product = await product_crud.create(db_session, obj_in=product_create)
        
        result = await payment_service.process_single_item(product.id, 2)
        
        assert result["success"] is False
        assert result["reason"] == "Product not found or inactive"

    @pytest.mark.asyncio
    async def test_should_process_multiple_items_when_process_payment(
        self, payment_service, inventory_service, test_product, test_product2
    ):
        await inventory_service.add_inventory(test_product.id, 10)
        await inventory_service.add_inventory(test_product2.id, 10)
        
        items = [
            {"product_id": test_product.id, "quantity": 2},
            {"product_id": test_product2.id, "quantity": 1},
        ]
        
        successful, failed, total = await payment_service.process_payment(1, items)
        
        assert len(successful) == 2
        assert len(failed) == 0
        assert total == Decimal("51.97")

    @pytest.mark.asyncio
    async def test_should_handle_mixed_results_when_process_payment(
        self, payment_service, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 5)
        
        items = [
            {"product_id": test_product.id, "quantity": 2},
            {"product_id": 999, "quantity": 1},
        ]
        
        successful, failed, total = await payment_service.process_payment(1, items)
        
        assert len(successful) == 1
        assert len(failed) == 1
        assert total == Decimal("21.98")

    @pytest.mark.asyncio
    async def test_should_create_sale_record_when_valid_purchase(
        self, payment_service, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 10)
        
        items = [{"product_id": test_product.id, "quantity": 2}]
        successful, failed, total = await payment_service.process_payment(1, items)
        
        assert len(successful) == 1
        
        result = await payment_service.create_sale_record(1, successful, total)
        
        assert "sale" in result
        assert "sale_items" in result
        assert result["sale"]["user_id"] == 1
        assert float(result["sale"]["total_amount"]) == 21.98
        assert len(result["sale_items"]) == 1

    @pytest.mark.asyncio
    async def test_should_validate_payment_method_correctly(
        self, payment_service
    ):
        assert payment_service.validate_payment_method("credit_card") is True
        assert payment_service.validate_payment_method("debit_card") is True
        assert payment_service.validate_payment_method("paypal") is True
        assert payment_service.validate_payment_method("stripe") is True
        assert payment_service.validate_payment_method("invalid") is False
        assert payment_service.validate_payment_method("") is False

    @pytest.mark.asyncio
    async def test_should_update_product_quantity_after_purchase(
        self, payment_service, inventory_service, test_product, db_session
    ):
        from crud.product import product as product_crud
        
        await inventory_service.add_inventory(test_product.id, 10)
        await product_crud.update(db_session, db_obj=test_product, obj_in={"quantity": 10})
        
        await payment_service.process_single_item(test_product.id, 3)
        
        updated_product = await product_crud.get(db_session, id=test_product.id)
        assert updated_product.quantity == 7

    @pytest.mark.asyncio
    async def test_should_deduct_inventory_correctly_after_purchase(
        self, payment_service, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 10)
        
        await payment_service.process_single_item(test_product.id, 3)
        
        total = await inventory_service.get_total_quantity(test_product.id)
        assert total == 7

    @pytest.mark.asyncio
    async def test_should_refund_payment_successfully_when_valid_sale_id(
        self, payment_service, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 10)
        
        items = [{"product_id": test_product.id, "quantity": 2}]
        successful, failed, total = await payment_service.process_payment(1, items)
        sale_record = await payment_service.create_sale_record(1, successful, total)
        
        before_refund_total = await inventory_service.get_total_quantity(test_product.id)
        
        result = await payment_service.refund_payment(sale_record["sale"]["id"])
        
        assert result is True
        
        after_refund_total = await inventory_service.get_total_quantity(test_product.id)
        assert after_refund_total == before_refund_total + 2

    @pytest.mark.asyncio
    async def test_should_return_false_when_refund_payment_with_invalid_sale_id(
        self, payment_service
    ):
        result = await payment_service.refund_payment(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_return_empty_when_process_payment_with_empty_items(
        self, payment_service
    ):
        successful, failed, total = await payment_service.process_payment(1, [])
        
        assert successful == []
        assert failed == []
        assert total == Decimal(0)

    @pytest.mark.asyncio
    async def test_should_reject_invalid_quantity_when_process_single_item(
        self, payment_service, inventory_service, test_product
    ):
        await inventory_service.add_inventory(test_product.id, 10)
        
        result = await payment_service.process_single_item(test_product.id, 0)
        
        assert result["success"] is False
