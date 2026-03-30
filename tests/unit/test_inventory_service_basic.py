from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Tuple

import pytest

from app.services.inventory import (
    InventoryService,
    InventoryResult,
    InventoryStatus,
    InventoryCheck,
)


class TestInventoryServiceInit:
    def test_should_initialize_inventory_service_when_created(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        assert service.db == mock_db
        assert service.LOW_STOCK_THRESHOLD == 10
        assert service.OVERSTOCK_THRESHOLD == 1000


class TestDetermineStatus:
    def test_should_return_out_of_stock_when_quantity_zero(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = service._determine_status(0)
        
        assert result == InventoryStatus.OUT_OF_STOCK
    
    def test_should_return_out_of_stock_when_quantity_negative(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = service._determine_status(-5)
        
        assert result == InventoryStatus.OUT_OF_STOCK
    
    def test_should_return_low_stock_when_quantity_below_threshold(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = service._determine_status(5)
        
        assert result == InventoryStatus.LOW_STOCK
    
    def test_should_return_low_stock_when_quantity_equals_threshold(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = service._determine_status(10)
        
        assert result == InventoryStatus.LOW_STOCK
    
    def test_should_return_available_when_quantity_normal(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = service._determine_status(100)
        
        assert result == InventoryStatus.AVAILABLE
    
    def test_should_return_overstocked_when_quantity_exceeds_threshold(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = service._determine_status(1001)
        
        assert result == InventoryStatus.OVERSTOCKED


class TestCheckAvailability:
    @pytest.mark.asyncio
    async def test_should_return_unavailable_when_quantity_zero(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = await service.check_availability(product_id=1, requested_quantity=0)
        
        assert result.is_available is False
        assert result.available_quantity == 0
    
    @pytest.mark.asyncio
    async def test_should_return_unavailable_when_quantity_negative(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = await service.check_availability(product_id=1, requested_quantity=-5)
        
        assert result.is_available is False
        assert result.available_quantity == 0
    
    @pytest.mark.asyncio
    async def test_should_return_unavailable_when_no_inventory(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[])
            
            result = await service.check_availability(product_id=1, requested_quantity=10)
            
            assert result.is_available is False
            assert result.available_quantity == 0
    
    @pytest.mark.asyncio
    async def test_should_return_available_when_sufficient_inventory(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_inventory = MagicMock()
        mock_inventory.quantity = 50
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[mock_inventory])
            
            result = await service.check_availability(product_id=1, requested_quantity=10)
            
            assert result.is_available is True
            assert result.available_quantity == 50
    
    @pytest.mark.asyncio
    async def test_should_return_unavailable_when_insufficient_inventory(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_inventory = MagicMock()
        mock_inventory.quantity = 5
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[mock_inventory])
            
            result = await service.check_availability(product_id=1, requested_quantity=10)
            
            assert result.is_available is False
            assert result.available_quantity == 5
    
    @pytest.mark.asyncio
    async def test_should_sum_multiple_inventory_records(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_inv1 = MagicMock()
        mock_inv1.quantity = 30
        mock_inv2 = MagicMock()
        mock_inv2.quantity = 20
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[mock_inv1, mock_inv2])
            
            result = await service.check_availability(product_id=1, requested_quantity=40)
            
            assert result.is_available is True
            assert result.available_quantity == 50


class TestCheckMultipleAvailability:
    @pytest.mark.asyncio
    async def test_should_return_empty_list_when_no_items(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = await service.check_multiple_availability([])
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_should_check_multiple_products(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_inventory = MagicMock()
        mock_inventory.quantity = 100
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[mock_inventory])
            
            items = [(1, 10), (2, 20), (3, 30)]
            result = await service.check_multiple_availability(items)
            
            assert len(result) == 3
            assert all(r.is_available for r in result)


class TestReserveInventory:
    @pytest.mark.asyncio
    async def test_should_return_failed_when_quantity_zero(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = await service.reserve_inventory(product_id=1, quantity=0)
        
        assert result.success is False
        assert result.status == InventoryStatus.OUT_OF_STOCK
        assert "Quantity must be greater than zero" in result.message
    
    @pytest.mark.asyncio
    async def test_should_return_failed_when_quantity_negative(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = await service.reserve_inventory(product_id=1, quantity=-5)
        
        assert result.success is False
        assert "Quantity must be greater than zero" in result.message
    
    @pytest.mark.asyncio
    async def test_should_return_failed_when_insufficient_inventory(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_inventory = MagicMock()
        mock_inventory.quantity = 5
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[mock_inventory])
            
            result = await service.reserve_inventory(product_id=1, quantity=10)
            
            assert result.success is False
            assert result.status == InventoryStatus.OUT_OF_STOCK
            assert "Insufficient inventory" in result.message
    
    @pytest.mark.asyncio
    async def test_should_return_failed_when_no_inventory_records(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[])
            
            result = await service.reserve_inventory(product_id=1, quantity=10)
            
            assert result.success is False
            assert result.status == InventoryStatus.OUT_OF_STOCK
    
    @pytest.mark.asyncio
    async def test_should_reserve_inventory_when_sufficient_stock(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_inventory = MagicMock()
        mock_inventory.quantity = 50
        mock_inventory.created_at = datetime.utcnow()
        
        mock_product = MagicMock()
        mock_product.quantity = 50
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[mock_inventory])
            mock_crud.inventory.bulk_update = AsyncMock(return_value=[mock_inventory])
            mock_crud.product.get = AsyncMock(return_value=mock_product)
            mock_crud.product.update = AsyncMock(return_value=mock_product)
            
            result = await service.reserve_inventory(product_id=1, quantity=10)
            
            assert result.success is True
            assert result.available_quantity == 40
    
    @pytest.mark.asyncio
    async def test_should_deplete_multiple_inventories_fifo(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_inv1 = MagicMock()
        mock_inv1.quantity = 10
        mock_inv1.created_at = datetime(2024, 1, 1)
        
        mock_inv2 = MagicMock()
        mock_inv2.quantity = 20
        mock_inv2.created_at = datetime(2024, 1, 2)
        
        mock_product = MagicMock()
        mock_product.quantity = 30
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[mock_inv1, mock_inv2])
            mock_crud.inventory.bulk_update = AsyncMock()
            mock_crud.product.get = AsyncMock(return_value=mock_product)
            mock_crud.product.update = AsyncMock()
            
            result = await service.reserve_inventory(product_id=1, quantity=15)
            
            assert result.success is True
            assert mock_inv1.quantity == 0
            assert mock_inv2.quantity == 15


class TestReleaseInventory:
    @pytest.mark.asyncio
    async def test_should_return_failed_when_quantity_zero(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = await service.release_inventory(product_id=1, quantity=0)
        
        assert result.success is False
        assert "Quantity must be greater than zero" in result.message
    
    @pytest.mark.asyncio
    async def test_should_return_failed_when_quantity_negative(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = await service.release_inventory(product_id=1, quantity=-5)
        
        assert result.success is False
    
    @pytest.mark.asyncio
    async def test_should_return_failed_when_no_inventory_records(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[])
            
            result = await service.release_inventory(product_id=1, quantity=10)
            
            assert result.success is False
            assert "No inventory records found" in result.message
    
    @pytest.mark.asyncio
    async def test_should_release_inventory_to_latest_record(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_inv1 = MagicMock()
        mock_inv1.quantity = 10
        mock_inv1.created_at = datetime(2024, 1, 1)
        
        mock_inv2 = MagicMock()
        mock_inv2.quantity = 20
        mock_inv2.created_at = datetime(2024, 1, 2)
        
        mock_product = MagicMock()
        mock_product.quantity = 30
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[mock_inv1, mock_inv2])
            mock_crud.inventory.bulk_update = AsyncMock()
            mock_crud.product.get = AsyncMock(return_value=mock_product)
            mock_crud.product.update = AsyncMock()
            
            result = await service.release_inventory(product_id=1, quantity=5)
            
            assert result.success is True
            assert mock_inv2.quantity == 25


class TestAddInventory:
    @pytest.mark.asyncio
    async def test_should_return_failed_when_quantity_zero(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = await service.add_inventory(product_id=1, quantity=0)
        
        assert result.success is False
        assert "Quantity must be greater than zero" in result.message
    
    @pytest.mark.asyncio
    async def test_should_return_failed_when_quantity_negative(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = await service.add_inventory(product_id=1, quantity=-5)
        
        assert result.success is False
    
    @pytest.mark.asyncio
    async def test_should_return_failed_when_product_not_found(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.product.get = AsyncMock(return_value=None)
            
            result = await service.add_inventory(product_id=999, quantity=10)
            
            assert result.success is False
            assert "Product not found" in result.message
    
    @pytest.mark.asyncio
    async def test_should_add_inventory_when_product_exists(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_product = MagicMock()
        mock_product.quantity = 50
        
        mock_new_inventory = MagicMock()
        mock_new_inventory.quantity = 10
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.product.get = AsyncMock(return_value=mock_product)
            mock_crud.inventory.create = AsyncMock(return_value=mock_new_inventory)
            mock_crud.product.update = AsyncMock()
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[mock_new_inventory])
            
            result = await service.add_inventory(product_id=1, quantity=10)
            
            assert result.success is True


class TestGetInventoryStatus:
    @pytest.mark.asyncio
    async def test_should_return_failed_when_no_inventory(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[])
            
            result = await service.get_inventory_status(product_id=1)
            
            assert result.success is False
            assert result.status == InventoryStatus.OUT_OF_STOCK
    
    @pytest.mark.asyncio
    async def test_should_return_status_when_inventory_exists(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_inventory = MagicMock()
        mock_inventory.quantity = 50
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[mock_inventory])
            
            result = await service.get_inventory_status(product_id=1)
            
            assert result.success is True
            assert result.status == InventoryStatus.AVAILABLE
            assert result.available_quantity == 50
    
    @pytest.mark.asyncio
    async def test_should_return_low_stock_status_when_below_threshold(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_inventory = MagicMock()
        mock_inventory.quantity = 5
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[mock_inventory])
            
            result = await service.get_inventory_status(product_id=1)
            
            assert result.success is True
            assert result.status == InventoryStatus.LOW_STOCK


class TestGetLowStockProducts:
    @pytest.mark.asyncio
    async def test_should_return_empty_list_when_no_low_stock(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.product.get_products_quantity_le = AsyncMock(return_value=[])
            
            result = await service.get_low_stock_products()
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_should_return_low_stock_products(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_product = MagicMock()
        mock_product.id = 1
        mock_product.quantity = 5
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.product.get_products_quantity_le = AsyncMock(return_value=[mock_product])
            
            result = await service.get_low_stock_products(threshold=10)
            
            assert len(result) == 1
            assert result[0][0] == 1
            assert result[0][1] == 5
            assert result[0][2] == InventoryStatus.LOW_STOCK
    
    @pytest.mark.asyncio
    async def test_should_use_default_threshold_when_not_specified(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.product.get_products_quantity_le = AsyncMock(return_value=[])
            
            await service.get_low_stock_products()
            
            mock_crud.product.get_products_quantity_le.assert_called_once_with(
                mock_db, quantity=10
            )


class TestTransferInventory:
    @pytest.mark.asyncio
    async def test_should_return_both_failed_when_quantity_zero(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        from_result, to_result = await service.transfer_inventory(
            from_product_id=1,
            to_product_id=2,
            quantity=0,
        )
        
        assert from_result.success is False
        assert to_result.success is False
    
    @pytest.mark.asyncio
    async def test_should_return_both_failed_when_quantity_negative(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        from_result, to_result = await service.transfer_inventory(
            from_product_id=1,
            to_product_id=2,
            quantity=-5,
        )
        
        assert from_result.success is False
        assert to_result.success is False
    
    @pytest.mark.asyncio
    async def test_should_transfer_inventory_when_sufficient_stock(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_inventory = MagicMock()
        mock_inventory.quantity = 50
        mock_inventory.created_at = datetime.utcnow()
        
        mock_product = MagicMock()
        mock_product.quantity = 50
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[mock_inventory])
            mock_crud.inventory.bulk_update = AsyncMock()
            mock_crud.product.get = AsyncMock(return_value=mock_product)
            mock_crud.product.update = AsyncMock()
            mock_crud.inventory.create = AsyncMock()
            
            from_result, to_result = await service.transfer_inventory(
                from_product_id=1,
                to_product_id=2,
                quantity=10,
            )
            
            assert from_result.success is True
            assert to_result.success is True


class TestBulkReserve:
    @pytest.mark.asyncio
    async def test_should_return_empty_list_when_no_items(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        result = await service.bulk_reserve([])
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_should_reserve_multiple_items(self):
        mock_db = MagicMock()
        service = InventoryService(mock_db)
        
        mock_inventory = MagicMock()
        mock_inventory.quantity = 100
        mock_inventory.created_at = datetime.utcnow()
        
        mock_product = MagicMock()
        mock_product.quantity = 100
        
        with patch('app.services.inventory.crud') as mock_crud:
            mock_crud.inventory.get_by_product_id = AsyncMock(return_value=[mock_inventory])
            mock_crud.inventory.bulk_update = AsyncMock()
            mock_crud.product.get = AsyncMock(return_value=mock_product)
            mock_crud.product.update = AsyncMock()
            
            items = [(1, 10), (2, 20)]
            result = await service.bulk_reserve(items)
            
            assert len(result) == 2
            assert all(r.success for r in result)


class TestInventoryResult:
    def test_should_create_inventory_result_with_defaults(self):
        result = InventoryResult(
            success=True,
            status=InventoryStatus.AVAILABLE,
            product_id=1,
            available_quantity=100,
        )
        
        assert result.success is True
        assert result.status == InventoryStatus.AVAILABLE
        assert result.product_id == 1
        assert result.available_quantity == 100
        assert result.message is None
        assert result.modified_inventories is None
    
    def test_should_create_inventory_result_with_all_fields(self):
        mock_inventories = [MagicMock()]
        result = InventoryResult(
            success=True,
            status=InventoryStatus.AVAILABLE,
            product_id=1,
            available_quantity=100,
            message="Success",
            modified_inventories=mock_inventories,
        )
        
        assert result.success is True
        assert result.message == "Success"
        assert result.modified_inventories == mock_inventories


class TestInventoryCheck:
    def test_should_create_inventory_check(self):
        check = InventoryCheck(
            product_id=1,
            requested_quantity=10,
            available_quantity=50,
            is_available=True,
        )
        
        assert check.product_id == 1
        assert check.requested_quantity == 10
        assert check.available_quantity == 50
        assert check.is_available is True


class TestInventoryStatusEnum:
    def test_should_have_correct_status_values(self):
        assert InventoryStatus.AVAILABLE.value == "available"
        assert InventoryStatus.LOW_STOCK.value == "low_stock"
        assert InventoryStatus.OUT_OF_STOCK.value == "out_of_stock"
        assert InventoryStatus.OVERSTOCKED.value == "overstocked"
