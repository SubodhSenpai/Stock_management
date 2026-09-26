"""Queries over products, categories, units of measure and reordering rules."""

from decimal import Decimal

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import Product, ProductCategory, ReorderRule, UnitOfMeasure
from app.models.operation import OperationLine
from app.models.stock import StockMove, StockQuant, stock_levels
from app.models.warehouse import Location

ZERO = Decimal(0)


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, category_id: int) -> ProductCategory | None:
        return self.db.get(ProductCategory, category_id)

    def list_all(self) -> list[ProductCategory]:
        return list(
            self.db.execute(select(ProductCategory).order_by(ProductCategory.name)).scalars()
        )

    def name_exists(self, name: str) -> bool:
        stmt = select(ProductCategory.id).where(func.lower(ProductCategory.name) == name.lower())
        return self.db.execute(stmt).first() is not None

    def has_products(self, category_id: int) -> bool:
        return bool(
            self.db.execute(select(exists().where(Product.category_id == category_id))).scalar()
        )

    def add(self, category: ProductCategory) -> ProductCategory:
        self.db.add(category)
        self.db.flush()
        return category


class UomRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, uom_id: int) -> UnitOfMeasure | None:
        return self.db.get(UnitOfMeasure, uom_id)

    def list_all(self) -> list[UnitOfMeasure]:
        return list(self.db.execute(select(UnitOfMeasure).order_by(UnitOfMeasure.id)).scalars())


class ProductRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _with_relations(self) -> Select:
        return select(Product).options(selectinload(Product.category), selectinload(Product.uom))

    def get(self, product_id: int) -> Product | None:
        stmt = self._with_relations().where(Product.id == product_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_many(self, product_ids: list[int]) -> dict[int, Product]:
        if not product_ids:
            return {}
        stmt = self._with_relations().where(Product.id.in_(product_ids))
        return {product.id: product for product in self.db.execute(stmt).scalars()}

    def sku_exists(self, sku: str) -> bool:
        return (
            self.db.execute(select(Product.id).where(Product.sku == sku.upper())).first()
            is not None
        )

    def add(self, product: Product) -> Product:
        self.db.add(product)
        self.db.flush()
        return product

    def has_moves(self, product_id: int) -> bool:
        return bool(
            self.db.execute(select(exists().where(StockMove.product_id == product_id))).scalar()
        )

    def has_open_lines(self, product_id: int) -> bool:
        return bool(
            self.db.execute(select(exists().where(OperationLine.product_id == product_id))).scalar()
        )

    def search(
        self,
        *,
        query: str | None = None,
        category_id: int | None = None,
        include_archived: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Product], int]:
        """Find products by name or SKU. Trigram indexes keep the ILIKE search fast."""
        stmt = self._with_relations()
        count_stmt = select(func.count()).select_from(Product)

        filters = []
        if not include_archived:
            filters.append(Product.is_active)
        if category_id is not None:
            filters.append(Product.category_id == category_id)
        if query:
            pattern = f"%{query}%"
            filters.append(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))

        if filters:
            stmt = stmt.where(*filters)
            count_stmt = count_stmt.where(*filters)

        total = self.db.execute(count_stmt).scalar_one()
        rows = self.db.execute(stmt.order_by(Product.name).limit(limit).offset(offset)).scalars()
        return list(rows), total

    def stock_totals(
        self, product_ids: list[int], *, warehouse_id: int | None = None
    ) -> dict[int, tuple[Decimal, Decimal]]:
        """On hand and reserved per product, summed over the requested warehouse or all of them."""
        if not product_ids:
            return {}
        stmt = select(
            stock_levels.c.product_id,
            func.sum(stock_levels.c.on_hand),
            func.sum(stock_levels.c.reserved),
        ).where(stock_levels.c.product_id.in_(product_ids))
        if warehouse_id is not None:
            stmt = stmt.where(stock_levels.c.warehouse_id == warehouse_id)
        stmt = stmt.group_by(stock_levels.c.product_id)
        return {row[0]: (row[1] or ZERO, row[2] or ZERO) for row in self.db.execute(stmt)}

    def minimum_quantities(
        self, product_ids: list[int], *, warehouse_id: int | None = None
    ) -> dict[int, Decimal]:
        """The reorder threshold per product, so a product can be flagged as low on stock."""
        if not product_ids:
            return {}
        stmt = select(ReorderRule.product_id, func.sum(ReorderRule.min_quantity)).where(
            ReorderRule.product_id.in_(product_ids)
        )
        if warehouse_id is not None:
            stmt = stmt.where(ReorderRule.warehouse_id == warehouse_id)
        stmt = stmt.group_by(ReorderRule.product_id)
        return {row[0]: row[1] or ZERO for row in self.db.execute(stmt)}

    def stock_by_location(self, product_id: int) -> list[tuple[Location, StockQuant]]:
        stmt = (
            select(Location, StockQuant)
            .join(StockQuant, StockQuant.location_id == Location.id)
            .options(selectinload(Location.warehouse))
            .where(StockQuant.product_id == product_id)
            .order_by(Location.name)
        )
        return [(row[0], row[1]) for row in self.db.execute(stmt)]


class ReorderRuleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, rule_id: int) -> ReorderRule | None:
        return self.db.get(ReorderRule, rule_id)

    def list_for(self, *, product_id: int | None = None) -> list[ReorderRule]:
        stmt = select(ReorderRule).options(selectinload(ReorderRule.product))
        if product_id is not None:
            stmt = stmt.where(ReorderRule.product_id == product_id)
        return list(self.db.execute(stmt.order_by(ReorderRule.id)).scalars())

    def exists_for(self, product_id: int, warehouse_id: int) -> bool:
        stmt = select(ReorderRule.id).where(
            ReorderRule.product_id == product_id, ReorderRule.warehouse_id == warehouse_id
        )
        return self.db.execute(stmt).first() is not None

    def add(self, rule: ReorderRule) -> ReorderRule:
        self.db.add(rule)
        self.db.flush()
        return rule
