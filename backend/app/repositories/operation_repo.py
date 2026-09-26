"""Queries over inventory operations and their reference numbering."""

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.clock import today
from app.models.enums import OperationStatus, OperationType
from app.models.operation import Operation, OperationLine
from app.models.partner import Partner
from app.models.warehouse import Location, Warehouse

OPEN_STATUSES = (OperationStatus.DRAFT, OperationStatus.WAITING, OperationStatus.READY)

REFERENCE_PREFIX = {
    OperationType.RECEIPT: "IN",
    OperationType.DELIVERY: "OUT",
    OperationType.INTERNAL: "INT",
    OperationType.ADJUSTMENT: "ADJ",
}


class OperationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _with_relations(self) -> Select:
        return select(Operation).options(
            selectinload(Operation.lines).selectinload(OperationLine.product),
            selectinload(Operation.source_location).selectinload(Location.warehouse),
            selectinload(Operation.dest_location).selectinload(Location.warehouse),
            selectinload(Operation.partner),
            selectinload(Operation.responsible),
        )

    def get(self, operation_id: int) -> Operation | None:
        stmt = self._with_relations().where(Operation.id == operation_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_for_update(self, operation_id: int) -> Operation | None:
        """Lock the document before changing its state.

        Two clicks on Validate arrive as two requests; the second waits here, then sees the
        status the first one left behind and is rejected by the state machine.
        """
        locked = self.db.execute(
            select(Operation.id).where(Operation.id == operation_id).with_for_update()
        ).scalar_one_or_none()
        if locked is None:
            return None
        self.db.expire_all()
        return self.get(operation_id)

    def add(self, operation: Operation) -> Operation:
        self.db.add(operation)
        self.db.flush()
        return operation

    def search(
        self,
        *,
        operation_type: OperationType | None = None,
        statuses: list[OperationStatus] | None = None,
        warehouse_id: int | None = None,
        location_id: int | None = None,
        partner_id: int | None = None,
        query: str | None = None,
        late_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Operation], int]:
        stmt = self._with_relations()
        count_stmt = select(func.count()).select_from(Operation)

        filters = []
        if operation_type is not None:
            filters.append(Operation.type == operation_type)
        if statuses:
            filters.append(Operation.status.in_(statuses))
        if warehouse_id is not None:
            filters.append(Operation.warehouse_id == warehouse_id)
        if location_id is not None:
            filters.append(
                or_(
                    Operation.source_location_id == location_id,
                    Operation.dest_location_id == location_id,
                )
            )
        if partner_id is not None:
            filters.append(Operation.partner_id == partner_id)
        if late_only:
            filters += [Operation.status.in_(OPEN_STATUSES), Operation.schedule_date < today()]
        if query:
            pattern = f"%{query}%"
            # Search by document reference or by contact name, as the mockup asks.
            contact_match = select(Partner.id).where(
                Partner.id == Operation.partner_id, Partner.name.ilike(pattern)
            )
            filters.append(or_(Operation.reference.ilike(pattern), contact_match.exists()))

        if filters:
            stmt = stmt.where(*filters)
            count_stmt = count_stmt.where(*filters)

        total = self.db.execute(count_stmt).scalar_one()
        rows = self.db.execute(
            stmt.order_by(Operation.schedule_date.desc(), Operation.id.desc())
            .limit(limit)
            .offset(offset)
        ).scalars()
        return list(rows), total

    def next_reference(self, warehouse: Warehouse, operation_type: OperationType) -> str:
        """Allocate the next document number for this warehouse and type.

        The upsert takes a row lock held until commit, so two users creating documents at
        the same moment get different numbers instead of colliding on the unique index.
        """
        next_number = self.db.execute(
            text(
                """
                INSERT INTO operation_sequences (warehouse_id, type, next_number)
                VALUES (:warehouse_id, CAST(:type AS operation_type), 2)
                ON CONFLICT (warehouse_id, type)
                DO UPDATE SET next_number = operation_sequences.next_number + 1
                RETURNING next_number - 1
                """
            ),
            {"warehouse_id": warehouse.id, "type": operation_type.value},
        ).scalar_one()
        return f"{warehouse.short_code}/{REFERENCE_PREFIX[operation_type]}/{next_number:04d}"
