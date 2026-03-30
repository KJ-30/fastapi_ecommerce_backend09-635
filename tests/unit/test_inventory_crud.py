import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from crud.inventory import CRUDInventory, inventory
from models.inventory import Inventory
from models.product import Product
from crud.schemas import InventoryCreate, InventoryUpdate


class TestCRUDInventoryGetByProductId:
    @pytest.mark.asyncio
    async def test_should_return_inventory_list_when_product_has_inventories(
        self, db_session: AsyncSession, test_product: Product, test_inventory: Inventory
    ):
        result = await inventory.get_by_product_id(db_session, product_id=test_product.id)
        result_list = list(result)
        assert len(result_list) == 1
        assert result_list[0].id == test_inventory.id
        assert result_list[0].product_id == test_product.id
        assert result_list[0].quantity == 100

    @pytest.mark.asyncio
    async def test_should_return_empty_list_when_product_has_no_inventories(
        self, db_session: AsyncSession
    ):
        result = await inventory.get_by_product_id(db_session, product_id=9999)
        result_list = list(result)
        assert len(result_list) == 0

    @pytest.mark.asyncio
    async def test_should_return_multiple_inventories_when_product_has_multiple_entries(
        self, db_session: AsyncSession, test_product: Product, test_multiple_inventories: list
    ):
        result = await inventory.get_by_product_id(db_session, product_id=test_product.id)
        result_list = list(result)
        assert len(result_list) == 3
        quantities = [inv.quantity for inv in result_list]
        assert sorted(quantities) == [30, 30, 40]


class TestCRUDInventoryCreate:
    @pytest.mark.asyncio
    async def test_should_create_inventory_with_valid_data(
        self, db_session: AsyncSession, test_product: Product
    ):
        inventory_data = InventoryCreate(product_id=test_product.id, quantity=50)
        result = await inventory.create(db_session, obj_in=inventory_data)
        assert result.id is not None
        assert result.product_id == test_product.id
        assert result.quantity == 50
        assert result.created_at is not None
        assert result.updated_at is not None

    @pytest.mark.asyncio
    async def test_should_create_inventory_with_zero_quantity(
        self, db_session: AsyncSession, test_product: Product
    ):
        inventory_data = InventoryCreate(product_id=test_product.id, quantity=0)
        result = await inventory.create(db_session, obj_in=inventory_data)
        assert result.quantity == 0


class TestCRUDInventoryGet:
    @pytest.mark.asyncio
    async def test_should_return_inventory_when_id_exists(
        self, db_session: AsyncSession, test_inventory: Inventory
    ):
        result = await inventory.get(db_session, id=test_inventory.id)
        assert result is not None
        assert result.id == test_inventory.id
        assert result.product_id == test_inventory.product_id

    @pytest.mark.asyncio
    async def test_should_return_none_when_id_does_not_exist(
        self, db_session: AsyncSession
    ):
        result = await inventory.get(db_session, id=9999)
        assert result is None


class TestCRUDInventoryUpdate:
    @pytest.mark.asyncio
    async def test_should_update_inventory_quantity(
        self, db_session: AsyncSession, test_inventory: Inventory
    ):
        update_data = InventoryUpdate(quantity=75)
        result = await inventory.update(
            db_session, db_obj=test_inventory, obj_in=update_data
        )
        assert result.quantity == 75

    @pytest.mark.asyncio
    async def test_should_update_inventory_using_dict(
        self, db_session: AsyncSession, test_inventory: Inventory
    ):
        update_data = {"quantity": 150}
        result = await inventory.update(
            db_session, db_obj=test_inventory, obj_in=update_data
        )
        assert result.quantity == 150


class TestCRUDInventoryBulkUpdate:
    @pytest.mark.asyncio
    async def test_should_update_multiple_inventories(
        self, db_session: AsyncSession, test_multiple_inventories: list
    ):
        inventories = test_multiple_inventories
        inventories[0].quantity = 10
        inventories[1].quantity = 20
        inventories[2].quantity = 30
        
        result = await inventory.bulk_update(db_session, db_objs=inventories)
        
        assert len(result) == 3
        assert result[0].quantity == 10
        assert result[1].quantity == 20
        assert result[2].quantity == 30

    @pytest.mark.asyncio
    async def test_should_return_empty_list_when_no_inventories_provided(
        self, db_session: AsyncSession
    ):
        result = await inventory.bulk_update(db_session, db_objs=[])
        assert result == []


class TestCRUDInventoryBulkCreate:
    @pytest.mark.asyncio
    async def test_should_create_multiple_inventories(
        self, db_session: AsyncSession, test_product: Product
    ):
        inventory_data_list = [
            InventoryCreate(product_id=test_product.id, quantity=10),
            InventoryCreate(product_id=test_product.id, quantity=20),
            InventoryCreate(product_id=test_product.id, quantity=30),
        ]
        result = await inventory.bulk_create(db_session, objs_in=inventory_data_list)
        
        assert len(result) == 3
        assert result[0].quantity == 10
        assert result[1].quantity == 20
        assert result[2].quantity == 30


class TestCRUDInventoryGetMulti:
    @pytest.mark.asyncio
    async def test_should_return_paginated_results(
        self, db_session: AsyncSession, test_product: Product
    ):
        for i in range(5):
            inv = Inventory(
                product_id=test_product.id,
                quantity=10 * (i + 1),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db_session.add(inv)
        await db_session.commit()
        
        result = await inventory.get_multi(
            db_session, page=1, per_page=3, order_by="id", order="asc"
        )
        result_list = list(result)
        assert len(result_list) == 3

    @pytest.mark.asyncio
    async def test_should_return_results_ordered_by_id_when_invalid_order_by(
        self, db_session: AsyncSession, test_product: Product
    ):
        for i in range(3):
            inv = Inventory(
                product_id=test_product.id,
                quantity=10 * (i + 1),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db_session.add(inv)
        await db_session.commit()
        
        result = await inventory.get_multi(
            db_session, page=1, per_page=10, order_by="invalid_field", order="asc"
        )
        result_list = list(result)
        assert len(result_list) >= 3


class TestCRUDInventoryRemove:
    @pytest.mark.asyncio
    async def test_should_remove_inventory_when_id_exists(
        self, db_session: AsyncSession, test_inventory: Inventory
    ):
        inventory_id = test_inventory.id
        await inventory.remove(db_session, id=inventory_id)
        
        result = await inventory.get(db_session, id=inventory_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_should_not_raise_error_when_removing_nonexistent_id(
        self, db_session: AsyncSession
    ):
        await inventory.remove(db_session, id=9999)


class TestCRUDInventoryInitialization:
    def test_should_have_correct_model(self):
        assert inventory.model == Inventory

    def test_should_inherit_from_crud_base(self):
        assert isinstance(inventory, CRUDInventory)
