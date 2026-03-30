import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import patch, MagicMock
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

import crud
from api.v1.endpoints.purchase_products import PurchaseProducts, Item
from api.v1.schemas.purchase_products import PurchaseProductsRequest
from crud.schemas import InventoryCreate
from models.inventory import Inventory
from models.product import Product
from models.user import User
from models.category import Category


class TestPurchaseProductsSuccessFlow:
    @pytest.mark.asyncio
    async def test_should_complete_full_purchase_with_single_inventory(
        self, db_session: AsyncSession, test_user: User, test_product: Product, test_inventory: Inventory
    ):
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[Item(product_id=test_product.id, quantity=5)]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        assert purchase.status_code == status.HTTP_200_OK
        assert purchase.response_message == "Products purchased successfully"
        assert len(purchase.response_data["purchased_items"]) == 1
        assert len(purchase.response_data["failed_items"]) == 0
        
        updated_inventory = await crud.inventory.get(db_session, id=test_inventory.id)
        assert updated_inventory.quantity == 95
        
        updated_product = await crud.product.get(db_session, id=test_product.id)
        assert updated_product.quantity == 95

    @pytest.mark.asyncio
    async def test_should_complete_full_purchase_across_multiple_inventories(
        self, db_session: AsyncSession, test_user: User, test_product: Product
    ):
        inv1 = await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=test_product.id, quantity=10)
        )
        inv2 = await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=test_product.id, quantity=20)
        )
        
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[Item(product_id=test_product.id, quantity=15)]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        assert purchase.status_code == status.HTTP_200_OK
        
        updated_inv1 = await crud.inventory.get(db_session, id=inv1.id)
        updated_inv2 = await crud.inventory.get(db_session, id=inv2.id)
        
        assert updated_inv1.quantity == 0
        assert updated_inv2.quantity == 15

    @pytest.mark.asyncio
    async def test_should_create_sale_record_after_successful_purchase(
        self, db_session: AsyncSession, test_user: User, test_product: Product, test_inventory: Inventory
    ):
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[Item(product_id=test_product.id, quantity=2)]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        sale_data = purchase.response_data
        assert sale_data["id"] is not None
        assert sale_data["user_id"] == test_user.id
        expected_total = Decimal("199.98")
        assert sale_data["total_amount"] == expected_total

    @pytest.mark.asyncio
    async def test_should_create_sale_items_after_successful_purchase(
        self, db_session: AsyncSession, test_user: User, test_product: Product, test_inventory: Inventory
    ):
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[Item(product_id=test_product.id, quantity=3)]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        purchased_items = purchase.response_data["purchased_items"]
        assert len(purchased_items) == 1
        assert purchased_items[0]["product_id"] == test_product.id
        assert purchased_items[0]["quantity"] == 3


class TestPurchaseProductsFailureFlow:
    @pytest.mark.asyncio
    async def test_should_mark_item_as_failed_when_product_not_found(
        self, db_session: AsyncSession, test_user: User
    ):
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[Item(product_id=99999, quantity=1)]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        assert len(purchase.response_data["failed_items"]) == 1
        assert purchase.response_data["failed_items"][0].product_id == 99999

    @pytest.mark.asyncio
    async def test_should_mark_item_as_failed_when_product_inactive(
        self, db_session: AsyncSession, test_user: User, test_product_inactive: Product
    ):
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[Item(product_id=test_product_inactive.id, quantity=1)]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        assert len(purchase.response_data["failed_items"]) == 1
        assert purchase.response_data["failed_items"][0].product_id == test_product_inactive.id

    @pytest.mark.asyncio
    async def test_should_mark_item_as_failed_when_no_inventory(
        self, db_session: AsyncSession, test_user: User, test_product: Product
    ):
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[Item(product_id=test_product.id, quantity=1)]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        assert len(purchase.response_data["failed_items"]) == 1
        assert len(purchase.response_data["purchased_items"]) == 0

    @pytest.mark.asyncio
    async def test_should_mark_item_as_failed_when_insufficient_inventory(
        self, db_session: AsyncSession, test_user: User, test_product: Product
    ):
        await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=test_product.id, quantity=5)
        )
        
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[Item(product_id=test_product.id, quantity=10)]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        assert len(purchase.response_data["failed_items"]) == 1
        assert len(purchase.response_data["purchased_items"]) == 0


class TestPurchaseProductsMixedFlow:
    @pytest.mark.asyncio
    async def test_should_process_mixed_successful_and_failed_items(
        self, db_session: AsyncSession, test_user: User, test_product: Product, test_inventory: Inventory
    ):
        nonexistent_product_id = 99999
        
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[
                Item(product_id=test_product.id, quantity=5),
                Item(product_id=nonexistent_product_id, quantity=1),
            ]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        assert len(purchase.response_data["purchased_items"]) == 1
        assert len(purchase.response_data["failed_items"]) == 1
        
        updated_inventory = await crud.inventory.get(db_session, id=test_inventory.id)
        assert updated_inventory.quantity == 95

    @pytest.mark.asyncio
    async def test_should_process_multiple_successful_items(
        self, db_session: AsyncSession, test_user: User, test_category: Category
    ):
        product1 = Product(
            product_name="Product 1",
            description="Test",
            category_id=test_category.id,
            price=Decimal("50.00"),
            quantity=100,
            is_active=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        product2 = Product(
            product_name="Product 2",
            description="Test",
            category_id=test_category.id,
            price=Decimal("75.00"),
            quantity=100,
            is_active=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(product1)
        db_session.add(product2)
        await db_session.commit()
        await db_session.refresh(product1)
        await db_session.refresh(product2)
        
        await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=product1.id, quantity=50)
        )
        await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=product2.id, quantity=50)
        )
        
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[
                Item(product_id=product1.id, quantity=2),
                Item(product_id=product2.id, quantity=3),
            ]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        assert len(purchase.response_data["purchased_items"]) == 2
        assert len(purchase.response_data["failed_items"]) == 0
        
        expected_total = Decimal("325.00")
        assert purchase.response_data["total_amount"] == expected_total


class TestPurchaseProductsInventoryDepletion:
    @pytest.mark.asyncio
    async def test_should_deplete_inventory_exactly_when_quantity_matches(
        self, db_session: AsyncSession, test_user: User, test_product: Product
    ):
        await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=test_product.id, quantity=10)
        )
        
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[Item(product_id=test_product.id, quantity=10)]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        assert purchase.status_code == status.HTTP_200_OK
        
        inventories = await crud.inventory.get_by_product_id(db_session, product_id=test_product.id)
        for inv in inventories:
            assert inv.quantity == 0

    @pytest.mark.asyncio
    async def test_should_deplete_oldest_inventory_first(
        self, db_session: AsyncSession, test_user: User, test_product: Product
    ):
        old_inventory = Inventory(
            product_id=test_product.id,
            quantity=5,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        )
        new_inventory = Inventory(
            product_id=test_product.id,
            quantity=20,
            created_at=datetime(2024, 6, 1),
            updated_at=datetime(2024, 6, 1),
        )
        db_session.add(old_inventory)
        db_session.add(new_inventory)
        await db_session.commit()
        await db_session.refresh(old_inventory)
        await db_session.refresh(new_inventory)
        
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[Item(product_id=test_product.id, quantity=10)]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        updated_old = await crud.inventory.get(db_session, id=old_inventory.id)
        updated_new = await crud.inventory.get(db_session, id=new_inventory.id)
        
        assert updated_old.quantity == 0
        assert updated_new.quantity == 15


class TestPurchaseProductsEdgeCases:
    @pytest.mark.asyncio
    async def test_should_handle_empty_items_list(
        self, db_session: AsyncSession, test_user: User
    ):
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(items=[])
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        assert purchase.status_code == status.HTTP_200_OK
        assert len(purchase.response_data["purchased_items"]) == 0
        assert len(purchase.response_data["failed_items"]) == 0
        assert purchase.response_data["total_amount"] == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_should_handle_all_failed_items(
        self, db_session: AsyncSession, test_user: User
    ):
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[
                Item(product_id=99999, quantity=1),
                Item(product_id=88888, quantity=2),
            ]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        assert purchase.status_code == status.HTTP_200_OK
        assert len(purchase.response_data["purchased_items"]) == 0
        assert len(purchase.response_data["failed_items"]) == 2

    @pytest.mark.asyncio
    async def test_should_handle_large_quantity_purchase(
        self, db_session: AsyncSession, test_user: User, test_product: Product
    ):
        await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=test_product.id, quantity=1000)
        )
        
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[Item(product_id=test_product.id, quantity=500)]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        assert purchase.status_code == status.HTTP_200_OK
        assert len(purchase.response_data["purchased_items"]) == 1

    @pytest.mark.asyncio
    async def test_should_preserve_product_quantity_consistency(
        self, db_session: AsyncSession, test_user: User, test_product: Product, test_inventory: Inventory
    ):
        initial_product_qty = test_product.quantity
        purchase_qty = 25
        
        purchase = PurchaseProducts()
        purchase.db = db_session
        purchase.request_data = PurchaseProductsRequest(
            items=[Item(product_id=test_product.id, quantity=purchase_qty)]
        )
        
        with patch("api.v1.endpoints.purchase_products.context") as mock_context:
            mock_context.data = {"user": {"id": test_user.id}}
            await purchase.process_flow()
        
        updated_product = await crud.product.get(db_session, id=test_product.id)
        assert updated_product.quantity == initial_product_qty - purchase_qty
