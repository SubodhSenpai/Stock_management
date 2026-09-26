"""Products, categories and reordering rules.

Opening stock is never written straight into the balance. It goes through an adjustment
document like any other change, so the ledger explains where every unit came from.
"""

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, DuplicateError, InUseError, NotFoundError
from app.models.catalog import Product, ProductCategory, ReorderRule, UnitOfMeasure
from app.models.enums import OperationType
from app.models.user import User
from app.repositories.catalog_repo import (
    CategoryRepository,
    ProductRepository,
    ReorderRuleRepository,
    UomRepository,
)
from app.schemas.catalog import (
    CategoryCreate,
    ProductCreate,
    ProductUpdate,
    ReorderRuleCreate,
    ReorderRuleUpdate,
)
from app.schemas.operation import OperationCreate, OperationLineIn

logger = logging.getLogger(__name__)
ZERO = Decimal(0)


class ProductService:
    def __init__(
        self,
        db: Session,
        products: ProductRepository,
        categories: CategoryRepository,
        uoms: UomRepository,
        rules: ReorderRuleRepository,
    ) -> None:
        self.db = db
        self.products = products
        self.categories = categories
        self.uoms = uoms
        self.rules = rules

    # ---------- products ----------

    def search(
        self,
        *,
        query: str | None = None,
        category_id: int | None = None,
        warehouse_id: int | None = None,
        include_archived: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[tuple[Product, Decimal, Decimal, bool]], int]:
        """Products with their stock totals and whether each is below its reorder level."""
        products, total = self.products.search(
            query=query,
            category_id=category_id,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )
        product_ids = [product.id for product in products]
        totals = self.products.stock_totals(product_ids, warehouse_id=warehouse_id)
        minimums = self.products.minimum_quantities(product_ids, warehouse_id=warehouse_id)

        rows = []
        for product in products:
            on_hand, reserved = totals.get(product.id, (ZERO, ZERO))
            minimum = minimums.get(product.id)
            is_low = minimum is not None and on_hand <= minimum
            rows.append((product, on_hand, reserved, is_low))
        return rows, total

    def get(self, product_id: int) -> Product:
        product = self.products.get(product_id)
        if product is None:
            raise NotFoundError("That product does not exist.")
        return product

    def stock_by_location(self, product_id: int) -> list:
        self.get(product_id)
        return self.products.stock_by_location(product_id)

    def create(self, data: ProductCreate, user: User) -> tuple[Product, OperationCreate | None]:
        """Create the product, and describe the opening-stock document if one is needed.

        The adjustment itself is raised by the API layer through OperationService, so this
        service never has to know how documents are validated.
        """
        if self.products.sku_exists(data.sku):
            raise DuplicateError(
                f"SKU {data.sku} is already used by another product.",
                [{"field": "sku", "message": "Already in use"}],
            )
        self._require_category(data.category_id)
        uom = self._require_uom(data.uom_id)

        if data.initial_stock and not uom.allow_fraction and data.initial_stock.quantity % 1 != 0:
            raise BusinessRuleError(
                f"{uom.name} cannot be split, so {data.initial_stock.quantity} is not valid.",
                code="INVALID_QUANTITY",
            )

        product = self.products.add(
            Product(
                sku=data.sku,
                name=data.name,
                category_id=data.category_id,
                uom_id=data.uom_id,
                unit_cost=data.unit_cost,
                created_by=user.id,
            )
        )
        self.db.commit()
        logger.info("Created product %s", product.sku)

        opening = None
        if data.initial_stock:
            opening = OperationCreate(
                type=OperationType.ADJUSTMENT,
                source_location_id=data.initial_stock.location_id,
                lines=[
                    OperationLineIn(
                        product_id=product.id, counted_quantity=data.initial_stock.quantity
                    )
                ],
                notes="Opening stock",
            )
        return product, opening

    def update(self, product_id: int, data: ProductUpdate) -> Product:
        product = self.get(product_id)

        if data.category_id is not None:
            self._require_category(data.category_id)
            product.category_id = data.category_id
        if data.uom_id is not None and data.uom_id != product.uom_id:
            # Changing the unit would silently reinterpret every past quantity.
            if self.products.has_moves(product_id):
                raise InUseError(
                    "This product already has stock movements, so its unit of measure "
                    "can no longer be changed."
                )
            self._require_uom(data.uom_id)
            product.uom_id = data.uom_id
        for field in ("name", "unit_cost", "is_active"):
            value = getattr(data, field)
            if value is not None:
                setattr(product, field, value)

        self.db.commit()
        return product

    def archive(self, product_id: int) -> None:
        """Products are archived, never deleted, so the ledger keeps its meaning."""
        product = self.get(product_id)
        product.is_active = False
        self.db.commit()

    # ---------- categories ----------

    def list_categories(self) -> list[ProductCategory]:
        return self.categories.list_all()

    def create_category(self, data: CategoryCreate) -> ProductCategory:
        if self.categories.name_exists(data.name):
            raise DuplicateError(
                f"A category named {data.name} already exists.",
                [{"field": "name", "message": "Already exists"}],
            )
        category = self.categories.add(ProductCategory(name=data.name))
        self.db.commit()
        return category

    def delete_category(self, category_id: int) -> None:
        self._require_category(category_id)
        if self.categories.has_products(category_id):
            raise InUseError("This category still has products, so it cannot be deleted.")
        self.db.delete(self.categories.get(category_id))
        self.db.commit()

    def list_uoms(self) -> list[UnitOfMeasure]:
        return self.uoms.list_all()

    # ---------- reordering rules ----------

    def list_rules(self, *, product_id: int | None = None) -> list[ReorderRule]:
        return self.rules.list_for(product_id=product_id)

    def create_rule(self, data: ReorderRuleCreate) -> ReorderRule:
        if data.max_quantity < data.min_quantity:
            raise BusinessRuleError(
                "The maximum must be at least the minimum.",
                [{"field": "max_quantity", "message": "Must be at least the minimum"}],
            )
        self.get(data.product_id)
        if self.rules.exists_for(data.product_id, data.warehouse_id):
            raise DuplicateError("This product already has a rule for that warehouse.")
        rule = self.rules.add(
            ReorderRule(
                product_id=data.product_id,
                warehouse_id=data.warehouse_id,
                min_quantity=data.min_quantity,
                max_quantity=data.max_quantity,
            )
        )
        self.db.commit()
        return rule

    def update_rule(self, rule_id: int, data: ReorderRuleUpdate) -> ReorderRule:
        rule = self.rules.get(rule_id)
        if rule is None:
            raise NotFoundError("That reordering rule does not exist.")

        minimum = data.min_quantity if data.min_quantity is not None else rule.min_quantity
        maximum = data.max_quantity if data.max_quantity is not None else rule.max_quantity
        if maximum < minimum:
            raise BusinessRuleError(
                "The maximum must be at least the minimum.",
                [{"field": "max_quantity", "message": "Must be at least the minimum"}],
            )
        rule.min_quantity, rule.max_quantity = minimum, maximum
        self.db.commit()
        return rule

    def delete_rule(self, rule_id: int) -> None:
        rule = self.rules.get(rule_id)
        if rule is None:
            raise NotFoundError("That reordering rule does not exist.")
        self.db.delete(rule)
        self.db.commit()

    # ---------- helpers ----------

    def _require_category(self, category_id: int) -> ProductCategory:
        category = self.categories.get(category_id)
        if category is None:
            raise NotFoundError("That category does not exist.")
        return category

    def _require_uom(self, uom_id: int) -> UnitOfMeasure:
        uom = self.uoms.get(uom_id)
        if uom is None:
            raise NotFoundError("That unit of measure does not exist.")
        return uom
