from typing import Dict, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

import crud
from models.product import Product
from crud.schemas import SaleCreate, SaleItemCreate
from .inventory import InventoryService


class PaymentService:
    """
    Service class for payment and purchase business logic
    """
    
    PAYMENT_METHODS = ["credit_card", "debit_card", "paypal", "stripe"]
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.inventory_service = InventoryService(db)

    async def process_payment(self, user_id: int, items: List[Dict], payment_method: str = "credit_card") -> Tuple[List[Dict], List[Dict], Decimal]:
        """
        Process payment for a list of items
        
        Returns: (successful_purchases, failed_purchases, total_amount)
        """
        successful_purchases = []
        failed_purchases = []
        total_amount = Decimal(0)

        for item in items:
            product_id = item.get("product_id")
            quantity = item.get("quantity", 1)

            if not product_id or quantity <= 0:
                failed_purchases.append({**item, "reason": "Invalid product_id or quantity"})
                continue

            result = await self.process_single_item(product_id, quantity)
            if result["success"]:
                successful_purchases.append(result["item"])
                total_amount += result["amount"]
            else:
                failed_purchases.append({**item, "reason": result["reason"]})

        return successful_purchases, failed_purchases, total_amount

    async def process_single_item(self, product_id: int, quantity: int) -> Dict:
        """
        Process a single item for purchase
        
        Returns: dict with success status and item details
        """
        product = await crud.product.get_active(self.db, id=product_id)
        if not product:
            return {"success": False, "reason": "Product not found or inactive"}

        stock_available = await self.inventory_service.check_stock_availability(product_id, quantity)
        if not stock_available:
            return {"success": False, "reason": "Insufficient stock"}

        deduction_success = await self.inventory_service.deduct_inventory(product_id, quantity)
        if not deduction_success:
            return {"success": False, "reason": "Failed to deduct inventory"}

        await crud.product.update(
            self.db,
            db_obj=product,
            obj_in={"quantity": product.quantity - quantity},
        )

        item_amount = product.price * quantity
        return {
            "success": True,
            "item": {
                "product_id": product_id,
                "quantity": quantity,
                "price_per_unit": float(product.price),
                "product_name": product.product_name
            },
            "amount": item_amount
        }

    async def create_sale_record(self, user_id: int, successful_purchases: List[Dict], total_amount: Decimal) -> Dict:
        """
        Create sale record and sale items
        """
        sale_create = SaleCreate(user_id=user_id, total_amount=float(total_amount))
        sale = await crud.sale.create(self.db, obj_in=sale_create)

        sale_items = []
        for item in successful_purchases:
            sale_item_create = SaleItemCreate(
                sale_id=sale.id,
                product_id=item["product_id"],
                quantity=item["quantity"],
                price_per_unit=item["price_per_unit"],
            )
            sale_item = await crud.sale_item.create(self.db, obj_in=sale_item_create)
            sale_items.append(sale_item)

        return {
            "sale": sale.to_dict(),
            "sale_items": [item.to_dict() for item in sale_items]
        }

    def validate_payment_method(self, payment_method: str) -> bool:
        """
        Validate if payment method is supported
        """
        return payment_method.lower() in self.PAYMENT_METHODS

    async def refund_payment(self, sale_id: int) -> bool:
        """
        Process refund for a sale
        """
        sale = await crud.sale.get(self.db, id=sale_id)
        if not sale:
            return False

        sale_items = await crud.sale_item.get_by_sale_id(self.db, sale_id=sale_id)
        
        for item in sale_items:
            product = await crud.product.get(self.db, id=item.product_id)
            if product:
                await self.inventory_service.add_inventory(item.product_id, item.quantity)
                await crud.product.update(
                    self.db,
                    db_obj=product,
                    obj_in={"quantity": product.quantity + item.quantity},
                )

        return True
