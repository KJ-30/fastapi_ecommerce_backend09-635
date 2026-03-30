from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.payment import (
    PaymentService,
    PaymentResult,
    PaymentStatus,
    PaymentMethod,
    PaymentItem,
)


class TestPaymentServiceInit:
    def test_should_initialize_payment_service_when_created(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        assert service.db == mock_db
        assert service._transaction_counter == 0


class TestGenerateTransactionId:
    def test_should_generate_unique_transaction_id_when_called(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        txn_id_1 = service._generate_transaction_id()
        txn_id_2 = service._generate_transaction_id()
        
        assert txn_id_1 != txn_id_2
        assert txn_id_1.startswith("TXN-")
        assert txn_id_2.startswith("TXN-")
    
    def test_should_increment_counter_when_generating_multiple_ids(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        id1 = service._generate_transaction_id()
        id2 = service._generate_transaction_id()
        id3 = service._generate_transaction_id()
        
        assert service._transaction_counter == 3


class TestProcessPayment:
    @pytest.mark.asyncio
    async def test_should_return_failed_when_items_empty(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = await service.process_payment(
            user_id=1,
            items=[],
            payment_method=PaymentMethod.CREDIT_CARD,
        )
        
        assert result.status == PaymentStatus.FAILED
        assert result.error_message == "No items to process"
    
    @pytest.mark.asyncio
    async def test_should_return_failed_when_total_amount_zero(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=0, price_per_unit=Decimal("0.00")),
        ]
        
        result = await service.process_payment(
            user_id=1,
            items=items,
            payment_method=PaymentMethod.CREDIT_CARD,
        )
        
        assert result.status == PaymentStatus.FAILED
        assert result.error_message == "Total amount must be greater than zero"
    
    @pytest.mark.asyncio
    async def test_should_return_failed_when_total_amount_negative(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=-1, price_per_unit=Decimal("10.00")),
        ]
        
        result = await service.process_payment(
            user_id=1,
            items=items,
            payment_method=PaymentMethod.CREDIT_CARD,
        )
        
        assert result.status == PaymentStatus.FAILED
        assert result.error_message == "Total amount must be greater than zero"
    
    @pytest.mark.asyncio
    async def test_should_process_stripe_payment_when_method_is_stripe(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=2, price_per_unit=Decimal("50.00")),
        ]
        
        with patch.object(service, '_process_stripe_payment') as mock_stripe:
            mock_stripe.return_value = PaymentResult(
                status=PaymentStatus.SUCCESS,
                transaction_id="TXN-123",
                amount=Decimal("100.00"),
            )
            
            result = await service.process_payment(
                user_id=1,
                items=items,
                payment_method=PaymentMethod.STRIPE,
            )
            
            mock_stripe.assert_called_once()
            assert result.status == PaymentStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_should_process_paypal_payment_when_method_is_paypal(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=1, price_per_unit=Decimal("100.00")),
        ]
        
        with patch.object(service, '_process_paypal_payment') as mock_paypal:
            mock_paypal.return_value = PaymentResult(
                status=PaymentStatus.SUCCESS,
                transaction_id="TXN-456",
                amount=Decimal("100.00"),
            )
            
            result = await service.process_payment(
                user_id=1,
                items=items,
                payment_method=PaymentMethod.PAYPAL,
            )
            
            mock_paypal.assert_called_once()
            assert result.status == PaymentStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_should_process_credit_card_payment_when_method_is_credit_card(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=1, price_per_unit=Decimal("75.00")),
        ]
        
        with patch.object(service, '_process_credit_card_payment') as mock_cc:
            mock_cc.return_value = PaymentResult(
                status=PaymentStatus.SUCCESS,
                transaction_id="TXN-789",
                amount=Decimal("75.00"),
            )
            
            result = await service.process_payment(
                user_id=1,
                items=items,
                payment_method=PaymentMethod.CREDIT_CARD,
            )
            
            mock_cc.assert_called_once()
            assert result.status == PaymentStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_should_process_cash_payment_when_method_is_cash(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=1, price_per_unit=Decimal("50.00")),
        ]
        
        with patch.object(service, '_process_cash_payment') as mock_cash:
            mock_cash.return_value = PaymentResult(
                status=PaymentStatus.SUCCESS,
                transaction_id="TXN-CASH",
                amount=Decimal("50.00"),
            )
            
            result = await service.process_payment(
                user_id=1,
                items=items,
                payment_method=PaymentMethod.CASH,
            )
            
            mock_cash.assert_called_once()
            assert result.status == PaymentStatus.SUCCESS


class TestProcessStripePayment:
    @pytest.mark.asyncio
    async def test_should_return_failed_when_quantity_is_zero(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=0, price_per_unit=Decimal("100.00")),
        ]
        
        result = await service._process_stripe_payment(
            user_id=1,
            items=items,
            total_amount=Decimal("0.00"),
            currency="USD",
        )
        
        assert result.status == PaymentStatus.FAILED
        assert "Invalid quantity" in result.error_message
    
    @pytest.mark.asyncio
    async def test_should_return_failed_when_quantity_is_negative(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=-5, price_per_unit=Decimal("100.00")),
        ]
        
        result = await service._process_stripe_payment(
            user_id=1,
            items=items,
            total_amount=Decimal("-500.00"),
            currency="USD",
        )
        
        assert result.status == PaymentStatus.FAILED
        assert "Invalid quantity" in result.error_message
    
    @pytest.mark.asyncio
    async def test_should_return_success_when_valid_items_provided(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=2, price_per_unit=Decimal("50.00")),
        ]
        
        with patch('app.services.payment.crud') as mock_crud:
            mock_sale = MagicMock()
            mock_sale.id = 1
            mock_crud.sale.create = AsyncMock(return_value=mock_sale)
            mock_crud.sale_item.bulk_create = AsyncMock(return_value=[])
            
            result = await service._process_stripe_payment(
                user_id=1,
                items=items,
                total_amount=Decimal("100.00"),
                currency="USD",
            )
            
            assert result.status == PaymentStatus.SUCCESS
            assert result.transaction_id is not None
            assert result.amount == Decimal("100.00")


class TestProcessPaypalPayment:
    @pytest.mark.asyncio
    async def test_should_return_failed_when_quantity_invalid(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=0, price_per_unit=Decimal("100.00")),
        ]
        
        result = await service._process_paypal_payment(
            user_id=1,
            items=items,
            total_amount=Decimal("0.00"),
            currency="USD",
        )
        
        assert result.status == PaymentStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_should_return_success_when_valid_items_provided(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=1, price_per_unit=Decimal("100.00")),
        ]
        
        with patch('app.services.payment.crud') as mock_crud:
            mock_sale = MagicMock()
            mock_sale.id = 1
            mock_crud.sale.create = AsyncMock(return_value=mock_sale)
            mock_crud.sale_item.bulk_create = AsyncMock(return_value=[])
            
            result = await service._process_paypal_payment(
                user_id=1,
                items=items,
                total_amount=Decimal("100.00"),
                currency="EUR",
            )
            
            assert result.status == PaymentStatus.SUCCESS
            assert result.currency == "EUR"


class TestProcessCreditCardPayment:
    @pytest.mark.asyncio
    async def test_should_return_failed_when_quantity_invalid(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=-1, price_per_unit=Decimal("100.00")),
        ]
        
        result = await service._process_credit_card_payment(
            user_id=1,
            items=items,
            total_amount=Decimal("-100.00"),
            currency="USD",
        )
        
        assert result.status == PaymentStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_should_return_success_when_valid_items_provided(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=3, price_per_unit=Decimal("33.33")),
        ]
        
        with patch('app.services.payment.crud') as mock_crud:
            mock_sale = MagicMock()
            mock_sale.id = 1
            mock_crud.sale.create = AsyncMock(return_value=mock_sale)
            mock_crud.sale_item.bulk_create = AsyncMock(return_value=[])
            
            result = await service._process_credit_card_payment(
                user_id=1,
                items=items,
                total_amount=Decimal("99.99"),
                currency="USD",
            )
            
            assert result.status == PaymentStatus.SUCCESS


class TestProcessCashPayment:
    @pytest.mark.asyncio
    async def test_should_return_failed_when_quantity_invalid(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=0, price_per_unit=Decimal("100.00")),
        ]
        
        result = await service._process_cash_payment(
            user_id=1,
            items=items,
            total_amount=Decimal("0.00"),
            currency="USD",
        )
        
        assert result.status == PaymentStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_should_return_success_when_valid_items_provided(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=1, price_per_unit=Decimal("25.00")),
        ]
        
        with patch('app.services.payment.crud') as mock_crud:
            mock_sale = MagicMock()
            mock_sale.id = 1
            mock_crud.sale.create = AsyncMock(return_value=mock_sale)
            mock_crud.sale_item.bulk_create = AsyncMock(return_value=[])
            
            result = await service._process_cash_payment(
                user_id=1,
                items=items,
                total_amount=Decimal("25.00"),
                currency="USD",
            )
            
            assert result.status == PaymentStatus.SUCCESS


class TestRefundPayment:
    @pytest.mark.asyncio
    async def test_should_return_failed_when_transaction_id_is_none(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = await service.refund_payment(transaction_id=None)
        
        assert result.status == PaymentStatus.FAILED
        assert "Transaction ID is required" in result.error_message
    
    @pytest.mark.asyncio
    async def test_should_return_failed_when_transaction_id_is_empty(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = await service.refund_payment(transaction_id="")
        
        assert result.status == PaymentStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_should_return_refunded_when_valid_transaction_id(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = await service.refund_payment(transaction_id="TXN-123456")
        
        assert result.status == PaymentStatus.REFUNDED
        assert result.transaction_id == "TXN-123456"
    
    @pytest.mark.asyncio
    async def test_should_refund_partial_amount_when_amount_specified(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = await service.refund_payment(
            transaction_id="TXN-123456",
            amount=Decimal("50.00"),
        )
        
        assert result.status == PaymentStatus.REFUNDED
        assert result.amount == Decimal("50.00")


class TestGetPaymentStatus:
    @pytest.mark.asyncio
    async def test_should_return_none_when_transaction_id_is_none(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = await service.get_payment_status(transaction_id=None)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_should_return_none_when_transaction_id_is_empty(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = await service.get_payment_status(transaction_id="")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_should_return_success_when_valid_transaction_id(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = await service.get_payment_status(transaction_id="TXN-123456")
        
        assert result == PaymentStatus.SUCCESS


class TestValidatePaymentAmount:
    def test_should_return_false_when_amount_below_minimum(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = service.validate_payment_amount(Decimal("0.001"))
        
        assert result is False
    
    def test_should_return_false_when_amount_above_maximum(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = service.validate_payment_amount(Decimal("2000000.00"))
        
        assert result is False
    
    def test_should_return_true_when_amount_within_range(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = service.validate_payment_amount(Decimal("100.00"))
        
        assert result is True
    
    def test_should_return_true_when_amount_equals_minimum(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = service.validate_payment_amount(Decimal("0.01"))
        
        assert result is True
    
    def test_should_return_true_when_amount_equals_maximum(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = service.validate_payment_amount(Decimal("1000000.00"))
        
        assert result is True
    
    def test_should_use_custom_min_max_when_provided(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = service.validate_payment_amount(
            Decimal("5.00"),
            min_amount=Decimal("1.00"),
            max_amount=Decimal("10.00"),
        )
        
        assert result is True
    
    def test_should_return_false_when_custom_min_exceeded(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = service.validate_payment_amount(
            Decimal("0.50"),
            min_amount=Decimal("1.00"),
        )
        
        assert result is False


class TestCalculateTotal:
    def test_should_calculate_subtotal_when_no_tax_or_discount(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=2, price_per_unit=Decimal("50.00")),
            PaymentItem(product_id=2, quantity=1, price_per_unit=Decimal("100.00")),
        ]
        
        result = service.calculate_total(items)
        
        assert result == Decimal("200.00")
    
    def test_should_calculate_total_with_tax_when_tax_rate_provided(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=1, price_per_unit=Decimal("100.00")),
        ]
        
        result = service.calculate_total(items, tax_rate=Decimal("0.10"))
        
        assert result == Decimal("110.00")
    
    def test_should_calculate_total_with_discount_when_discount_rate_provided(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=1, price_per_unit=Decimal("100.00")),
        ]
        
        result = service.calculate_total(items, discount_rate=Decimal("0.20"))
        
        assert result == Decimal("80.00")
    
    def test_should_calculate_total_with_tax_and_discount(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=1, price_per_unit=Decimal("100.00")),
        ]
        
        result = service.calculate_total(
            items,
            tax_rate=Decimal("0.10"),
            discount_rate=Decimal("0.10"),
        )
        
        assert result == Decimal("100.00")
    
    def test_should_return_zero_when_items_empty(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        result = service.calculate_total([])
        
        assert result == Decimal("0.00")
    
    def test_should_round_to_two_decimal_places(self):
        mock_db = MagicMock()
        service = PaymentService(mock_db)
        
        items = [
            PaymentItem(product_id=1, quantity=3, price_per_unit=Decimal("33.33")),
        ]
        
        result = service.calculate_total(items)
        
        assert result == Decimal("99.99")


class TestPaymentResult:
    def test_should_create_payment_result_with_defaults(self):
        result = PaymentResult(status=PaymentStatus.SUCCESS)
        
        assert result.status == PaymentStatus.SUCCESS
        assert result.transaction_id is None
        assert result.amount is None
        assert result.currency == "USD"
        assert result.error_message is None
        assert result.created_at is None
    
    def test_should_create_payment_result_with_all_fields(self):
        now = datetime.utcnow()
        result = PaymentResult(
            status=PaymentStatus.SUCCESS,
            transaction_id="TXN-123",
            amount=Decimal("100.00"),
            currency="EUR",
            created_at=now,
        )
        
        assert result.status == PaymentStatus.SUCCESS
        assert result.transaction_id == "TXN-123"
        assert result.amount == Decimal("100.00")
        assert result.currency == "EUR"
        assert result.created_at == now


class TestPaymentItem:
    def test_should_create_payment_item(self):
        item = PaymentItem(
            product_id=1,
            quantity=5,
            price_per_unit=Decimal("19.99"),
        )
        
        assert item.product_id == 1
        assert item.quantity == 5
        assert item.price_per_unit == Decimal("19.99")


class TestPaymentStatusEnum:
    def test_should_have_correct_status_values(self):
        assert PaymentStatus.PENDING.value == "pending"
        assert PaymentStatus.SUCCESS.value == "success"
        assert PaymentStatus.FAILED.value == "failed"
        assert PaymentStatus.REFUNDED.value == "refunded"


class TestPaymentMethodEnum:
    def test_should_have_correct_method_values(self):
        assert PaymentMethod.STRIPE.value == "stripe"
        assert PaymentMethod.PAYPAL.value == "paypal"
        assert PaymentMethod.CREDIT_CARD.value == "credit_card"
        assert PaymentMethod.CASH.value == "cash"
