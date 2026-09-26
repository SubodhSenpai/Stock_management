"""Security guarantees, tested rather than assumed.

Three groups:
  * every endpoint that is not deliberately public rejects anonymous callers;
  * refresh tokens rotate, revoke, and detect reuse;
  * inputs cannot be used to inject SQL, smuggle fields, or leak internals through errors.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import login_limiter, otp_request_limiter
from app.core.tokens import create_reset_token, hash_refresh_token
from app.main import create_app
from app.models.user import RefreshToken

API = "/api/v1"
PASSWORD = "Str0ng!Password"

# Endpoints anonymous callers are meant to reach. Everything else must return 401.
PUBLIC_ENDPOINTS = {
    (f"{API}/health", "get"),
    (f"{API}/auth/signup", "post"),
    (f"{API}/auth/login", "post"),
    (f"{API}/auth/logout", "post"),
    (f"{API}/auth/refresh", "post"),
    (f"{API}/auth/forgot-password", "post"),
    (f"{API}/auth/verify-otp", "post"),
    (f"{API}/auth/reset-password", "post"),
}

PATH_PARAMS = {
    "{operation_id}": "1",
    "{product_id}": "1",
    "{warehouse_id}": "1",
    "{location_id}": "1",
    "{partner_id}": "1",
    "{category_id}": "1",
    "{rule_id}": "1",
}


@pytest.fixture(autouse=True)
def clear_rate_limits() -> None:
    login_limiter._hits.clear()
    otp_request_limiter._hits.clear()


def signup(client: TestClient, login_id: str = "manager1") -> dict:
    response = client.post(
        f"{API}/auth/signup",
        json={
            "login_id": login_id,
            "email": f"{login_id}@example.com",
            "role": "manager",
            "password": PASSWORD,
            "confirm_password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def concrete_paths() -> list[tuple[str, str]]:
    """Every route in the app, with path parameters filled in."""
    spec = create_app().openapi()
    routes = []
    for path, operations in spec["paths"].items():
        url = path
        for placeholder, value in PATH_PARAMS.items():
            url = url.replace(placeholder, value)
        routes.extend((url, method) for method in operations)
    return sorted(routes)


class TestEveryEndpointIsProtected:
    """A missed auth dependency is the classic way private data leaks, so check them all."""

    def test_protected_endpoints_reject_anonymous_callers(self, client: TestClient) -> None:
        leaks = []
        for url, method in concrete_paths():
            if (url, method) in PUBLIC_ENDPOINTS:
                continue
            response = client.request(method.upper(), url, json={})
            if response.status_code != 401:
                leaks.append(f"{method.upper()} {url} -> {response.status_code}")

        assert leaks == [], f"these endpoints answered without a session: {leaks}"

    def test_a_protected_endpoint_returns_no_data_when_refused(self, client: TestClient) -> None:
        response = client.get(f"{API}/products")

        assert response.status_code == 401
        assert set(response.json()) == {"error"}, "the body must carry no payload"

    @pytest.mark.parametrize(
        "token",
        [
            "not-a-token",
            "a.b.c",
            # Signed with the right shape but the wrong secret.
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.bad-signature",
        ],
    )
    def test_a_forged_access_token_is_refused(self, client: TestClient, token: str) -> None:
        client.cookies.set(get_settings().auth_cookie_name, token)

        assert client.get(f"{API}/auth/me").status_code == 401

    def test_a_reset_token_cannot_be_used_as_a_session(self, client: TestClient) -> None:
        """Tokens carry a purpose, so one issued for a password reset is not a login."""
        user = signup(client)
        client.cookies.clear()
        client.cookies.set(get_settings().auth_cookie_name, create_reset_token(user["id"]))

        assert client.get(f"{API}/auth/me").status_code == 401


class TestRefreshTokens:
    def test_signing_in_issues_both_cookies(self, client: TestClient) -> None:
        signup(client)
        settings = get_settings()

        assert settings.auth_cookie_name in client.cookies
        assert settings.refresh_cookie_name in client.cookies

    def test_both_cookies_are_hidden_from_scripts(self, client: TestClient) -> None:
        response = client.post(
            f"{API}/auth/signup",
            json={
                "login_id": "manager1",
                "email": "manager1@example.com",
                "password": PASSWORD,
                "confirm_password": PASSWORD,
            },
        )

        cookies = response.headers.get_list("set-cookie")
        assert len(cookies) == 2
        assert all("httponly" in cookie.lower() for cookie in cookies)
        assert all("samesite=lax" in cookie.lower() for cookie in cookies)

    def test_the_refresh_cookie_is_scoped_to_the_auth_path(self, client: TestClient) -> None:
        """It should not ride along with ordinary API calls."""
        response = client.post(
            f"{API}/auth/signup",
            json={
                "login_id": "manager1",
                "email": "manager1@example.com",
                "password": PASSWORD,
                "confirm_password": PASSWORD,
            },
        )

        refresh_cookie = next(
            cookie
            for cookie in response.headers.get_list("set-cookie")
            if cookie.startswith(get_settings().refresh_cookie_name)
        )
        assert "Path=/api/v1/auth" in refresh_cookie

    def test_the_stored_token_is_hashed(self, client: TestClient, db: Session) -> None:
        signup(client)
        presented = client.cookies[get_settings().refresh_cookie_name]

        stored = db.execute(select(RefreshToken)).scalars().one()
        assert stored.token_hash != presented
        assert stored.token_hash == hash_refresh_token(presented)

    def test_refreshing_returns_a_new_pair(self, client: TestClient) -> None:
        signup(client)
        settings = get_settings()
        before = client.cookies[settings.refresh_cookie_name]

        response = client.post(f"{API}/auth/refresh")

        assert response.status_code == 200
        assert client.cookies[settings.refresh_cookie_name] != before, "the token must rotate"

    def test_the_new_access_token_works(self, client: TestClient) -> None:
        signup(client)

        client.post(f"{API}/auth/refresh")

        assert client.get(f"{API}/auth/me").status_code == 200

    def test_a_used_refresh_token_stops_working(self, client: TestClient) -> None:
        signup(client)
        settings = get_settings()
        first = client.cookies[settings.refresh_cookie_name]
        client.post(f"{API}/auth/refresh")

        client.cookies.set(settings.refresh_cookie_name, first)
        response = client.post(f"{API}/auth/refresh")

        assert response.status_code == 401

    def test_reusing_a_token_signs_out_every_session(self, client: TestClient, db: Session) -> None:
        """A replayed token means it was copied, so nobody keeps the session."""
        signup(client)
        settings = get_settings()
        stolen = client.cookies[settings.refresh_cookie_name]
        client.post(f"{API}/auth/refresh")  # the real client rotates

        client.cookies.set(settings.refresh_cookie_name, stolen)
        client.post(f"{API}/auth/refresh")  # the copy is replayed

        db.expire_all()
        tokens = db.execute(select(RefreshToken)).scalars().all()
        assert all(token.revoked_at is not None for token in tokens)

    def test_refreshing_without_a_token_is_refused(self, client: TestClient) -> None:
        response = client.post(f"{API}/auth/refresh")

        assert response.status_code == 401

    def test_logging_out_revokes_the_token(self, client: TestClient) -> None:
        signup(client)
        settings = get_settings()
        token = client.cookies[settings.refresh_cookie_name]

        client.post(f"{API}/auth/logout")

        client.cookies.set(settings.refresh_cookie_name, token)
        assert client.post(f"{API}/auth/refresh").status_code == 401

    def test_logging_out_everywhere_ends_all_sessions(
        self, client: TestClient, db: Session
    ) -> None:
        signup(client)
        client.post(f"{API}/auth/refresh")

        response = client.post(f"{API}/auth/logout-all")

        assert response.status_code == 200
        db.expire_all()
        tokens = db.execute(select(RefreshToken)).scalars().all()
        assert all(token.revoked_at is not None for token in tokens)

    def test_changing_the_password_ends_other_sessions(
        self, client: TestClient, db: Session
    ) -> None:
        signup(client)
        new_password = "N3w!PasswordHere"

        response = client.post(
            f"{API}/users/me/password",
            json={
                "current_password": PASSWORD,
                "password": new_password,
                "confirm_password": new_password,
            },
        )

        assert response.status_code == 200
        db.expire_all()
        tokens = db.execute(select(RefreshToken)).scalars().all()
        assert all(token.revoked_at is not None for token in tokens)


class TestInputHandling:
    @pytest.fixture(autouse=True)
    def signed_in(self, client: TestClient) -> None:
        signup(client)

    @pytest.mark.parametrize(
        "payload",
        [
            "'; DROP TABLE products; --",
            "' OR '1'='1",
            "%' UNION SELECT NULL, NULL --",
        ],
    )
    def test_search_terms_cannot_inject_sql(self, client: TestClient, payload: str) -> None:
        """Queries are parameterised, so these are treated as ordinary text."""
        response = client.get(f"{API}/products", params={"q": payload})

        assert response.status_code == 200
        assert response.json()["items"] == []
        assert client.get(f"{API}/products").status_code == 200, "the table still exists"

    def test_unknown_fields_are_rejected(self, client: TestClient) -> None:
        """Stops a caller setting a field the endpoint never offered."""
        response = client.post(
            f"{API}/partners",
            json={"name": "Someone", "type": "vendor", "id": 999, "is_admin": True},
        )

        assert response.status_code == 422

    def test_an_id_that_is_not_a_number_is_rejected(self, client: TestClient) -> None:
        assert client.get(f"{API}/products/not-an-id").status_code == 422

    def test_a_negative_id_is_rejected(self, client: TestClient) -> None:
        assert client.get(f"{API}/products", params={"category_id": -5}).status_code == 422

    def test_an_oversized_field_is_rejected(self, client: TestClient) -> None:
        response = client.post(f"{API}/partners", json={"name": "x" * 500, "type": "vendor"})

        assert response.status_code == 422

    def test_errors_do_not_leak_internals(self, client: TestClient) -> None:
        """No stack traces, SQL or file paths in a response body."""
        response = client.get(f"{API}/products/999999")

        assert response.status_code == 404
        body = response.text.lower()
        assert "traceback" not in body
        assert "select" not in body
        assert "\\users\\" not in body

    def test_responses_carry_security_headers(self, client: TestClient) -> None:
        headers = client.get(f"{API}/auth/me").headers

        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Referrer-Policy"] == "same-origin"

    def test_every_response_carries_a_request_id(self, client: TestClient) -> None:
        """Lets a support report be matched to a server log line."""
        response = client.get(f"{API}/auth/me")

        assert response.headers["X-Request-ID"]

    def test_a_client_supplied_request_id_cannot_inject_into_logs(self, client: TestClient) -> None:
        response = client.get(f"{API}/auth/me", headers={"X-Request-ID": "bad\nINJECTED LOG LINE"})

        assert "\n" not in response.headers["X-Request-ID"]
