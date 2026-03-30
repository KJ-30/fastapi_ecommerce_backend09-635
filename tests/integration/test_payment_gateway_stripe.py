from decimal import Decimal
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.payment import (
    PaymentService,
    PaymentResult,
    PaymentStatus,
    PaymentMethod,
    PaymentItem,
)
import crud


class TestPaymentServiceIntegrationStripe:
    @pytest.mark.asyncio
    async def test_should_process_stripe_payment_when_valid_data(
        self,
        db_session: AsyncSession,
        sample_user,
        sample_product,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=sample_product.id,
                quantity=2,
                price_per_unit=sample_product.price,
            )
        ]
        
        result = await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.STRIPE,
        )
        
        assert result.status == PaymentStatus.SUCCESS
        assert result.transaction_id is not None
        assert result.amount == sample_product.price * 2
    
    @pytest.mark.asyncio
    async def test_should_create_sale_record_when_stripe_payment_successful(
        self,
        db_session: AsyncSession,
        sample_user,
        sample_product,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=sample_product.id,
                quantity=1,
                price_per_unit=Decimal("50.00"),
            )
        ]
        
        await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.STRIPE,
        )
        
        sales = await crud.sale.get_multi(
            db_session,
            page=1,
            per_page=10,
            order_by="id",
            order="desc",
        )
        
        assert len(sales) >= 1
    
    @pytest.mark.asyncio
    async def test_should_create_sale_items_when_stripe_payment_successful(
        self,
        db_session: AsyncSession,
        sample_user,
        sample_product,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=sample_product.id,
                quantity=3,
                price_per_unit=Decimal("25.00"),
            )
        ]
        
        await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.STRIPE,
        )
        
        sale_items = await crud.sale_item.get_multi(
            db_session,
            page=1,
            per_page=10,
            order_by="id",
            order="desc",
        )
        
        assert len(sale_items) >= 1


class TestPaymentServiceIntegrationPaypal:
    @pytest.mark.asyncio
    async def test_should_process_paypal_payment_when_valid_data(
        self,
        db_session: AsyncSession,
        sample_user,
        sample_product,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=sample_product.id,
                quantity=1,
                price_per_unit=sample_product.price,
            )
        ]
        
        result = await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.PAYPAL,
        )
        
        assert result.status == PaymentStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_should_use_correct_currency_when_paypal_payment(
        self,
        db_session: AsyncSession,
        sample_user,
        sample_product,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=sample_product.id,
                quantity=1,
                price_per_unit=Decimal("100.00"),
            )
        ]
        
        result = await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.PAYPAL,
            currency="EUR",
        )
        
        assert result.currency == "EUR"


class TestPaymentServiceIntegrationCreditCard:
    @pytest.mark.asyncio
    async def test_should_process_credit_card_payment_when_valid_data(
        self,
        db_session: AsyncSession,
        sample_user,
        sample_product,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=sample_product.id,
                quantity=1,
                price_per_unit=Decimal("75.00"),
            )
        ]
        
        result = await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.CREDIT_CARD,
        )
        
        assert result.status == PaymentStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_should_calculate_correct_total_when_multiple_items(
        self,
        db_session: AsyncSession,
        sample_user,
        sample_product,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=sample_product.id,
                quantity=2,
                price_per_unit=Decimal("50.00"),
            ),
            PaymentItem(
                product_id=sample_product.id,
                quantity=1,
                price_per_unit=Decimal("25.00"),
            )
        ]
        
        result = await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.CREDIT_CARD,
        )
        
        assert result.amount == Decimal("125.00")


class TestPaymentServiceIntegrationCash:
    @pytest.mark.asyncio
    async def test_should_process_cash_payment_when_valid_data(
        self,
        db_session: AsyncSession,
        sample_user,
        sample_product,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=sample_product.id,
                quantity=1,
                price_per_unit=Decimal("30.00"),
            )
        ]
        
        result = await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.CASH,
        )
        
        assert result.status == PaymentStatus.SUCCESS


class TestPaymentServiceIntegrationRefund:
    @pytest.mark.asyncio
    async def test_should_refund_payment_when_valid_transaction_id(
        self,
        db_session: AsyncSession,
        sample_user,
        sample_product,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=sample_product.id,
                quantity=1,
                price_per_unit=Decimal("50.00"),
            )
        ]
        
        payment_result = await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.CREDIT_CARD,
        )
        
        refund_result = await service.refund_payment(
            transaction_id=payment_result.transaction_id
        )
        
        assert refund_result.status == PaymentStatus.REFUNDED
        assert refund_result.transaction_id == payment_result.transaction_id
    
    @pytest.mark.asyncio
    async def test_should_refund_partial_amount_when_specified(
        self,
        db_session: AsyncSession,
        sample_user,
        sample_product,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=sample_product.id,
                quantity=2,
                price_per_unit=Decimal("50.00"),
            )
        ]
        
        payment_result = await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.CREDIT_CARD,
        )
        
        refund_result = await service.refund_payment(
            transaction_id=payment_result.transaction_id,
            amount=Decimal("50.00"),
        )
        
        assert refund_result.status == PaymentStatus.REFUNDED
        assert refund_result.amount == Decimal("50.00")


class TestPaymentServiceIntegrationValidation:
    @pytest.mark.asyncio
    async def test_should_fail_when_items_empty(
        self,
        db_session: AsyncSession,
        sample_user,
    ):
        service = PaymentService(db_session)
        
        result = await service.process_payment(
            user_id=sample_user.id,
            items=[],
            payment_method=PaymentMethod.CREDIT_CARD,
        )
        
        assert result.status == PaymentStatus.FAILED
        assert "No items to process" in result.error_message
    
    @pytest.mark.asyncio
    async def test_should_fail_when_total_amount_zero(
        self,
        db_session: AsyncSession,
        sample_user,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=1,
                quantity=0,
                price_per_unit=Decimal("0.00"),
            )
        ]
        
        result = await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.CREDIT_CARD,
        )
        
        assert result.status == PaymentStatus.FAILED


class TestPaymentServiceIntegrationCalculateTotal:
    @pytest.mark.asyncio
    async def test_should_calculate_total_with_tax(
        self,
        db_session: AsyncSession,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=1,
                quantity=1,
                price_per_unit=Decimal("100.00"),
            )
        ]
        
        total = service.calculate_total(
            items,
            tax_rate=Decimal("0.08"),
        )
        
        assert total == Decimal("108.00")
    
    @pytest.mark.asyncio
    async def test_should_calculate_total_with_discount(
        self,
        db_session: AsyncSession,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=1,
                quantity=1,
                price_per_unit=Decimal("100.00"),
            )
        ]
        
        total = service.calculate_total(
            items,
            discount_rate=Decimal("0.10"),
        )
        
        assert total == Decimal("90.00")
    
    @pytest.mark.asyncio
    async def test_should_calculate_total_with_tax_and_discount(
        self,
        db_session: AsyncSession,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=1,
                quantity=2,
                price_per_unit=Decimal("50.00"),
            )
        ]
        
        total = service.calculate_total(
            items,
            tax_rate=Decimal("0.10"),
            discount_rate=Decimal("0.05"),
        )
        
        assert total == Decimal("105.00")


class TestPaymentServiceIntegrationValidateAmount:
    @pytest.mark.asyncio
    async def test_should_validate_amount_within_range(
        self,
        db_session: AsyncSession,
    ):
        service = PaymentService(db_session)
        
        is_valid = service.validate_payment_amount(Decimal("500.00"))
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_should_reject_amount_below_minimum(
        self,
        db_session: AsyncSession,
    ):
        service = PaymentService(db_session)
        
        is_valid = service.validate_payment_amount(Decimal("0.001"))
        
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_should_reject_amount_above_maximum(
        self,
        db_session: AsyncSession,
    ):
        service = PaymentService(db_session)
        
        is_valid = service.validate_payment_amount(Decimal("5000000.00"))
        
        assert is_valid is False


class TestPaymentServiceIntegrationMultiplePayments:
    @pytest.mark.asyncio
    async def test_should_generate_unique_transaction_ids(
        self,
        db_session: AsyncSession,
        sample_user,
        sample_product,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=sample_product.id,
                quantity=1,
                price_per_unit=Decimal("50.00"),
            )
        ]
        
        result1 = await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.CREDIT_CARD,
        )
        
        result2 = await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.CREDIT_CARD,
        )
        
        assert result1.transaction_id != result2.transaction_id
    
    @pytest.mark.asyncio
    async def test_should_create_multiple_sale_records(
        self,
        db_session: AsyncSession,
        sample_user,
        sample_product,
    ):
        service = PaymentService(db_session)
        
        items = [
            PaymentItem(
                product_id=sample_product.id,
                quantity=1,
                price_per_unit=Decimal("50.00"),
            )
        ]
        
        await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.CREDIT_CARD,
        )
        
        await service.process_payment(
            user_id=sample_user.id,
            items=items,
            payment_method=PaymentMethod.STRIPE,
        )
        
        sales = await crud.sale.get_multi(
            db_session,
            page=1,
            per_page=10,
            order_by="id",
            order="desc",
        )
        
        assert len(sales) >= 2
