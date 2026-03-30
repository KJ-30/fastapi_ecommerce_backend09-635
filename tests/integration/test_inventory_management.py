from decimal import Decimal
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inventory import (
    InventoryService,
    InventoryResult,
    InventoryStatus,
    InventoryCheck,
)
import crud


class TestInventoryServiceIntegrationCheckAvailability:
    @pytest.mark.asyncio
    async def test_should_return_available_when_sufficient_stock(
        self,
        db_session: AsyncSession,
        sample_product,
        sample_inventory,
    ):
        service = InventoryService(db_session)
        
        result = await service.check_availability(
            product_id=sample_product.id,
            requested_quantity=10,
        )
        
        assert result.is_available is True
        assert result.available_quantity >= 10
    
    @pytest.mark.asyncio
    async def test_should_return_unavailable_when_insufficient_stock(
        self,
        db_session: AsyncSession,
        sample_product,
        sample_inventory,
    ):
        service = InventoryService(db_session)
        
        result = await service.check_availability(
            product_id=sample_product.id,
            requested_quantity=1000,
        )
        
        assert result.is_available is False
    
    @pytest.mark.asyncio
    async def test_should_return_unavailable_when_no_inventory(
        self,
        db_session: AsyncSession,
        sample_product,
    ):
        service = InventoryService(db_session)
        
        result = await service.check_availability(
            product_id=sample_product.id,
            requested_quantity=10,
        )
        
        assert result.is_available is False
        assert result.available_quantity == 0
    
    @pytest.mark.asyncio
    async def test_should_return_unavailable_when_quantity_zero(
        self,
        db_session: AsyncSession,
        sample_product,
    ):
        service = InventoryService(db_session)
        
        result = await service.check_availability(
            product_id=sample_product.id,
            requested_quantity=0,
        )
        
        assert result.is_available is False


class TestInventoryServiceIntegrationReserveInventory:
    @pytest.mark.asyncio
    async def test_should_reserve_inventory_when_sufficient_stock(
        self,
        db_session: AsyncSession,
        sample_product,
        sample_inventory,
    ):
        service = InventoryService(db_session)
        
        initial_quantity = sample_inventory.quantity
        
        result = await service.reserve_inventory(
            product_id=sample_product.id,
            quantity=10,
        )
        
        assert result.success is True
        assert result.available_quantity == initial_quantity - 10
    
    @pytest.mark.asyncio
    async def test_should_update_product_quantity_when_reserved(
        self,
        db_session: AsyncSession,
        sample_product,
        sample_inventory,
    ):
        service = InventoryService(db_session)
        
        initial_product_quantity = sample_product.quantity
        
        await service.reserve_inventory(
            product_id=sample_product.id,
            quantity=10,
        )
        
        updated_product = await crud.product.get(db_session, id=sample_product.id)
        
        assert updated_product.quantity == initial_product_quantity - 10
    
    @pytest.mark.asyncio
    async def test_should_fail_when_insufficient_stock(
        self,
        db_session: AsyncSession,
        sample_product,
        sample_inventory,
    ):
        service = InventoryService(db_session)
        
        result = await service.reserve_inventory(
            product_id=sample_product.id,
            quantity=10000,
        )
        
        assert result.success is False
        assert result.status == InventoryStatus.OUT_OF_STOCK
    
    @pytest.mark.asyncio
    async def test_should_fail_when_quantity_zero(
        self,
        db_session: AsyncSession,
        sample_product,
    ):
        service = InventoryService(db_session)
        
        result = await service.reserve_inventory(
            product_id=sample_product.id,
            quantity=0,
        )
        
        assert result.success is False
    
    @pytest.mark.asyncio
    async def test_should_deplete_multiple_inventories_fifo(
        self,
        db_session: AsyncSession,
        sample_product,
    ):
        from models.inventory import Inventory
        from datetime import datetime, timedelta
        
        inv1 = Inventory(
            product_id=sample_product.id,
            quantity=10,
            created_at=datetime.utcnow() - timedelta(days=1),
            updated_at=datetime.utcnow(),
        )
        inv2 = Inventory(
            product_id=sample_product.id,
            quantity=20,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(inv1)
        db_session.add(inv2)
        await db_session.commit()
        await db_session.refresh(inv1)
        await db_session.refresh(inv2)
        
        service = InventoryService(db_session)
        
        result = await service.reserve_inventory(
            product_id=sample_product.id,
            quantity=15,
        )
        
        assert result.success is True
        
        inventories = await crud.inventory.get_by_product_id(
            db_session, product_id=sample_product.id
        )
        
        total_remaining = sum(inv.quantity for inv in inventories)
        assert total_remaining == 15


class TestInventoryServiceIntegrationReleaseInventory:
    @pytest.mark.asyncio
    async def test_should_release_inventory_when_inventory_exists(
        self,
        db_session: AsyncSession,
        sample_product,
        sample_inventory,
    ):
        service = InventoryService(db_session)
        
        inventories_before = await crud.inventory.get_by_product_id(
            db_session, product_id=sample_product.id
        )
        total_before = sum(inv.quantity for inv in inventories_before)
        
        result = await service.release_inventory(
            product_id=sample_product.id,
            quantity=10,
        )
        
        assert result.success is True
        assert result.available_quantity == total_before + 10
    
    @pytest.mark.asyncio
    async def test_should_update_product_quantity_when_released(
        self,
        db_session: AsyncSession,
        sample_product,
        sample_inventory,
    ):
        service = InventoryService(db_session)
        
        initial_product_quantity = sample_product.quantity
        
        await service.release_inventory(
            product_id=sample_product.id,
            quantity=10,
        )
        
        updated_product = await crud.product.get(db_session, id=sample_product.id)
        
        assert updated_product.quantity == initial_product_quantity + 10
    
    @pytest.mark.asyncio
    async def test_should_fail_when_no_inventory_records(
        self,
        db_session: AsyncSession,
        sample_product,
    ):
        service = InventoryService(db_session)
        
        result = await service.release_inventory(
            product_id=sample_product.id,
            quantity=10,
        )
        
        assert result.success is False


class TestInventoryServiceIntegrationAddInventory:
    @pytest.mark.asyncio
    async def test_should_add_inventory_when_product_exists(
        self,
        db_session: AsyncSession,
        sample_product,
    ):
        service = InventoryService(db_session)
        
        result = await service.add_inventory(
            product_id=sample_product.id,
            quantity=25,
        )
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_should_create_new_inventory_record(
        self,
        db_session: AsyncSession,
        sample_product,
    ):
        service = InventoryService(db_session)
        
        initial_inventories = await crud.inventory.get_by_product_id(
            db_session, product_id=sample_product.id
        )
        initial_count = len(initial_inventories)
        
        await service.add_inventory(
            product_id=sample_product.id,
            quantity=25,
        )
        
        updated_inventories = await crud.inventory.get_by_product_id(
            db_session, product_id=sample_product.id
        )
        
        assert len(updated_inventories) == initial_count + 1
    
    @pytest.mark.asyncio
    async def test_should_update_product_quantity_when_added(
        self,
        db_session: AsyncSession,
        sample_product,
    ):
        service = InventoryService(db_session)
        
        initial_quantity = sample_product.quantity
        
        await service.add_inventory(
            product_id=sample_product.id,
            quantity=25,
        )
        
        updated_product = await crud.product.get(db_session, id=sample_product.id)
        
        assert updated_product.quantity == initial_quantity + 25
    
    @pytest.mark.asyncio
    async def test_should_fail_when_product_not_found(
        self,
        db_session: AsyncSession,
    ):
        service = InventoryService(db_session)
        
        result = await service.add_inventory(
            product_id=9999,
            quantity=25,
        )
        
        assert result.success is False
        assert "Product not found" in result.message


class TestInventoryServiceIntegrationGetStatus:
    @pytest.mark.asyncio
    async def test_should_return_available_status_when_sufficient_stock(
        self,
        db_session: AsyncSession,
        sample_product,
        sample_inventory,
    ):
        service = InventoryService(db_session)
        
        sample_inventory.quantity = 100
        await db_session.commit()
        
        result = await service.get_inventory_status(product_id=sample_product.id)
        
        assert result.success is True
        assert result.status == InventoryStatus.AVAILABLE
    
    @pytest.mark.asyncio
    async def test_should_return_low_stock_status_when_below_threshold(
        self,
        db_session: AsyncSession,
        sample_product,
        sample_inventory,
    ):
        service = InventoryService(db_session)
        
        sample_inventory.quantity = 5
        await db_session.commit()
        
        result = await service.get_inventory_status(product_id=sample_product.id)
        
        assert result.success is True
        assert result.status == InventoryStatus.LOW_STOCK
    
    @pytest.mark.asyncio
    async def test_should_return_out_of_stock_status_when_zero(
        self,
        db_session: AsyncSession,
        sample_product,
        sample_inventory,
    ):
        service = InventoryService(db_session)
        
        sample_inventory.quantity = 0
        await db_session.commit()
        
        result = await service.get_inventory_status(product_id=sample_product.id)
        
        assert result.success is True
        assert result.status == InventoryStatus.OUT_OF_STOCK
    
    @pytest.mark.asyncio
    async def test_should_return_overstocked_status_when_exceeds_threshold(
        self,
        db_session: AsyncSession,
        sample_product,
        sample_inventory,
    ):
        service = InventoryService(db_session)
        
        sample_inventory.quantity = 1500
        await db_session.commit()
        
        result = await service.get_inventory_status(product_id=sample_product.id)
        
        assert result.success is True
        assert result.status == InventoryStatus.OVERSTOCKED


class TestInventoryServiceIntegrationLowStock:
    @pytest.mark.asyncio
    async def test_should_return_low_stock_products(
        self,
        db_session: AsyncSession,
        sample_category,
    ):
        from models.product import Product
        
        low_stock_product = Product(
            product_name="Low Stock Item",
            description="A low stock product",
            category_id=sample_category.id,
            price=Decimal("10.00"),
            quantity=5,
            is_active=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(low_stock_product)
        await db_session.commit()
        
        service = InventoryService(db_session)
        
        result = await service.get_low_stock_products(threshold=10)
        
        assert len(result) >= 1
        low_stock_found = any(p[1] <= 10 for p in result)
        assert low_stock_found
    
    @pytest.mark.asyncio
    async def test_should_use_default_threshold(
        self,
        db_session: AsyncSession,
        sample_category,
    ):
        from models.product import Product
        
        product = Product(
            product_name="Test Item",
            description="Test",
            category_id=sample_category.id,
            price=Decimal("10.00"),
            quantity=8,
            is_active=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(product)
        await db_session.commit()
        
        service = InventoryService(db_session)
        
        result = await service.get_low_stock_products()
        
        assert any(p[0] == product.id for p in result)


class TestInventoryServiceIntegrationTransfer:
    @pytest.mark.asyncio
    async def test_should_transfer_inventory_between_products(
        self,
        db_session: AsyncSession,
        sample_category,
    ):
        from models.product import Product
        from models.inventory import Inventory
        
        product1 = Product(
            product_name="Source Product",
            description="Source",
            category_id=sample_category.id,
            price=Decimal("10.00"),
            quantity=100,
            is_active=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        product2 = Product(
            product_name="Target Product",
            description="Target",
            category_id=sample_category.id,
            price=Decimal("15.00"),
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
        
        inventory1 = Inventory(
            product_id=product1.id,
            quantity=100,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(inventory1)
        await db_session.commit()
        
        service = InventoryService(db_session)
        
        from_result, to_result = await service.transfer_inventory(
            from_product_id=product1.id,
            to_product_id=product2.id,
            quantity=30,
        )
        
        assert from_result.success is True
        assert to_result.success is True
    
    @pytest.mark.asyncio
    async def test_should_fail_transfer_when_insufficient_source_stock(
        self,
        db_session: AsyncSession,
        sample_category,
    ):
        from models.product import Product
        
        product1 = Product(
            product_name="Low Stock Source",
            description="Source",
            category_id=sample_category.id,
            price=Decimal("10.00"),
            quantity=5,
            is_active=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        product2 = Product(
            product_name="Target",
            description="Target",
            category_id=sample_category.id,
            price=Decimal("15.00"),
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
        
        service = InventoryService(db_session)
        
        from_result, to_result = await service.transfer_inventory(
            from_product_id=product1.id,
            to_product_id=product2.id,
            quantity=100,
        )
        
        assert from_result.success is False
        assert to_result.success is False


class TestInventoryServiceIntegrationBulkOperations:
    @pytest.mark.asyncio
    async def test_should_check_multiple_products_availability(
        self,
        db_session: AsyncSession,
        sample_product,
        sample_inventory,
    ):
        service = InventoryService(db_session)
        
        items = [
            (sample_product.id, 10),
            (sample_product.id, 5),
        ]
        
        results = await service.check_multiple_availability(items)
        
        assert len(results) == 2
        assert all(r.product_id == sample_product.id for r in results)
    
    @pytest.mark.asyncio
    async def test_should_bulk_reserve_inventory(
        self,
        db_session: AsyncSession,
        sample_product,
        sample_inventory,
    ):
        service = InventoryService(db_session)
        
        sample_inventory.quantity = 100
        await db_session.commit()
        
        items = [
            (sample_product.id, 10),
            (sample_product.id, 20),
        ]
        
        results = await service.bulk_reserve(items)
        
        assert len(results) == 2
        assert all(r.success for r in results)


class TestInventoryServiceIntegrationFullWorkflow:
    @pytest.mark.asyncio
    async def test_should_complete_full_inventory_workflow(
        self,
        db_session: AsyncSession,
        sample_product,
    ):
        service = InventoryService(db_session)
        
        add_result = await service.add_inventory(
            product_id=sample_product.id,
            quantity=100,
        )
        assert add_result.success is True
        
        check_result = await service.check_availability(
            product_id=sample_product.id,
            requested_quantity=30,
        )
        assert check_result.is_available is True
        
        reserve_result = await service.reserve_inventory(
            product_id=sample_product.id,
            quantity=30,
        )
        assert reserve_result.success is True
        
        status_result = await service.get_inventory_status(
            product_id=sample_product.id
        )
        assert status_result.available_quantity == 70
        
        release_result = await service.release_inventory(
            product_id=sample_product.id,
            quantity=10,
        )
        assert release_result.success is True
        
        final_status = await service.get_inventory_status(
            product_id=sample_product.id
        )
        assert final_status.available_quantity == 80
