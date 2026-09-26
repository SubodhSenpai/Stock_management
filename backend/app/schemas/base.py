"""Base classes every request and response schema builds on."""

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Request bodies: unknown fields are rejected rather than silently ignored.

    This stops a caller from smuggling in a field the endpoint never meant to accept.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReadModel(BaseModel):
    """Responses: built straight from ORM objects."""

    model_config = ConfigDict(from_attributes=True)
