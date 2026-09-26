"""Reusable field rules, so the same policy applies wherever a value is accepted."""

import re
from typing import Annotated

from pydantic import Field

# bcrypt only reads the first 72 bytes, so longer passwords would silently truncate.
PASSWORD_MIN_LENGTH = 9
PASSWORD_MAX_LENGTH = 72

LOGIN_ID_PATTERN = r"^[A-Za-z0-9_.]+$"
SKU_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9-]{1,31}$"
WAREHOUSE_CODE_PATTERN = r"^[A-Za-z0-9]{1,5}$"
LOCATION_CODE_PATTERN = r"^[A-Za-z0-9-]{1,20}$"

LoginId = Annotated[str, Field(min_length=6, max_length=12, pattern=LOGIN_ID_PATTERN)]
Password = Annotated[str, Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)]
Sku = Annotated[str, Field(min_length=2, max_length=32, pattern=SKU_PATTERN)]
WarehouseCode = Annotated[str, Field(min_length=1, max_length=5, pattern=WAREHOUSE_CODE_PATTERN)]
LocationCode = Annotated[str, Field(min_length=1, max_length=20, pattern=LOCATION_CODE_PATTERN)]

_LOWERCASE = re.compile(r"[a-z]")
_UPPERCASE = re.compile(r"[A-Z]")
_SPECIAL = re.compile(r"[^A-Za-z0-9]")


def validate_password_strength(value: str) -> str:
    """Require a lowercase letter, an uppercase letter and a special character.

    Matches the rule shown on the sign-up mockup. Raises ValueError so Pydantic reports it
    as a field error rather than a 500.
    """
    missing = []
    if not _LOWERCASE.search(value):
        missing.append("a lowercase letter")
    if not _UPPERCASE.search(value):
        missing.append("an uppercase letter")
    if not _SPECIAL.search(value):
        missing.append("a special character")
    if missing:
        raise ValueError(f"Password must contain {', '.join(missing)}")
    return value
