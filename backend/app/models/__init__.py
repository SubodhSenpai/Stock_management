"""ORM models. Importing this package registers every table on `Base.metadata`."""

from app.models.base import Base
from app.models.catalog import Product, ProductCategory, ReorderRule, UnitOfMeasure
from app.models.enums import LocationType, OperationStatus, OperationType, PartnerType, UserRole
from app.models.operation import Operation, OperationLine, OperationSequence
from app.models.partner import Partner
from app.models.stock import StockMove, StockQuant, stock_levels
from app.models.user import PasswordResetOtp, RefreshToken, User
from app.models.warehouse import Location, Warehouse

__all__ = [
    "Base",
    "Location",
    "LocationType",
    "Operation",
    "OperationLine",
    "OperationSequence",
    "OperationStatus",
    "OperationType",
    "PasswordResetOtp",
    "Partner",
    "PartnerType",
    "Product",
    "ProductCategory",
    "RefreshToken",
    "ReorderRule",
    "StockMove",
    "StockQuant",
    "UnitOfMeasure",
    "User",
    "UserRole",
    "Warehouse",
    "stock_levels",
]
