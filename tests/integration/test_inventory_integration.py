import pytest
from decimal import Decimal
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

import crud
from crud.schemas import InventoryCreate, InventoryUpdate
from models.inventory import Inventory
from models.product import Product
from models.category import Category


class TestInventoryCreateFlow:
    @pytest.mark.asyncio
    async def test_should_create_inventory_and_update_product_quantity(
        self, db_session: AsyncSession, test_product: Product
    ):
        initial_quantity = test_product.quantity
        inventory_data = InventoryCreate(product_id=test_product.id, quantity=50)
        
        created_inventory = await crud.inventory.create(db_session, obj_in=inventory_data)
        
        assert created_inventory.id is not None
        assert created_inventory.product_id == test_product.id
        assert created_inventory.quantity == 50
        
        updated_product = await crud.product.get(db_session, id=test_product.id)
        assert updated_product.quantity == initial_quantity

    @pytest.mark.asyncio
    async def test_should_create_multiple_inventories_for_same_product(
        self, db_session: AsyncSession, test_product: Product
    ):
        inventory_data_1 = InventoryCreate(product_id=test_product.id, quantity=30)
        inventory_data_2 = InventoryCreate(product_id=test_product.id, quantity=40)
        
        inv1 = await crud.inventory.create(db_session, obj_in=inventory_data_1)
        inv2 = await crud.inventory.create(db_session, obj_in=inventory_data_2)
        
        inventories = await crud.inventory.get_by_product_id(db_session, product_id=test_product.id)
        inventory_list = list(inventories)
        
        assert len(inventory_list) == 2
        quantities = [inv.quantity for inv in inventory_list]
        assert sorted(quantities) == [30, 40]


class TestInventoryUpdateFlow:
    @pytest.mark.asyncio
    async def test_should_update_inventory_and_verify_persistence(
        self, db_session: AsyncSession, test_inventory: Inventory
    ):
        update_data = InventoryUpdate(quantity=200)
        
        updated = await crud.inventory.update(
            db_session, db_obj=test_inventory, obj_in=update_data
        )
        
        assert updated.quantity == 200
        
        fetched = await crud.inventory.get(db_session, id=test_inventory.id)
        assert fetched.quantity == 200

    @pytest.mark.asyncio
    async def test_should_bulk_update_inventories_and_verify_all_changes(
        self, db_session: AsyncSession, test_product: Product
    ):
        inv1 = await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=test_product.id, quantity=10)
        )
        inv2 = await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=test_product.id, quantity=20)
        )
        inv3 = await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=test_product.id, quantity=30)
        )
        
        inv1.quantity = 100
        inv2.quantity = 200
        inv3.quantity = 300
        
        await crud.inventory.bulk_update(db_session, db_objs=[inv1, inv2, inv3])
        
        fetched_inventories = await crud.inventory.get_by_product_id(
            db_session, product_id=test_product.id
        )
        quantities = {inv.id: inv.quantity for inv in fetched_inventories}
        
        assert quantities[inv1.id] == 100
        assert quantities[inv2.id] == 200
        assert quantities[inv3.id] == 300


class TestInventoryQueryFlow:
    @pytest.mark.asyncio
    async def test_should_get_inventories_by_product_id_with_correct_data(
        self, db_session: AsyncSession, test_product: Product
    ):
        await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=test_product.id, quantity=25)
        )
        await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=test_product.id, quantity=35)
        )
        
        inventories = await crud.inventory.get_by_product_id(db_session, product_id=test_product.id)
        inventory_list = list(inventories)
        
        assert len(inventory_list) == 2
        for inv in inventory_list:
            assert inv.product_id == test_product.id
            assert inv.quantity in [25, 35]

    @pytest.mark.asyncio
    async def test_should_return_empty_list_for_nonexistent_product(
        self, db_session: AsyncSession
    ):
        inventories = await crud.inventory.get_by_product_id(db_session, product_id=99999)
        inventory_list = list(inventories)
        
        assert len(inventory_list) == 0

    @pytest.mark.asyncio
    async def test_should_get_inventory_by_id_with_all_fields(
        self, db_session: AsyncSession, test_inventory: Inventory
    ):
        fetched = await crud.inventory.get(db_session, id=test_inventory.id)
        
        assert fetched is not None
        assert fetched.id == test_inventory.id
        assert fetched.product_id == test_inventory.product_id
        assert fetched.quantity == test_inventory.quantity
        assert fetched.created_at is not None
        assert fetched.updated_at is not None

    @pytest.mark.asyncio
    async def test_should_return_none_for_nonexistent_inventory_id(
        self, db_session: AsyncSession
    ):
        fetched = await crud.inventory.get(db_session, id=99999)
        
        assert fetched is None


class TestInventoryDeleteFlow:
    @pytest.mark.asyncio
    async def test_should_remove_inventory_and_verify_deletion(
        self, db_session: AsyncSession, test_inventory: Inventory
    ):
        inventory_id = test_inventory.id
        
        await crud.inventory.remove(db_session, id=inventory_id)
        
        fetched = await crud.inventory.get(db_session, id=inventory_id)
        assert fetched is None

    @pytest.mark.asyncio
    async def test_should_not_affect_other_inventories_when_removing_one(
        self, db_session: AsyncSession, test_product: Product
    ):
        inv1 = await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=test_product.id, quantity=10)
        )
        inv2 = await crud.inventory.create(
            db_session, obj_in=InventoryCreate(product_id=test_product.id, quantity=20)
        )
        
        await crud.inventory.remove(db_session, id=inv1.id)
        
        remaining = await crud.inventory.get(db_session, id=inv2.id)
        assert remaining is not None
        assert remaining.quantity == 20


class TestInventoryPaginationFlow:
    @pytest.mark.asyncio
    async def test_should_return_paginated_results_with_correct_page_size(
        self, db_session: AsyncSession, test_product: Product
    ):
        for i in range(10):
            inv = Inventory(
                product_id=test_product.id,
                quantity=i * 10,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db_session.add(inv)
        await db_session.commit()
        
        page1 = await crud.inventory.get_multi(
            db_session, page=1, per_page=5, order_by="id", order="asc"
        )
        page1_list = list(page1)
        
        page2 = await crud.inventory.get_multi(
            db_session, page=2, per_page=5, order_by="id", order="asc"
        )
        page2_list = list(page2)
        
        assert len(page1_list) == 5
        assert len(page2_list) == 5

    @pytest.mark.asyncio
    async def test_should_return_different_results_for_different_pages(
        self, db_session: AsyncSession, test_product: Product
    ):
        for i in range(6):
            inv = Inventory(
                product_id=test_product.id,
                quantity=i * 10,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db_session.add(inv)
        await db_session.commit()
        
        page1 = await crud.inventory.get_multi(
            db_session, page=1, per_page=3, order_by="id", order="asc"
        )
        page1_ids = {inv.id for inv in page1}
        
        page2 = await crud.inventory.get_multi(
            db_session, page=2, per_page=3, order_by="id", order="asc"
        )
        page2_ids = {inv.id for inv in page2}
        
        assert not page1_ids.intersection(page2_ids)


class TestInventoryWithProductRelationship:
    @pytest.mark.asyncio
    async def test_should_maintain_product_relationship_after_update(
        self, db_session: AsyncSession, test_inventory: Inventory, test_product: Product
    ):
        update_data = InventoryUpdate(quantity=999)
        
        updated = await crud.inventory.update(
            db_session, db_obj=test_inventory, obj_in=update_data
        )
        
        assert updated.product_id == test_product.id
        
        product_inventories = await crud.inventory.get_by_product_id(
            db_session, product_id=test_product.id
        )
        assert any(inv.id == test_inventory.id for inv in product_inventories)

    @pytest.mark.asyncio
    async def test_should_handle_inventory_for_different_products(
        self, db_session: AsyncSession, test_category: Category
    ):
        product1 = Product(
            product_name="Product 1",
            description="Test",
            category_id=test_category.id,
            price=Decimal("10.00"),
            quantity=0,
            is_active=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        product2 = Product(
            product_name="Product 2",
            description="Test",
            category_id=test_category.id,
            price=Decimal("20.00"),
            quantity=0,
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
            db_session, obj_in=InventoryCreate(product_id=product2.id, quantity=75)
        )
        
        inv1_list = list(await crud.inventory.get_by_product_id(db_session, product_id=product1.id))
        inv2_list = list(await crud.inventory.get_by_product_id(db_session, product_id=product2.id))
        
        assert len(inv1_list) == 1
        assert inv1_list[0].quantity == 50
        assert len(inv2_list) == 1
        assert inv2_list[0].quantity == 75


class TestInventoryBulkCreateFlow:
    @pytest.mark.asyncio
    async def test_should_create_multiple_inventories_in_single_operation(
        self, db_session: AsyncSession, test_product: Product
    ):
        inventory_data_list = [
            InventoryCreate(product_id=test_product.id, quantity=10),
            InventoryCreate(product_id=test_product.id, quantity=20),
            InventoryCreate(product_id=test_product.id, quantity=30),
        ]
        
        created = await crud.inventory.bulk_create(db_session, objs_in=inventory_data_list)
        
        assert len(created) == 3
        assert all(inv.id is not None for inv in created)
        
        all_inventories = await crud.inventory.get_by_product_id(
            db_session, product_id=test_product.id
        )
        quantities = [inv.quantity for inv in all_inventories]
        assert sorted(quantities) == [10, 20, 30]

    @pytest.mark.asyncio
    async def test_should_preserve_order_in_bulk_create(
        self, db_session: AsyncSession, test_product: Product
    ):
        inventory_data_list = [
            InventoryCreate(product_id=test_product.id, quantity=100),
            InventoryCreate(product_id=test_product.id, quantity=200),
        ]
        
        created = await crud.inventory.bulk_create(db_session, objs_in=inventory_data_list)
        
        assert created[0].quantity == 100
        assert created[1].quantity == 200
