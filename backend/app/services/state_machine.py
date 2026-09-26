"""Which actions are legal on a document, and from which states.

This table is the single source of truth. The API exposes the same table as
`allowed_actions` on each document, so the UI shows buttons without reimplementing rules.
"""

from enum import StrEnum

from app.core.exceptions import InvalidTransitionError
from app.models.enums import OperationStatus, OperationType
from app.models.operation import Operation


class Action(StrEnum):
    CONFIRM = "confirm"
    CHECK_AVAILABILITY = "check_availability"
    VALIDATE = "validate"
    CANCEL = "cancel"


_T = OperationType
_S = OperationStatus
_A = Action

OPEN_STATUSES = frozenset({_S.DRAFT, _S.WAITING, _S.READY})
EDITABLE_STATUSES = frozenset({_S.DRAFT})

# (document type, action) -> the states the action may be taken from
TRANSITIONS: dict[tuple[OperationType, Action], frozenset[OperationStatus]] = {
    (_T.RECEIPT, _A.CONFIRM): frozenset({_S.DRAFT}),
    (_T.RECEIPT, _A.VALIDATE): frozenset({_S.READY}),
    (_T.DELIVERY, _A.CONFIRM): frozenset({_S.DRAFT}),
    (_T.DELIVERY, _A.CHECK_AVAILABILITY): frozenset({_S.WAITING}),
    (_T.DELIVERY, _A.VALIDATE): frozenset({_S.READY}),
    (_T.INTERNAL, _A.CONFIRM): frozenset({_S.DRAFT}),
    (_T.INTERNAL, _A.CHECK_AVAILABILITY): frozenset({_S.WAITING}),
    (_T.INTERNAL, _A.VALIDATE): frozenset({_S.READY}),
    # An adjustment has nothing to reserve, so it applies straight from draft.
    (_T.ADJUSTMENT, _A.VALIDATE): frozenset({_S.DRAFT}),
    **{(operation_type, _A.CANCEL): OPEN_STATUSES for operation_type in OperationType},
}

_ACTION_VERB = {
    _A.CONFIRM: "confirm",
    _A.CHECK_AVAILABILITY: "check availability for",
    _A.VALIDATE: "validate",
    _A.CANCEL: "cancel",
}


def is_allowed(operation: Operation, action: Action) -> bool:
    return operation.status in TRANSITIONS.get((operation.type, action), frozenset())


def assert_allowed(operation: Operation, action: Action) -> None:
    if not is_allowed(operation, action):
        raise InvalidTransitionError(
            f"Cannot {_ACTION_VERB[action]} a {operation.status.value} "
            f"{operation.type.value} ({operation.reference})."
        )


def allowed_actions(operation: Operation) -> list[str]:
    """Every action currently legal on this document, in a stable order."""
    return [action.value for action in Action if is_allowed(operation, action)]


def assert_editable(operation: Operation) -> None:
    if operation.status not in EDITABLE_STATUSES:
        raise InvalidTransitionError(
            f"{operation.reference} can only be edited while it is a draft."
        )
