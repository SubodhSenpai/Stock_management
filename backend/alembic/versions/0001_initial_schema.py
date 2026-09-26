"""Initial schema: auth, catalog, warehouses, operations and the stock ledger.

Revision ID: 0001
Revises:
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QUANTITY = sa.Numeric(14, 3)
MONEY = sa.Numeric(12, 2)

user_role = postgresql.ENUM("manager", "staff", name="user_role", create_type=False)
location_type = postgresql.ENUM(
    "internal", "vendor", "customer", "adjustment", name="location_type", create_type=False
)
operation_type = postgresql.ENUM(
    "receipt", "delivery", "internal", "adjustment", name="operation_type", create_type=False
)
operation_status = postgresql.ENUM(
    "draft", "waiting", "ready", "done", "canceled", name="operation_status", create_type=False
)
partner_type = postgresql.ENUM(
    "vendor", "customer", "both", name="partner_type", create_type=False
)

ENUMS = (user_role, location_type, operation_type, operation_status, partner_type)

# The ledger is the audit trail: rows may be inserted, never changed or removed.
LEDGER_GUARD_FUNCTION = """
CREATE OR REPLACE FUNCTION forbid_ledger_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'stock_moves is append-only: % is not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;
"""

LEDGER_GUARD_TRIGGER = """
CREATE TRIGGER trg_stock_moves_immutable
BEFORE UPDATE OR DELETE ON stock_moves
FOR EACH ROW EXECUTE FUNCTION forbid_ledger_mutation();
"""

# One definition of on hand / reserved / free, reused by the stock page, dashboard and alerts.
STOCK_LEVELS_VIEW = """
CREATE VIEW stock_levels AS
SELECT q.product_id,
       l.warehouse_id,
       SUM(q.quantity)                       AS on_hand,
       SUM(q.reserved_quantity)              AS reserved,
       SUM(q.quantity - q.reserved_quantity) AS free_to_use
FROM stock_quants q
JOIN locations l ON l.id = q.location_id
GROUP BY q.product_id, l.warehouse_id;
"""


def _id_column() -> sa.Column:
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False)


def upgrade() -> None:
    bind = op.get_bind()
    # Trigram indexes make the ILIKE '%term%' search boxes index-backed.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for enum in ENUMS:
        enum.create(bind, checkfirst=True)

    _create_auth_tables()
    _create_warehouse_tables()
    _create_catalog_tables()
    _create_partner_table()
    _create_stock_quant_table()
    _create_operation_tables()
    _create_stock_move_table()

    op.execute(LEDGER_GUARD_FUNCTION)
    op.execute(LEDGER_GUARD_TRIGGER)
    op.execute(STOCK_LEVELS_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS stock_levels")
    op.execute("DROP TRIGGER IF EXISTS trg_stock_moves_immutable ON stock_moves")
    op.execute("DROP FUNCTION IF EXISTS forbid_ledger_mutation()")

    for table in (
        "stock_moves",
        "operation_lines",
        "operations",
        "operation_sequences",
        "stock_quants",
        "partners",
        "reorder_rules",
        "products",
        "units_of_measure",
        "product_categories",
        "locations",
        "warehouses",
        "password_reset_otps",
        "users",
    ):
        op.drop_table(table)

    bind = op.get_bind()
    for enum in ENUMS:
        enum.drop(bind, checkfirst=True)
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")


def _create_auth_tables() -> None:
    op.create_table(
        "users",
        _id_column(),
        sa.Column("login_id", sa.String(12), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("full_name", sa.String(100)),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="staff"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("login_id ~ '^[A-Za-z0-9_.]{6,12}$'", name="ck_users_login_id_format"),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
    )
    op.create_index("ux_users_login_id_lower", "users", [sa.text("lower(login_id)")], unique=True)

    op.create_table(
        "password_reset_otps",
        _id_column(),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("otp_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_password_reset_otps"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_password_reset_otps_user_id_users",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_password_reset_otps_attempts_non_negative"),
    )
    op.create_index(
        "ix_password_reset_otps_user_id_created_at",
        "password_reset_otps",
        ["user_id", "created_at"],
    )
    # At most one live code per user; issuing a new code consumes the previous one.
    op.create_index(
        "ux_password_reset_otps_one_active",
        "password_reset_otps",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("consumed_at IS NULL"),
    )


def _create_warehouse_tables() -> None:
    op.create_table(
        "warehouses",
        _id_column(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("short_code", sa.String(5), nullable=False),
        sa.Column("address", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_warehouses"),
        sa.UniqueConstraint("short_code", name="uq_warehouses_short_code"),
        sa.CheckConstraint("short_code ~ '^[A-Z0-9]{1,5}$'", name="ck_warehouses_short_code_format"),
    )

    op.create_table(
        "locations",
        _id_column(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("short_code", sa.String(20), nullable=False),
        sa.Column("type", location_type, nullable=False, server_default="internal"),
        sa.Column("warehouse_id", sa.BigInteger()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_locations"),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_locations_warehouse_id_warehouses",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "warehouse_id",
            "short_code",
            name="uq_locations_warehouse_id_short_code",
            postgresql_nulls_not_distinct=True,
        ),
        sa.CheckConstraint("short_code ~ '^[A-Za-z0-9-]{1,20}$'", name="ck_locations_short_code_format"),
        sa.CheckConstraint(
            "(type = 'internal') = (warehouse_id IS NOT NULL)",
            name="ck_locations_warehouse_iff_internal",
        ),
    )
    op.create_index("ix_locations_warehouse_id", "locations", ["warehouse_id"])


def _create_catalog_tables() -> None:
    op.create_table(
        "product_categories",
        _id_column(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_product_categories"),
    )
    op.create_index(
        "ux_product_categories_name_lower",
        "product_categories",
        [sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "units_of_measure",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("allow_fraction", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id", name="pk_units_of_measure"),
        sa.UniqueConstraint("code", name="uq_units_of_measure_code"),
    )

    op.create_table(
        "products",
        _id_column(),
        sa.Column("sku", sa.String(32), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("uom_id", sa.SmallInteger(), nullable=False),
        sa.Column("unit_cost", MONEY, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["product_categories.id"],
            name="fk_products_category_id_product_categories",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["uom_id"],
            ["units_of_measure.id"],
            name="fk_products_uom_id_units_of_measure",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_products_created_by_users"),
        sa.UniqueConstraint("sku", name="uq_products_sku"),
        sa.CheckConstraint("sku ~ '^[A-Z0-9][A-Z0-9-]{1,31}$'", name="ck_products_sku_format"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_products_name_not_blank"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_products_unit_cost_non_negative"),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index(
        "ix_products_name_trgm",
        "products",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_products_sku_trgm",
        "products",
        ["sku"],
        postgresql_using="gin",
        postgresql_ops={"sku": "gin_trgm_ops"},
    )

    op.create_table(
        "reorder_rules",
        _id_column(),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), nullable=False),
        sa.Column("min_quantity", QUANTITY, nullable=False),
        sa.Column("max_quantity", QUANTITY, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_reorder_rules"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_reorder_rules_product_id_products",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_reorder_rules_warehouse_id_warehouses",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "product_id", "warehouse_id", name="uq_reorder_rules_product_id_warehouse_id"
        ),
        sa.CheckConstraint("min_quantity >= 0", name="ck_reorder_rules_min_non_negative"),
        sa.CheckConstraint("max_quantity >= min_quantity", name="ck_reorder_rules_max_gte_min"),
    )
    op.create_index("ix_reorder_rules_warehouse_id", "reorder_rules", ["warehouse_id"])


def _create_partner_table() -> None:
    op.create_table(
        "partners",
        _id_column(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("type", partner_type, nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("phone", sa.String(20)),
        sa.Column("address", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_partners"),
    )
    op.create_index(
        "ix_partners_name_trgm",
        "partners",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )


def _create_stock_quant_table() -> None:
    op.create_table(
        "stock_quants",
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", QUANTITY, nullable=False, server_default="0"),
        sa.Column("reserved_quantity", QUANTITY, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("product_id", "location_id", name="pk_stock_quants"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_stock_quants_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_stock_quants_location_id_locations",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("quantity >= 0", name="ck_stock_quants_quantity_non_negative"),
        sa.CheckConstraint(
            "reserved_quantity >= 0 AND reserved_quantity <= quantity",
            name="ck_stock_quants_reserved_within_on_hand",
        ),
    )
    op.create_index("ix_stock_quants_location_id", "stock_quants", ["location_id"])


def _create_operation_tables() -> None:
    op.create_table(
        "operation_sequences",
        sa.Column("warehouse_id", sa.BigInteger(), nullable=False),
        sa.Column("type", operation_type, nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("warehouse_id", "type", name="pk_operation_sequences"),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_operation_sequences_warehouse_id_warehouses",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("next_number > 0", name="ck_operation_sequences_next_number_positive"),
    )

    op.create_table(
        "operations",
        _id_column(),
        sa.Column("reference", sa.String(30), nullable=False),
        sa.Column("type", operation_type, nullable=False),
        sa.Column("status", operation_status, nullable=False, server_default="draft"),
        sa.Column("warehouse_id", sa.BigInteger(), nullable=False),
        sa.Column("source_location_id", sa.BigInteger(), nullable=False),
        sa.Column("dest_location_id", sa.BigInteger(), nullable=False),
        sa.Column("partner_id", sa.BigInteger()),
        sa.Column("delivery_address", sa.Text()),
        sa.Column("schedule_date", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("responsible_id", sa.BigInteger()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("validated_by", sa.BigInteger()),
        sa.Column("validated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_operations"),
        sa.ForeignKeyConstraint(
            ["warehouse_id"], ["warehouses.id"], name="fk_operations_warehouse_id_warehouses"
        ),
        sa.ForeignKeyConstraint(
            ["source_location_id"],
            ["locations.id"],
            name="fk_operations_source_location_id_locations",
        ),
        sa.ForeignKeyConstraint(
            ["dest_location_id"], ["locations.id"], name="fk_operations_dest_location_id_locations"
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"], ["partners.id"], name="fk_operations_partner_id_partners"
        ),
        sa.ForeignKeyConstraint(
            ["responsible_id"], ["users.id"], name="fk_operations_responsible_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_operations_created_by_users"
        ),
        sa.ForeignKeyConstraint(
            ["validated_by"], ["users.id"], name="fk_operations_validated_by_users"
        ),
        sa.UniqueConstraint("reference", name="uq_operations_reference"),
        sa.CheckConstraint(
            "source_location_id <> dest_location_id", name="ck_operations_locations_differ"
        ),
        sa.CheckConstraint(
            "(status = 'done') = (validated_at IS NOT NULL)",
            name="ck_operations_done_iff_validated",
        ),
        sa.CheckConstraint(
            "type NOT IN ('receipt', 'delivery') OR partner_id IS NOT NULL",
            name="ck_operations_partner_required",
        ),
    )
    op.create_index("ix_operations_warehouse_id", "operations", ["warehouse_id"])
    op.create_index("ix_operations_source_location_id", "operations", ["source_location_id"])
    op.create_index("ix_operations_dest_location_id", "operations", ["dest_location_id"])
    op.create_index("ix_operations_partner_id", "operations", ["partner_id"])
    op.create_index("ix_operations_type_status", "operations", ["type", "status"])
    # Partial index stays small: it only covers documents still in progress.
    op.create_index(
        "ix_operations_pending_schedule_date",
        "operations",
        ["schedule_date"],
        postgresql_where=sa.text("status IN ('draft', 'waiting', 'ready')"),
    )
    op.create_index(
        "ix_operations_reference_trgm",
        "operations",
        ["reference"],
        postgresql_using="gin",
        postgresql_ops={"reference": "gin_trgm_ops"},
    )

    op.create_table(
        "operation_lines",
        _id_column(),
        sa.Column("operation_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", QUANTITY),
        sa.Column("counted_quantity", QUANTITY),
        sa.Column("system_quantity", QUANTITY),
        sa.PrimaryKeyConstraint("id", name="pk_operation_lines"),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.id"],
            name="fk_operation_lines_operation_id_operations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name="fk_operation_lines_product_id_products"
        ),
        sa.UniqueConstraint(
            "operation_id", "product_id", name="uq_operation_lines_operation_id_product_id"
        ),
        sa.CheckConstraint("quantity > 0", name="ck_operation_lines_quantity_positive"),
        sa.CheckConstraint(
            "counted_quantity >= 0", name="ck_operation_lines_counted_quantity_non_negative"
        ),
        sa.CheckConstraint(
            "num_nonnulls(quantity, counted_quantity) = 1",
            name="ck_operation_lines_exactly_one_quantity",
        ),
    )
    op.create_index("ix_operation_lines_product_id", "operation_lines", ["product_id"])


def _create_stock_move_table() -> None:
    op.create_table(
        "stock_moves",
        _id_column(),
        sa.Column("operation_id", sa.BigInteger(), nullable=False),
        sa.Column("operation_line_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("from_location_id", sa.BigInteger(), nullable=False),
        sa.Column("to_location_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", QUANTITY, nullable=False),
        sa.Column("unit_cost", MONEY, nullable=False),
        sa.Column("moved_by", sa.BigInteger(), nullable=False),
        sa.Column("moved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_stock_moves"),
        sa.ForeignKeyConstraint(
            ["operation_id"], ["operations.id"], name="fk_stock_moves_operation_id_operations"
        ),
        sa.ForeignKeyConstraint(
            ["operation_line_id"],
            ["operation_lines.id"],
            name="fk_stock_moves_operation_line_id_operation_lines",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name="fk_stock_moves_product_id_products"
        ),
        sa.ForeignKeyConstraint(
            ["from_location_id"], ["locations.id"], name="fk_stock_moves_from_location_id_locations"
        ),
        sa.ForeignKeyConstraint(
            ["to_location_id"], ["locations.id"], name="fk_stock_moves_to_location_id_locations"
        ),
        sa.ForeignKeyConstraint(["moved_by"], ["users.id"], name="fk_stock_moves_moved_by_users"),
        # One line executes at most once, so validating twice is impossible at the DB level.
        sa.UniqueConstraint("operation_line_id", name="uq_stock_moves_operation_line_id"),
        sa.CheckConstraint("quantity > 0", name="ck_stock_moves_quantity_positive"),
        sa.CheckConstraint(
            "from_location_id <> to_location_id", name="ck_stock_moves_locations_differ"
        ),
    )
    op.create_index("ix_stock_moves_product_id_moved_at", "stock_moves", ["product_id", "moved_at"])
    op.create_index("ix_stock_moves_from_location_id", "stock_moves", ["from_location_id"])
    op.create_index("ix_stock_moves_to_location_id", "stock_moves", ["to_location_id"])
    op.create_index("ix_stock_moves_operation_id", "stock_moves", ["operation_id"])
    # Backs keyset pagination of Move History: WHERE (moved_at, id) < (:ts, :id).
    op.create_index("ix_stock_moves_moved_at_id", "stock_moves", ["moved_at", "id"])
