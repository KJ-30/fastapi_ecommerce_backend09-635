from enum import Enum
from decimal import Decimal
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime

import crud
from sqlalchemy.ext.asyncio import AsyncSession
from crud.schemas import SaleCreate, SaleItemCreate


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"
    CREDIT_CARD = "credit_card"
    CASH = "cash"


@dataclass
class PaymentResult:
    status: PaymentStatus
    transaction_id: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: str = "USD"
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class PaymentItem:
    product_id: int
    quantity: int
    price_per_unit: Decimal


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._transaction_counter = 0

    def _generate_transaction_id(self) -> str:
        self._transaction_counter += 1
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"TXN-{timestamp}-{self._transaction_counter:06d}"

    async def process_payment(
        self,
        user_id: int,
        items: List[PaymentItem],
        payment_method: PaymentMethod = PaymentMethod.CREDIT_CARD,
        currency: str = "USD",
    ) -> PaymentResult:
        if not items:
            return PaymentResult(
                status=PaymentStatus.FAILED,
                error_message="No items to process",
            )

        total_amount = sum(
            item.price_per_unit * item.quantity for item in items
        )

        if total_amount <= 0:
            return PaymentResult(
                status=PaymentStatus.FAILED,
                error_message="Total amount must be greater than zero",
            )

        if payment_method == PaymentMethod.STRIPE:
            return await self._process_stripe_payment(user_id, items, total_amount, currency)
        elif payment_method == PaymentMethod.PAYPAL:
            return await self._process_paypal_payment(user_id, items, total_amount, currency)
        elif payment_method == PaymentMethod.CREDIT_CARD:
            return await self._process_credit_card_payment(user_id, items, total_amount, currency)
        elif payment_method == PaymentMethod.CASH:
            return await self._process_cash_payment(user_id, items, total_amount, currency)
        else:
            return PaymentResult(
                status=PaymentStatus.FAILED,
                error_message=f"Unsupported payment method: {payment_method}",
            )

    async def _process_stripe_payment(
        self,
        user_id: int,
        items: List[PaymentItem],
        total_amount: Decimal,
        currency: str,
    ) -> PaymentResult:
        transaction_id = self._generate_transaction_id()

        for item in items:
            if item.quantity <= 0:
                return PaymentResult(
                    status=PaymentStatus.FAILED,
                    error_message=f"Invalid quantity for product {item.product_id}",
                )

        sale = await self._create_sale_record(user_id, items, total_amount)

        return PaymentResult(
            status=PaymentStatus.SUCCESS,
            transaction_id=transaction_id,
            amount=total_amount,
            currency=currency,
            created_at=datetime.utcnow(),
        )

    async def _process_paypal_payment(
        self,
        user_id: int,
        items: List[PaymentItem],
        total_amount: Decimal,
        currency: str,
    ) -> PaymentResult:
        transaction_id = self._generate_transaction_id()

        for item in items:
            if item.quantity <= 0:
                return PaymentResult(
                    status=PaymentStatus.FAILED,
                    error_message=f"Invalid quantity for product {item.product_id}",
                )

        sale = await self._create_sale_record(user_id, items, total_amount)

        return PaymentResult(
            status=PaymentStatus.SUCCESS,
            transaction_id=transaction_id,
            amount=total_amount,
            currency=currency,
            created_at=datetime.utcnow(),
        )

    async def _process_credit_card_payment(
        self,
        user_id: int,
        items: List[PaymentItem],
        total_amount: Decimal,
        currency: str,
    ) -> PaymentResult:
        transaction_id = self._generate_transaction_id()

        for item in items:
            if item.quantity <= 0:
                return PaymentResult(
                    status=PaymentStatus.FAILED,
                    error_message=f"Invalid quantity for product {item.product_id}",
                )

        sale = await self._create_sale_record(user_id, items, total_amount)

        return PaymentResult(
            status=PaymentStatus.SUCCESS,
            transaction_id=transaction_id,
            amount=total_amount,
            currency=currency,
            created_at=datetime.utcnow(),
        )

    async def _process_cash_payment(
        self,
        user_id: int,
        items: List[PaymentItem],
        total_amount: Decimal,
        currency: str,
    ) -> PaymentResult:
        transaction_id = self._generate_transaction_id()

        for item in items:
            if item.quantity <= 0:
                return PaymentResult(
                    status=PaymentStatus.FAILED,
                    error_message=f"Invalid quantity for product {item.product_id}",
                )

        sale = await self._create_sale_record(user_id, items, total_amount)

        return PaymentResult(
            status=PaymentStatus.SUCCESS,
            transaction_id=transaction_id,
            amount=total_amount,
            currency=currency,
            created_at=datetime.utcnow(),
        )

    async def _create_sale_record(
        self,
        user_id: int,
        items: List[PaymentItem],
        total_amount: Decimal,
    ) -> Optional[object]:
        sale_create = SaleCreate(
            user_id=user_id,
            total_amount=total_amount,
        )
        sale = await crud.sale.create(self.db, obj_in=sale_create)

        sale_items = []
        for item in items:
            sale_item = SaleItemCreate(
                sale_id=sale.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price_per_unit=item.price_per_unit,
            )
            sale_items.append(sale_item)

        if sale_items:
            await crud.sale_item.bulk_create(self.db, objs_in=sale_items)

        return sale

    async def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[Decimal] = None,
    ) -> PaymentResult:
        if not transaction_id:
            return PaymentResult(
                status=PaymentStatus.FAILED,
                error_message="Transaction ID is required for refund",
            )

        return PaymentResult(
            status=PaymentStatus.REFUNDED,
            transaction_id=transaction_id,
            amount=amount,
            created_at=datetime.utcnow(),
        )

    async def get_payment_status(self, transaction_id: str) -> Optional[PaymentStatus]:
        if not transaction_id:
            return None

        return PaymentStatus.SUCCESS

    def validate_payment_amount(
        self,
        amount: Decimal,
        min_amount: Decimal = Decimal("0.01"),
        max_amount: Decimal = Decimal("1000000.00"),
    ) -> bool:
        if amount < min_amount:
            return False
        if amount > max_amount:
            return False
        return True

    def calculate_total(
        self,
        items: List[PaymentItem],
        tax_rate: Decimal = Decimal("0.00"),
        discount_rate: Decimal = Decimal("0.00"),
    ) -> Decimal:
        subtotal = sum(item.price_per_unit * item.quantity for item in items)

        tax_amount = subtotal * tax_rate

        discount_amount = subtotal * discount_rate

        total = subtotal + tax_amount - discount_amount

        return total.quantize(Decimal("0.01"))
