from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.sale_item import SaleItem
from crud.schemas import SaleItemCreate, SaleItemUpdate


class CRUDSaleItem(CRUDBase[SaleItem, SaleItemCreate, SaleItemUpdate]):
    async def get_by_sale_id(
        self, db: AsyncSession, *, sale_id: int
    ) -> Iterable[SaleItem]:
        async with db as session:
            stmt = select(self.model).filter(self.model.sale_id == sale_id)
            results = await session.execute(stmt)
            return results.scalars().all()


sale_item = CRUDSaleItem(SaleItem)
