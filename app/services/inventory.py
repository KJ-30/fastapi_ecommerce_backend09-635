from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

import crud
from models.inventory import Inventory
from models.product import Product
from crud.schemas import InventoryCreate, InventoryUpdate


class InventoryService:
    """
    Service class for inventory management business logic
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_inventory_by_product_id(self, product_id: int) -> List[Inventory]:
        """
        Get all inventory records for a product
        """
        return await crud.inventory.get_by_product_id(self.db, product_id=product_id)

    async def get_total_quantity(self, product_id: int) -> int:
        """
        Get total available quantity for a product
        """
        inventories = await self.get_inventory_by_product_id(product_id)
        return sum(inv.quantity for inv in inventories)

    async def check_stock_availability(self, product_id: int, requested_quantity: int) -> bool:
        """
        Check if requested quantity is available in stock
        """
        total_quantity = await self.get_total_quantity(product_id)
        return total_quantity >= requested_quantity

    async def add_inventory(self, product_id: int, quantity: int) -> Inventory:
        """
        Add inventory for a product
        """
        inventory_create = InventoryCreate(product_id=product_id, quantity=quantity)
        return await crud.inventory.create(self.db, obj_in=inventory_create)

    async def update_inventory(self, inventory_id: int, quantity: int) -> Optional[Inventory]:
        """
        Update inventory quantity
        """
        inventory = await crud.inventory.get(self.db, id=inventory_id)
        if not inventory:
            return None
        
        inventory_update = InventoryUpdate(quantity=quantity)
        return await crud.inventory.update(self.db, db_obj=inventory, obj_in=inventory_update)

    async def deduct_inventory(self, product_id: int, quantity: int) -> bool:
        """
        Deduct inventory for a product (FIFO method - oldest first)
        Returns True if successful, False if insufficient stock
        """
        inventories = await self.get_inventory_by_product_id(product_id)
        if not inventories:
            return False

        total_available = sum(inv.quantity for inv in inventories)
        if total_available < quantity:
            return False

        inventories = sorted(inventories, key=lambda x: x.created_at)
        
        modified_inventories = []
        remaining_quantity = quantity

        for inventory in inventories:
            if remaining_quantity <= 0:
                break

            if inventory.quantity >= remaining_quantity:
                inventory.quantity -= remaining_quantity
                remaining_quantity = 0
                modified_inventories.append(inventory)
                break
            else:
                remaining_quantity -= inventory.quantity
                inventory.quantity = 0
                modified_inventories.append(inventory)

        if modified_inventories:
            await crud.inventory.bulk_update(self.db, db_objs=modified_inventories)
            return True

        return False

    async def get_low_stock_products(self, threshold: int) -> List[Product]:
        """
        Get products with stock quantity below or equal to threshold
        """
        return await crud.product.get_products_quantity_le(self.db, quantity=threshold)
