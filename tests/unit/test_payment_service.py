import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from app.services.payment import PaymentService
from models.product import Product


class TestPaymentService:
    """Unit tests for PaymentService"""

    @pytest.fixture
    def mock_db_session(self):
        return Mock(spec=AsyncSession)

    @pytest.fixture
    def payment_service(self, mock_db_session):
        return PaymentService(mock_db_session)

    @pytest.fixture
    def sample_product(self):
        return Product(
            id=1,
            product_name="Test Product",
            category_id=1,
            price=Decimal("10.99"),
            quantity=10,
            is_active=1
        )

    @pytest.fixture
    def sample_items(self):
        return [
            {"product_id": 1, "quantity": 2},
            {"product_id": 2, "quantity": 1},
        ]

    def test_should_return_true_when_validate_payment_method_with_valid_method(
        self, payment_service
    ):
        valid_methods = ["credit_card", "debit_card", "paypal", "stripe"]
        
        for method in valid_methods:
            result = payment_service.validate_payment_method(method)
            assert result is True

    def test_should_return_false_when_validate_payment_method_with_invalid_method(
        self, payment_service
    ):
        invalid_methods = ["cash", "crypto", "invalid", ""]
        
        for method in invalid_methods:
            result = payment_service.validate_payment_method(method)
            assert result is False

    def test_should_return_true_when_validate_payment_method_with_case_insensitive(
        self, payment_service
    ):
        result = payment_service.validate_payment_method("CREDIT_CARD")
        assert result is True
        
        result = payment_service.validate_payment_method("PayPal")
        assert result is True

    @pytest.mark.asyncio
    async def test_should_return_success_when_process_single_item_with_valid_data(
        self, payment_service, mock_db_session, sample_product
    ):
        with patch("crud.product.get_active", new_callable=AsyncMock) as mock_get_active:
            mock_get_active.return_value = sample_product
            
            with patch.object(payment_service.inventory_service, "check_stock_availability", new_callable=AsyncMock) as mock_check:
                mock_check.return_value = True
                
                with patch.object(payment_service.inventory_service, "deduct_inventory", new_callable=AsyncMock) as mock_deduct:
                    mock_deduct.return_value = True
                    
                    with patch("crud.product.update", new_callable=AsyncMock) as mock_update:
                        mock_update.return_value = sample_product
                        
                        result = await payment_service.process_single_item(1, 2)
                        
                        assert result["success"] is True
                        assert result["item"]["product_id"] == 1
                        assert result["item"]["quantity"] == 2
                        assert result["amount"] == Decimal("21.98")  # 10.99 * 2
                        mock_get_active.assert_called_once_with(mock_db_session, id=1)
                        mock_check.assert_called_once_with(1, 2)
                        mock_deduct.assert_called_once_with(1, 2)

    @pytest.mark.asyncio
    async def test_should_return_failure_when_process_single_item_with_inactive_product(
        self, payment_service, mock_db_session
    ):
        with patch("crud.product.get_active", new_callable=AsyncMock) as mock_get_active:
            mock_get_active.return_value = None
            
            result = await payment_service.process_single_item(999, 2)
            
            assert result["success"] is False
            assert result["reason"] == "Product not found or inactive"
            mock_get_active.assert_called_once_with(mock_db_session, id=999)

    @pytest.mark.asyncio
    async def test_should_return_failure_when_process_single_item_with_insufficient_stock(
        self, payment_service, mock_db_session, sample_product
    ):
        with patch("crud.product.get_active", new_callable=AsyncMock) as mock_get_active:
            mock_get_active.return_value = sample_product
            
            with patch.object(payment_service.inventory_service, "check_stock_availability", new_callable=AsyncMock) as mock_check:
                mock_check.return_value = False
                
                result = await payment_service.process_single_item(1, 20)
                
                assert result["success"] is False
                assert result["reason"] == "Insufficient stock"
                mock_check.assert_called_once_with(1, 20)

    @pytest.mark.asyncio
    async def test_should_return_failure_when_process_single_item_with_deduction_failure(
        self, payment_service, mock_db_session, sample_product
    ):
        with patch("crud.product.get_active", new_callable=AsyncMock) as mock_get_active:
            mock_get_active.return_value = sample_product
            
            with patch.object(payment_service.inventory_service, "check_stock_availability", new_callable=AsyncMock) as mock_check:
                mock_check.return_value = True
                
                with patch.object(payment_service.inventory_service, "deduct_inventory", new_callable=AsyncMock) as mock_deduct:
                    mock_deduct.return_value = False
                    
                    result = await payment_service.process_single_item(1, 2)
                    
                    assert result["success"] is False
                    assert result["reason"] == "Failed to deduct inventory"
                    mock_deduct.assert_called_once_with(1, 2)

    @pytest.mark.asyncio
    async def test_should_process_items_when_process_payment_with_mixed_results(
        self, payment_service, mock_db_session, sample_product
    ):
        items = [
            {"product_id": 1, "quantity": 2},
            {"product_id": 999, "quantity": 1},
            {"product_id": 1, "quantity": 0},
        ]
        
        with patch.object(payment_service, "process_single_item", new_callable=AsyncMock) as mock_process:
            mock_process.side_effect = [
                {"success": True, "item": {"product_id": 1, "quantity": 2, "price_per_unit": 10.99}, "amount": Decimal("21.98")},
                {"success": False, "reason": "Product not found"},
                {"success": False, "reason": "Invalid quantity"},
            ]
            
            successful, failed, total = await payment_service.process_payment(1, items)
            
            assert len(successful) == 1
            assert len(failed) == 2
            assert total == Decimal("21.98")

    @pytest.mark.asyncio
    async def test_should_return_empty_when_process_payment_with_empty_items(
        self, payment_service, mock_db_session
    ):
        successful, failed, total = await payment_service.process_payment(1, [])
        
        assert successful == []
        assert failed == []
        assert total == Decimal(0)

    @pytest.mark.asyncio
    async def test_should_create_sale_record_when_create_sale_record_with_valid_data(
        self, payment_service, mock_db_session
    ):
        successful_purchases = [
            {"product_id": 1, "quantity": 2, "price_per_unit": 10.99},
            {"product_id": 2, "quantity": 1, "price_per_unit": 29.99},
        ]
        
        with patch("crud.sale.create", new_callable=AsyncMock) as mock_create_sale:
            mock_sale = Mock()
            mock_sale.id = 1
            mock_sale.to_dict.return_value = {"id": 1, "user_id": 1, "total_amount": 51.97}
            mock_create_sale.return_value = mock_sale
            
            with patch("crud.sale_item.create", new_callable=AsyncMock) as mock_create_item:
                mock_item = Mock()
                mock_item.to_dict.return_value = {"id": 1, "sale_id": 1}
                mock_create_item.return_value = mock_item
                
                result = await payment_service.create_sale_record(1, successful_purchases, Decimal("51.97"))
                
                assert "sale" in result
                assert "sale_items" in result
                assert len(result["sale_items"]) == 2
                mock_create_sale.assert_called_once()
                assert mock_create_item.call_count == 2

    @pytest.mark.asyncio
    async def test_should_return_true_when_refund_payment_with_valid_sale_id(
        self, payment_service, mock_db_session
    ):
        mock_sale = Mock()
        mock_sale.id = 1
        
        mock_sale_items = [
            Mock(product_id=1, quantity=2),
            Mock(product_id=2, quantity=1),
        ]
        
        mock_product = Mock(quantity=5)
        
        with patch("crud.sale.get", new_callable=AsyncMock) as mock_get_sale:
            mock_get_sale.return_value = mock_sale
            
            with patch("crud.sale_item.get_by_sale_id", new_callable=AsyncMock) as mock_get_items:
                mock_get_items.return_value = mock_sale_items
                
                with patch("crud.product.get", new_callable=AsyncMock) as mock_get_product:
                    mock_get_product.return_value = mock_product
                    
                    with patch.object(payment_service.inventory_service, "add_inventory", new_callable=AsyncMock) as mock_add:
                        mock_add.return_value = Mock()
                        
                        with patch("crud.product.update", new_callable=AsyncMock) as mock_update:
                            mock_update.return_value = mock_product
                            
                            result = await payment_service.refund_payment(1)
                            
                            assert result is True
                            mock_get_sale.assert_called_once_with(mock_db_session, id=1)
                            mock_get_items.assert_called_once_with(mock_db_session, sale_id=1)

    @pytest.mark.asyncio
    async def test_should_return_false_when_refund_payment_with_invalid_sale_id(
        self, payment_service, mock_db_session
    ):
        with patch("crud.sale.get", new_callable=AsyncMock) as mock_get_sale:
            mock_get_sale.return_value = None
            
            result = await payment_service.refund_payment(999)
            
            assert result is False
            mock_get_sale.assert_called_once_with(mock_db_session, id=999)
