"""The operations, stock, products and dashboard endpoints over HTTP.

Covers the parts that only exist at the API layer: role permissions, the response
contract, and the query filters the UI depends on.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tokens import create_access_token
from app.models.enums import UserRole
from tests import factories

API = "/api/v1"


@pytest.fixture
def manager(db: Session):
    return factories.make_user(db, "manager1", UserRole.MANAGER)


@pytest.fixture
def staff(db: Session):
    return factories.make_user(db, "staff001", UserRole.STAFF)


@pytest.fixture
def sign_in(client: TestClient):
    """Put a user's session cookie on the test client."""

    def _sign_in(user) -> TestClient:
        client.cookies.set(get_settings().auth_cookie_name, create_access_token(user.id))
        return client

    return _sign_in


@pytest.fixture
def world(db: Session, manager) -> dict:
    warehouse = factories.make_warehouse(db)
    category = factories.make_category(db)
    pieces = factories.make_uom(db, "pcs")
    stock = factories.make_location(db, warehouse, "Stock")
    desk = factories.make_product(db, category, pieces, sku="DESK001", name="Desk")
    db.commit()
    return {
        "warehouse": warehouse,
        "stock": stock,
        "desk": desk,
        "category": category,
        "uom": pieces,
        "partner": factories.make_partner(db),
    }


def error_of(response) -> dict:
    return response.json()["error"]


def receipt_body(world: dict, quantity: int) -> dict:
    return {
        "type": "receipt",
        "dest_location_id": world["stock"].id,
        "partner_id": world["partner"].id,
        "lines": [{"product_id": world["desk"].id, "quantity": str(quantity)}],
    }


class TestPermissions:
    def test_every_endpoint_needs_a_session(self, client: TestClient) -> None:
        for method, path in [
            ("get", f"{API}/operations"),
            ("get", f"{API}/products"),
            ("get", f"{API}/stock"),
            ("get", f"{API}/moves"),
            ("get", f"{API}/dashboard/summary"),
            ("get", f"{API}/warehouses"),
        ]:
            response = getattr(client, method)(path)
            assert response.status_code == 401, path

    def test_staff_cannot_create_master_data(
        self, client: TestClient, sign_in, staff, world: dict
    ) -> None:
        sign_in(staff)

        response = client.post(f"{API}/warehouses", json={"name": "New Site", "short_code": "NEW"})

        assert response.status_code == 403
        assert error_of(response)["code"] == "FORBIDDEN"

    def test_staff_can_still_run_stock_operations(
        self, client: TestClient, sign_in, staff, world: dict
    ) -> None:
        """Warehouse staff do the day-to-day work, so operations must stay open to them."""
        sign_in(staff)

        response = client.post(f"{API}/operations", json=receipt_body(world, 5))

        assert response.status_code == 201

    def test_managers_can_create_master_data(self, client: TestClient, sign_in, manager) -> None:
        sign_in(manager)

        response = client.post(f"{API}/warehouses", json={"name": "New Site", "short_code": "new"})

        assert response.status_code == 201
        assert response.json()["short_code"] == "NEW", "codes are normalised to upper case"


class TestOperationLifecycleOverHttp:
    def test_a_new_receipt_starts_as_a_draft_with_a_reference(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        sign_in(manager)

        body = client.post(f"{API}/operations", json=receipt_body(world, 50)).json()

        assert body["status"] == "draft"
        assert body["reference"] == "WH/IN/0001"
        assert body["allowed_actions"] == ["confirm", "cancel"]

    def test_the_response_says_which_actions_are_available(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        """The UI renders buttons from this, instead of repeating the rules."""
        sign_in(manager)
        created = client.post(f"{API}/operations", json=receipt_body(world, 50)).json()

        confirmed = client.post(f"{API}/operations/{created['id']}/confirm").json()
        assert confirmed["allowed_actions"] == ["validate", "cancel"]

        done = client.post(f"{API}/operations/{created['id']}/validate").json()
        assert done["allowed_actions"] == []

    def test_validating_twice_is_rejected(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        sign_in(manager)
        created = client.post(f"{API}/operations", json=receipt_body(world, 50)).json()
        client.post(f"{API}/operations/{created['id']}/confirm")
        client.post(f"{API}/operations/{created['id']}/validate")

        response = client.post(f"{API}/operations/{created['id']}/validate")

        assert response.status_code == 409
        assert error_of(response)["code"] == "INVALID_TRANSITION"

    def test_a_short_delivery_marks_the_line_unavailable(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        """This is what turns the line red in the UI."""
        sign_in(manager)
        delivery = client.post(
            f"{API}/operations",
            json={
                "type": "delivery",
                "source_location_id": world["stock"].id,
                "partner_id": world["partner"].id,
                "lines": [{"product_id": world["desk"].id, "quantity": "6"}],
            },
        ).json()

        confirmed = client.post(f"{API}/operations/{delivery['id']}/confirm").json()

        assert confirmed["status"] == "waiting"
        assert confirmed["lines"][0]["is_available"] is False
        assert Decimal(confirmed["lines"][0]["available_quantity"]) == Decimal(0)

    def test_a_duplicate_product_line_is_rejected(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        sign_in(manager)

        response = client.post(
            f"{API}/operations",
            json={
                "type": "receipt",
                "dest_location_id": world["stock"].id,
                "partner_id": world["partner"].id,
                "lines": [
                    {"product_id": world["desk"].id, "quantity": "5"},
                    {"product_id": world["desk"].id, "quantity": "3"},
                ],
            },
        )

        assert response.status_code == 422
        assert "only once" in response.text

    def test_an_operation_needs_at_least_one_line(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        sign_in(manager)

        response = client.post(
            f"{API}/operations",
            json={
                "type": "receipt",
                "dest_location_id": world["stock"].id,
                "partner_id": world["partner"].id,
                "lines": [],
            },
        )

        assert response.status_code == 422


class TestOperationFilters:
    @pytest.fixture(autouse=True)
    def some_operations(self, client: TestClient, sign_in, manager, world: dict) -> None:
        sign_in(manager)
        for _ in range(3):
            client.post(f"{API}/operations", json=receipt_body(world, 5))

    def test_filters_by_type(self, client: TestClient) -> None:
        assert client.get(f"{API}/operations", params={"type": "receipt"}).json()["total"] == 3
        assert client.get(f"{API}/operations", params={"type": "delivery"}).json()["total"] == 0

    def test_filters_by_status(self, client: TestClient) -> None:
        body = client.get(f"{API}/operations", params={"status": "draft"}).json()

        assert body["total"] == 3

    def test_searches_by_reference(self, client: TestClient) -> None:
        body = client.get(f"{API}/operations", params={"q": "WH/IN/0002"}).json()

        assert body["total"] == 1
        assert body["items"][0]["reference"] == "WH/IN/0002"

    def test_searches_by_contact_name(self, client: TestClient) -> None:
        body = client.get(f"{API}/operations", params={"q": "Azure"}).json()

        assert body["total"] == 3

    def test_paginates(self, client: TestClient) -> None:
        body = client.get(f"{API}/operations", params={"page": 2, "page_size": 2}).json()

        assert body["total"] == 3
        assert len(body["items"]) == 1
        assert body["page"] == 2

    def test_rejects_an_oversized_page(self, client: TestClient) -> None:
        assert client.get(f"{API}/operations", params={"page_size": 500}).status_code == 422


class TestStockEndpoints:
    def test_the_stock_page_shows_on_hand_and_free(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        sign_in(manager)
        created = client.post(f"{API}/operations", json=receipt_body(world, 50)).json()
        client.post(f"{API}/operations/{created['id']}/confirm")
        client.post(f"{API}/operations/{created['id']}/validate")

        row = client.get(f"{API}/stock").json()["items"][0]

        assert Decimal(row["on_hand"]) == Decimal(50)
        assert Decimal(row["free_to_use"]) == Decimal(50)
        assert row["product"]["sku"] == "DESK001"

    def test_adjusting_from_the_stock_page_records_a_document(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        """Editing stock must leave a trail, not silently overwrite the number."""
        sign_in(manager)

        response = client.post(
            f"{API}/stock/adjust",
            json={
                "product_id": world["desk"].id,
                "location_id": world["stock"].id,
                "counted_quantity": "17",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "done"
        assert response.json()["reference"].startswith("WH/ADJ/")

        row = client.get(f"{API}/stock").json()["items"][0]
        assert Decimal(row["on_hand"]) == Decimal(17)

    def test_move_history_labels_direction(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        """Incoming rows show green and outgoing red, driven by this field."""
        sign_in(manager)
        created = client.post(f"{API}/operations", json=receipt_body(world, 50)).json()
        client.post(f"{API}/operations/{created['id']}/confirm")
        client.post(f"{API}/operations/{created['id']}/validate")

        body = client.get(f"{API}/moves").json()

        assert body["items"][0]["direction"] == "in"
        assert body["items"][0]["reference"] == "WH/IN/0001"
        assert body["next_cursor"] is None

    def test_move_history_pages_with_a_cursor(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        sign_in(manager)
        for _ in range(3):
            created = client.post(f"{API}/operations", json=receipt_body(world, 5)).json()
            client.post(f"{API}/operations/{created['id']}/confirm")
            client.post(f"{API}/operations/{created['id']}/validate")

        first = client.get(f"{API}/moves", params={"limit": 2}).json()
        assert len(first["items"]) == 2
        assert first["next_cursor"]

        second = client.get(
            f"{API}/moves", params={"limit": 2, "cursor": first["next_cursor"]}
        ).json()
        assert len(second["items"]) == 1
        assert second["next_cursor"] is None

        ids = {item["id"] for item in first["items"]} | {item["id"] for item in second["items"]}
        assert len(ids) == 3, "pages must not overlap"

    def test_a_tampered_cursor_is_rejected(self, client: TestClient, sign_in, manager) -> None:
        sign_in(manager)

        response = client.get(f"{API}/moves", params={"cursor": "not-a-real-cursor"})

        assert response.status_code == 422


class TestProductEndpoints:
    def test_creating_a_product_with_opening_stock_records_it(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        sign_in(manager)

        response = client.post(
            f"{API}/products",
            json={
                "sku": "chair001",
                "name": "Chair",
                "category_id": world["category"].id,
                "uom_id": world["uom"].id,
                "unit_cost": "1200.00",
                "initial_stock": {"location_id": world["stock"].id, "quantity": "40"},
            },
        )

        assert response.status_code == 201
        assert response.json()["sku"] == "CHAIR001", "SKUs are normalised to upper case"

        moves = client.get(f"{API}/moves").json()["items"]
        assert any(move["product"]["sku"] == "CHAIR001" for move in moves), (
            "opening stock should appear in the ledger"
        )

    def test_a_duplicate_sku_is_rejected(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        sign_in(manager)

        response = client.post(
            f"{API}/products",
            json={
                "sku": "DESK001",
                "name": "Another Desk",
                "category_id": world["category"].id,
                "uom_id": world["uom"].id,
            },
        )

        assert response.status_code == 409
        assert error_of(response)["details"][0]["field"] == "sku"

    def test_products_can_be_searched_by_sku(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        sign_in(manager)

        assert client.get(f"{API}/products", params={"q": "DESK"}).json()["total"] == 1
        assert client.get(f"{API}/products", params={"q": "nothing"}).json()["total"] == 0


class TestDashboard:
    def test_summary_counts_open_documents_by_type(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        sign_in(manager)
        created = client.post(f"{API}/operations", json=receipt_body(world, 50)).json()
        client.post(f"{API}/operations/{created['id']}/confirm")

        body = client.get(f"{API}/dashboard/summary").json()

        receipts = next(card for card in body["cards"] if card["type"] == "receipt")
        assert receipts["to_process"] == 1
        assert receipts["pending"] == 1

    def test_all_four_cards_are_always_present(
        self, client: TestClient, sign_in, manager, world: dict
    ) -> None:
        """The dashboard layout should not shift around when a type has no documents."""
        sign_in(manager)

        body = client.get(f"{API}/dashboard/summary").json()

        assert {card["type"] for card in body["cards"]} == {
            "receipt",
            "delivery",
            "internal",
            "adjustment",
        }

    def test_low_stock_suggests_how_much_to_order(
        self, client: TestClient, sign_in, manager, world: dict, db: Session
    ) -> None:
        factories.make_reorder_rule(
            db, world["desk"], world["warehouse"], minimum=Decimal(10), maximum=Decimal(50)
        )
        db.commit()
        sign_in(manager)

        items = client.get(f"{API}/dashboard/low-stock").json()

        assert len(items) == 1
        assert Decimal(items[0]["suggested_order"]) == Decimal(50)
        assert items[0]["product"]["sku"] == "DESK001"
