from enum import Enum
from decimal import Decimal
from typing import Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime

import crud
from sqlalchemy.ext.asyncio import AsyncSession
from models.inventory import Inventory
from models.product import Product


class InventoryStatus(str, Enum):
    AVAILABLE = "available"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    OVERSTOCKED = "overstocked"


@dataclass
class InventoryResult:
    success: bool
    status: InventoryStatus
    product_id: int
    available_quantity: int
    message: Optional[str] = None
    modified_inventories: Optional[List[Inventory]] = None


@dataclass
class InventoryCheck:
    product_id: int
    requested_quantity: int
    available_quantity: int
    is_available: bool


class InventoryService:
    LOW_STOCK_THRESHOLD = 10
    OVERSTOCK_THRESHOLD = 1000

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_availability(
        self,
        product_id: int,
        requested_quantity: int,
    ) -> InventoryCheck:
        if requested_quantity <= 0:
            return InventoryCheck(
                product_id=product_id,
                requested_quantity=requested_quantity,
                available_quantity=0,
                is_available=False,
            )

        inventories = await crud.inventory.get_by_product_id(
            self.db, product_id=product_id
        )

        if not inventories:
            return InventoryCheck(
                product_id=product_id,
                requested_quantity=requested_quantity,
                available_quantity=0,
                is_available=False,
            )

        total_quantity = sum(inv.quantity for inv in inventories)

        return InventoryCheck(
            product_id=product_id,
            requested_quantity=requested_quantity,
            available_quantity=total_quantity,
            is_available=total_quantity >= requested_quantity,
        )

    async def check_multiple_availability(
        self,
        items: List[Tuple[int, int]],
    ) -> List[InventoryCheck]:
        results = []
        for product_id, quantity in items:
            check = await self.check_availability(product_id, quantity)
            results.append(check)
        return results

    async def reserve_inventory(
        self,
        product_id: int,
        quantity: int,
    ) -> InventoryResult:
        if quantity <= 0:
            return InventoryResult(
                success=False,
                status=InventoryStatus.OUT_OF_STOCK,
                product_id=product_id,
                available_quantity=0,
                message="Quantity must be greater than zero",
            )

        availability = await self.check_availability(product_id, quantity)

        if not availability.is_available:
            return InventoryResult(
                success=False,
                status=InventoryStatus.OUT_OF_STOCK,
                product_id=product_id,
                available_quantity=availability.available_quantity,
                message=f"Insufficient inventory. Available: {availability.available_quantity}, Requested: {quantity}",
            )

        inventories = await crud.inventory.get_by_product_id(
            self.db, product_id=product_id
        )

        if not inventories:
            return InventoryResult(
                success=False,
                status=InventoryStatus.OUT_OF_STOCK,
                product_id=product_id,
                available_quantity=0,
                message="No inventory records found",
            )

        sorted_inventories = sorted(inventories, key=lambda x: x.created_at)

        modified_inventories = []
        remaining_quantity = quantity

        for inventory in sorted_inventories:
            if remaining_quantity <= 0:
                break

            if inventory.quantity >= remaining_quantity:
                inventory.quantity -= remaining_quantity
                remaining_quantity = 0
                modified_inventories.append(inventory)
            else:
                remaining_quantity -= inventory.quantity
                inventory.quantity = 0
                modified_inventories.append(inventory)

        if modified_inventories:
            await crud.inventory.bulk_update(self.db, db_objs=modified_inventories)

        product = await crud.product.get(self.db, id=product_id)
        if product:
            new_quantity = product.quantity - quantity
            await crud.product.update(
                self.db,
                db_obj=product,
                obj_in={"quantity": new_quantity},
            )

        final_status = self._determine_status(availability.available_quantity - quantity)

        return InventoryResult(
            success=True,
            status=final_status,
            product_id=product_id,
            available_quantity=availability.available_quantity - quantity,
            message="Inventory reserved successfully",
            modified_inventories=modified_inventories,
        )

    async def release_inventory(
        self,
        product_id: int,
        quantity: int,
    ) -> InventoryResult:
        if quantity <= 0:
            return InventoryResult(
                success=False,
                status=InventoryStatus.AVAILABLE,
                product_id=product_id,
                available_quantity=0,
                message="Quantity must be greater than zero",
            )

        inventories = await crud.inventory.get_by_product_id(
            self.db, product_id=product_id
        )

        if not inventories:
            return InventoryResult(
                success=False,
                status=InventoryStatus.OUT_OF_STOCK,
                product_id=product_id,
                available_quantity=0,
                message="No inventory records found",
            )

        latest_inventory = max(inventories, key=lambda x: x.created_at)
        latest_inventory.quantity += quantity

        await crud.inventory.bulk_update(self.db, db_objs=[latest_inventory])

        product = await crud.product.get(self.db, id=product_id)
        if product:
            new_quantity = product.quantity + quantity
            await crud.product.update(
                self.db,
                db_obj=product,
                obj_in={"quantity": new_quantity},
            )

        total_quantity = sum(inv.quantity for inv in inventories)
        final_status = self._determine_status(total_quantity)

        return InventoryResult(
            success=True,
            status=final_status,
            product_id=product_id,
            available_quantity=total_quantity,
            message="Inventory released successfully",
        )

    async def add_inventory(
        self,
        product_id: int,
        quantity: int,
    ) -> InventoryResult:
        if quantity <= 0:
            return InventoryResult(
                success=False,
                status=InventoryStatus.OUT_OF_STOCK,
                product_id=product_id,
                available_quantity=0,
                message="Quantity must be greater than zero",
            )

        product = await crud.product.get(self.db, id=product_id)
        if not product:
            return InventoryResult(
                success=False,
                status=InventoryStatus.OUT_OF_STOCK,
                product_id=product_id,
                available_quantity=0,
                message="Product not found",
            )

        from crud.schemas import InventoryCreate
        inventory_create = InventoryCreate(
            product_id=product_id,
            quantity=quantity,
        )
        await crud.inventory.create(self.db, obj_in=inventory_create)

        new_product_quantity = product.quantity + quantity
        await crud.product.update(
            self.db,
            db_obj=product,
            obj_in={"quantity": new_product_quantity},
        )

        inventories = await crud.inventory.get_by_product_id(
            self.db, product_id=product_id
        )
        total_quantity = sum(inv.quantity for inv in inventories) if inventories else 0
        final_status = self._determine_status(total_quantity)

        return InventoryResult(
            success=True,
            status=final_status,
            product_id=product_id,
            available_quantity=total_quantity,
            message="Inventory added successfully",
        )

    async def get_inventory_status(
        self,
        product_id: int,
    ) -> InventoryResult:
        inventories = await crud.inventory.get_by_product_id(
            self.db, product_id=product_id
        )

        if not inventories:
            return InventoryResult(
                success=False,
                status=InventoryStatus.OUT_OF_STOCK,
                product_id=product_id,
                available_quantity=0,
                message="No inventory found for product",
            )

        total_quantity = sum(inv.quantity for inv in inventories)
        status = self._determine_status(total_quantity)

        return InventoryResult(
            success=True,
            status=status,
            product_id=product_id,
            available_quantity=total_quantity,
            message=f"Inventory status: {status.value}",
        )

    async def get_low_stock_products(
        self,
        threshold: Optional[int] = None,
    ) -> List[Tuple[int, int, InventoryStatus]]:
        if threshold is None:
            threshold = self.LOW_STOCK_THRESHOLD

        products = await crud.product.get_products_quantity_le(
            self.db, quantity=threshold
        )

        results = []
        for product in products:
            status = self._determine_status(product.quantity)
            results.append((product.id, product.quantity, status))

        return results

    def _determine_status(self, quantity: int) -> InventoryStatus:
        if quantity <= 0:
            return InventoryStatus.OUT_OF_STOCK
        elif quantity <= self.LOW_STOCK_THRESHOLD:
            return InventoryStatus.LOW_STOCK
        elif quantity > self.OVERSTOCK_THRESHOLD:
            return InventoryStatus.OVERSTOCKED
        else:
            return InventoryStatus.AVAILABLE

    async def transfer_inventory(
        self,
        from_product_id: int,
        to_product_id: int,
        quantity: int,
    ) -> Tuple[InventoryResult, InventoryResult]:
        if quantity <= 0:
            return (
                InventoryResult(
                    success=False,
                    status=InventoryStatus.OUT_OF_STOCK,
                    product_id=from_product_id,
                    available_quantity=0,
                    message="Quantity must be greater than zero",
                ),
                InventoryResult(
                    success=False,
                    status=InventoryStatus.OUT_OF_STOCK,
                    product_id=to_product_id,
                    available_quantity=0,
                    message="Quantity must be greater than zero",
                ),
            )

        release_result = await self.reserve_inventory(from_product_id, quantity)

        if not release_result.success:
            return (
                release_result,
                InventoryResult(
                    success=False,
                    status=InventoryStatus.OUT_OF_STOCK,
                    product_id=to_product_id,
                    available_quantity=0,
                    message="Source product does not have enough inventory",
                ),
            )

        add_result = await self.add_inventory(to_product_id, quantity)

        return (release_result, add_result)

    async def bulk_reserve(
        self,
        items: List[Tuple[int, int]],
    ) -> List[InventoryResult]:
        results = []
        for product_id, quantity in items:
            result = await self.reserve_inventory(product_id, quantity)
            results.append(result)
        return results
