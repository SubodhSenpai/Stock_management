"""Domain enumerations shared by models, schemas and services."""

from enum import StrEnum


class UserRole(StrEnum):
    MANAGER = "manager"
    STAFF = "staff"


class LocationType(StrEnum):
    """Internal locations hold stock; the rest are virtual counterparties in the ledger."""

    INTERNAL = "internal"
    VENDOR = "vendor"
    CUSTOMER = "customer"
    ADJUSTMENT = "adjustment"


class OperationType(StrEnum):
    RECEIPT = "receipt"
    DELIVERY = "delivery"
    INTERNAL = "internal"
    ADJUSTMENT = "adjustment"


class OperationStatus(StrEnum):
    DRAFT = "draft"
    WAITING = "waiting"
    READY = "ready"
    DONE = "done"
    CANCELED = "canceled"


class PartnerType(StrEnum):
    VENDOR = "vendor"
    CUSTOMER = "customer"
    BOTH = "both"
