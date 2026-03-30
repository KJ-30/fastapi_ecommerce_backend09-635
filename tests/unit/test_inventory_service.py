import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inventory import InventoryService
from models.inventory import Inventory
from models.product import Product


class TestInventoryService:
    """Unit tests for InventoryService"""

    @pytest.fixture
    def mock_db_session(self):
        return Mock(spec=AsyncSession)

    @pytest.fixture
    def inventory_service(self, mock_db_session):
        return InventoryService(mock_db_session)

    @pytest.fixture
    def sample_inventories(self):
        return [
            Inventory(id=1, product_id=1, quantity=5, created_at="2023-01-01"),
            Inventory(id=2, product_id=1, quantity=10, created_at="2023-01-02"),
            Inventory(id=3, product_id=2, quantity=3, created_at="2023-01-01"),
        ]

    @pytest.fixture
    def sample_products(self):
        return [
            Product(id=1, product_name="Test Product 1", quantity=15, price=10.99, is_active=1),
            Product(id=2, product_name="Test Product 2", quantity=3, price=29.99, is_active=1),
        ]

    @pytest.mark.asyncio
    async def test_should_return_inventories_when_get_inventory_by_product_id_with_valid_id(
        self, inventory_service, mock_db_session, sample_inventories
    ):
        with patch("crud.inventory.get_by_product_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [sample_inventories[0], sample_inventories[1]]
            
            result = await inventory_service.get_inventory_by_product_id(1)
            
            assert len(result) == 2
            assert all(inv.product_id == 1 for inv in result)
            mock_get.assert_called_once_with(mock_db_session, product_id=1)

    @pytest.mark.asyncio
    async def test_should_return_empty_list_when_get_inventory_by_product_id_with_invalid_id(
        self, inventory_service, mock_db_session
    ):
        with patch("crud.inventory.get_by_product_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []
            
            result = await inventory_service.get_inventory_by_product_id(999)
            
            assert result == []
            mock_get.assert_called_once_with(mock_db_session, product_id=999)

    @pytest.mark.asyncio
    async def test_should_return_correct_total_quantity_when_get_total_quantity_with_multiple_inventories(
        self, inventory_service, mock_db_session, sample_inventories
    ):
        with patch.object(inventory_service, "get_inventory_by_product_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [sample_inventories[0], sample_inventories[1]]
            
            result = await inventory_service.get_total_quantity(1)
            
            assert result == 15  # 5 + 10
            mock_get.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_should_return_zero_when_get_total_quantity_with_no_inventories(
        self, inventory_service, mock_db_session
    ):
        with patch.object(inventory_service, "get_inventory_by_product_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []
            
            result = await inventory_service.get_total_quantity(999)
            
            assert result == 0
            mock_get.assert_called_once_with(999)

    @pytest.mark.asyncio
    async def test_should_return_true_when_check_stock_availability_with_sufficient_stock(
        self, inventory_service, mock_db_session
    ):
        with patch.object(inventory_service, "get_total_quantity", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = 15
            
            result = await inventory_service.check_stock_availability(1, 10)
            
            assert result is True
            mock_get.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_should_return_false_when_check_stock_availability_with_insufficient_stock(
        self, inventory_service, mock_db_session
    ):
        with patch.object(inventory_service, "get_total_quantity", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = 5
            
            result = await inventory_service.check_stock_availability(1, 10)
            
            assert result is False
            mock_get.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_should_return_true_when_check_stock_availability_with_exact_quantity(
        self, inventory_service, mock_db_session
    ):
        with patch.object(inventory_service, "get_total_quantity", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = 10
            
            result = await inventory_service.check_stock_availability(1, 10)
            
            assert result is True
            mock_get.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_should_create_inventory_when_add_inventory_with_valid_data(
        self, inventory_service, mock_db_session
    ):
        test_inventory = Inventory(id=1, product_id=1, quantity=10)
        
        with patch("crud.inventory.create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = test_inventory
            
            result = await inventory_service.add_inventory(1, 10)
            
            assert result == test_inventory
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_update_inventory_when_update_inventory_with_valid_id(
        self, inventory_service, mock_db_session
    ):
        test_inventory = Inventory(id=1, product_id=1, quantity=10)
        updated_inventory = Inventory(id=1, product_id=1, quantity=20)
        
        with patch("crud.inventory.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = test_inventory
            with patch("crud.inventory.update", new_callable=AsyncMock) as mock_update:
                mock_update.return_value = updated_inventory
                
                result = await inventory_service.update_inventory(1, 20)
                
                assert result == updated_inventory
                mock_get.assert_called_once_with(mock_db_session, id=1)
                mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_return_none_when_update_inventory_with_invalid_id(
        self, inventory_service, mock_db_session
    ):
        with patch("crud.inventory.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            result = await inventory_service.update_inventory(999, 20)
            
            assert result is None
            mock_get.assert_called_once_with(mock_db_session, id=999)

    @pytest.mark.asyncio
    async def test_should_return_true_when_deduct_inventory_with_sufficient_stock(
        self, inventory_service, mock_db_session, sample_inventories
    ):
        with patch.object(inventory_service, "get_inventory_by_product_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [sample_inventories[0], sample_inventories[1]]
            with patch("crud.inventory.bulk_update", new_callable=AsyncMock) as mock_bulk_update:
                mock_bulk_update.return_value = []
                
                result = await inventory_service.deduct_inventory(1, 7)
                
                assert result is True
                mock_get.assert_called_once_with(1)
                mock_bulk_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_return_false_when_deduct_inventory_with_insufficient_stock(
        self, inventory_service, mock_db_session, sample_inventories
    ):
        with patch.object(inventory_service, "get_inventory_by_product_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [sample_inventories[0]]
            
            result = await inventory_service.deduct_inventory(1, 10)
            
            assert result is False
            mock_get.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_should_return_false_when_deduct_inventory_with_no_inventories(
        self, inventory_service, mock_db_session
    ):
        with patch.object(inventory_service, "get_inventory_by_product_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []
            
            result = await inventory_service.deduct_inventory(1, 5)
            
            assert result is False
            mock_get.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_should_return_products_when_get_low_stock_products_with_threshold(
        self, inventory_service, mock_db_session, sample_products
    ):
        with patch("crud.product.get_products_quantity_le", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [sample_products[1]]
            
            result = await inventory_service.get_low_stock_products(5)
            
            assert len(result) == 1
            assert result[0].quantity <= 5
            mock_get.assert_called_once_with(mock_db_session, quantity=5)
