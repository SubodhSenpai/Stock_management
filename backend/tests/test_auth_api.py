"""Authentication endpoints, including the rules that keep account details private."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import login_limiter, otp_request_limiter
from app.models.user import PasswordResetOtp, User
from app.services.email_service import EmailService

VALID_PASSWORD = "Str0ng!Password"
SIGNUP_BODY = {
    "login_id": "manager1",
    "email": "manager@example.com",
    "full_name": "Priya Sharma",
    "role": "manager",
    "password": VALID_PASSWORD,
    "confirm_password": VALID_PASSWORD,
}


@pytest.fixture(autouse=True)
def clear_rate_limits() -> None:
    """Rate limiters are process-wide, so reset them between tests."""
    login_limiter._hits.clear()
    otp_request_limiter._hits.clear()


def signup(client: TestClient, **overrides: object) -> dict:
    response = client.post("/api/v1/auth/signup", json={**SIGNUP_BODY, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def error_of(response) -> dict:
    return response.json()["error"]


@pytest.fixture
def emailed_codes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Capture reset codes at the point they would be emailed."""
    codes: list[str] = []

    def record(self: EmailService, to: str, otp: str, valid_minutes: int) -> None:
        codes.append(otp)

    monkeypatch.setattr(EmailService, "send_password_reset_otp", record)
    return codes


class TestSignup:
    def test_creates_an_account_and_signs_the_user_in(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/signup", json=SIGNUP_BODY)

        assert response.status_code == 201
        body = response.json()
        assert body["login_id"] == "manager1"
        assert body["role"] == "manager"
        assert get_settings().auth_cookie_name in response.cookies

    def test_never_returns_the_password_hash(self, client: TestClient) -> None:
        assert "password_hash" not in signup(client)

    def test_session_cookie_is_not_readable_by_scripts(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/signup", json=SIGNUP_BODY)
        cookie_header = response.headers["set-cookie"].lower()
        assert "httponly" in cookie_header
        assert "samesite=lax" in cookie_header

    @pytest.mark.parametrize(
        ("password", "reason"),
        [
            ("short1!A", "too short"),
            ("nouppercase1!", "no uppercase letter"),
            ("NOLOWERCASE1!", "no lowercase letter"),
            ("NoSpecialChar1", "no special character"),
        ],
    )
    def test_rejects_a_weak_password(self, client: TestClient, password: str, reason: str) -> None:
        response = client.post(
            "/api/v1/auth/signup",
            json={**SIGNUP_BODY, "password": password, "confirm_password": password},
        )

        assert response.status_code == 422, reason
        assert error_of(response)["code"] == "VALIDATION_ERROR"
        assert any(d["field"] == "password" for d in error_of(response)["details"])

    def test_rejects_mismatched_confirmation(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/signup",
            json={**SIGNUP_BODY, "confirm_password": "Different!1Password"},
        )

        assert response.status_code == 422
        assert "do not match" in response.text

    @pytest.mark.parametrize("login_id", ["short", "waaaaaaaaaytoolong", "has spaces"])
    def test_rejects_an_invalid_login_id(self, client: TestClient, login_id: str) -> None:
        response = client.post("/api/v1/auth/signup", json={**SIGNUP_BODY, "login_id": login_id})

        assert response.status_code == 422
        assert any(d["field"] == "login_id" for d in error_of(response)["details"])

    def test_rejects_a_duplicate_login_id_whatever_the_case(self, client: TestClient) -> None:
        signup(client)

        response = client.post(
            "/api/v1/auth/signup",
            json={**SIGNUP_BODY, "login_id": "MANAGER1", "email": "other@example.com"},
        )

        assert response.status_code == 409
        assert error_of(response)["code"] == "DUPLICATE"
        assert error_of(response)["details"][0]["field"] == "login_id"

    def test_rejects_a_duplicate_email(self, client: TestClient) -> None:
        signup(client)

        response = client.post("/api/v1/auth/signup", json={**SIGNUP_BODY, "login_id": "someone2"})

        assert response.status_code == 409
        assert error_of(response)["details"][0]["field"] == "email"

    def test_rejects_unexpected_fields(self, client: TestClient) -> None:
        """Guards against a caller trying to set fields the API does not offer."""
        response = client.post("/api/v1/auth/signup", json={**SIGNUP_BODY, "is_active": False})

        assert response.status_code == 422


class TestLogin:
    def test_accepts_correct_credentials(self, client: TestClient) -> None:
        signup(client)
        client.cookies.clear()

        response = client.post(
            "/api/v1/auth/login", json={"login_id": "manager1", "password": VALID_PASSWORD}
        )

        assert response.status_code == 200
        assert response.json()["login_id"] == "manager1"

    def test_login_id_is_not_case_sensitive(self, client: TestClient) -> None:
        signup(client)

        response = client.post(
            "/api/v1/auth/login", json={"login_id": "MANAGER1", "password": VALID_PASSWORD}
        )

        assert response.status_code == 200

    def test_wrong_password_and_unknown_user_give_the_same_answer(self, client: TestClient) -> None:
        """The reply must not reveal whether the account exists."""
        signup(client)

        wrong_password = client.post(
            "/api/v1/auth/login", json={"login_id": "manager1", "password": "Wr0ng!Password"}
        )
        unknown_user = client.post(
            "/api/v1/auth/login", json={"login_id": "nobody99", "password": VALID_PASSWORD}
        )

        assert wrong_password.status_code == unknown_user.status_code == 401
        assert error_of(wrong_password) | {"request_id": None} == error_of(unknown_user) | {
            "request_id": None
        }
        assert error_of(wrong_password)["message"] == "Invalid Login Id or Password"

    def test_blocks_repeated_guessing(self, client: TestClient) -> None:
        signup(client)
        attempt = {"login_id": "manager1", "password": "Wr0ng!Password"}

        for _ in range(5):
            assert client.post("/api/v1/auth/login", json=attempt).status_code == 401

        response = client.post("/api/v1/auth/login", json=attempt)
        assert response.status_code == 429
        assert error_of(response)["code"] == "TOO_MANY_REQUESTS"


class TestSession:
    def test_me_returns_the_signed_in_user(self, client: TestClient) -> None:
        signup(client)

        response = client.get("/api/v1/auth/me")

        assert response.status_code == 200
        assert response.json()["email"] == "manager@example.com"

    def test_me_requires_a_session(self, client: TestClient) -> None:
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401
        assert error_of(response)["code"] == "NOT_AUTHENTICATED"

    def test_a_forged_token_is_rejected(self, client: TestClient) -> None:
        client.cookies.set(get_settings().auth_cookie_name, "not.a.real.token")

        assert client.get("/api/v1/auth/me").status_code == 401

    def test_logout_clears_the_session(self, client: TestClient) -> None:
        signup(client)

        assert client.post("/api/v1/auth/logout").status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401


class TestPasswordReset:
    def _latest_code_hash(self, db: Session) -> str:
        otp = (
            db.execute(select(PasswordResetOtp).order_by(PasswordResetOtp.id.desc()))
            .scalars()
            .first()
        )
        assert otp is not None
        return otp.otp_hash

    def _request_code(self, client: TestClient, emailed_codes: list[str]) -> str:
        response = client.post(
            "/api/v1/auth/forgot-password", json={"email": "manager@example.com"}
        )
        assert response.status_code == 202
        assert emailed_codes, "a reset code should have been sent"
        return emailed_codes[-1]

    def test_unknown_email_gets_the_same_reply(self, client: TestClient) -> None:
        signup(client)

        known = client.post("/api/v1/auth/forgot-password", json={"email": "manager@example.com"})
        unknown = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})

        assert known.status_code == unknown.status_code == 202
        assert known.json() == unknown.json()

    def test_the_stored_code_is_hashed(self, client: TestClient, db: Session) -> None:
        signup(client)
        client.post("/api/v1/auth/forgot-password", json={"email": "manager@example.com"})

        stored = self._latest_code_hash(db)
        assert len(stored) == 64
        assert not stored.isdigit()

    def test_full_reset_flow(self, client: TestClient, emailed_codes: list[str]) -> None:
        signup(client)
        code = self._request_code(client, emailed_codes)

        verified = client.post(
            "/api/v1/auth/verify-otp", json={"email": "manager@example.com", "otp": code}
        )
        assert verified.status_code == 200
        reset_token = verified.json()["reset_token"]

        new_password = "Br4nd!NewPassword"
        reset = client.post(
            "/api/v1/auth/reset-password",
            json={
                "reset_token": reset_token,
                "password": new_password,
                "confirm_password": new_password,
            },
        )
        assert reset.status_code == 200

        client.cookies.clear()
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"login_id": "manager1", "password": new_password},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"login_id": "manager1", "password": VALID_PASSWORD},
            ).status_code
            == 401
        )

    def test_a_wrong_code_is_rejected(self, client: TestClient) -> None:
        signup(client)
        client.post("/api/v1/auth/forgot-password", json={"email": "manager@example.com"})

        response = client.post(
            "/api/v1/auth/verify-otp", json={"email": "manager@example.com", "otp": "000000"}
        )

        assert response.status_code == 400
        assert error_of(response)["code"] == "OTP_INVALID"

    def test_a_code_stops_working_after_too_many_attempts(self, client: TestClient) -> None:
        signup(client)
        client.post("/api/v1/auth/forgot-password", json={"email": "manager@example.com"})
        guess = {"email": "manager@example.com", "otp": "000000"}

        for _ in range(get_settings().otp_max_attempts):
            client.post("/api/v1/auth/verify-otp", json=guess)

        response = client.post("/api/v1/auth/verify-otp", json=guess)
        assert error_of(response)["code"] == "OTP_EXPIRED"

    def test_a_code_can_only_be_used_once(
        self, client: TestClient, emailed_codes: list[str]
    ) -> None:
        signup(client)
        code = self._request_code(client, emailed_codes)
        token = client.post(
            "/api/v1/auth/verify-otp", json={"email": "manager@example.com", "otp": code}
        ).json()["reset_token"]
        password = "Us3d!OncePassword"
        body = {"reset_token": token, "password": password, "confirm_password": password}

        assert client.post("/api/v1/auth/reset-password", json=body).status_code == 200
        assert (
            client.post(
                "/api/v1/auth/verify-otp", json={"email": "manager@example.com", "otp": code}
            ).status_code
            == 400
        )

    def test_an_access_token_cannot_be_used_to_reset_a_password(self, client: TestClient) -> None:
        """Tokens are bound to a purpose, so a stolen session cannot change the password."""
        signup(client)
        session_token = client.cookies[get_settings().auth_cookie_name]
        password = "Another!1Password"

        response = client.post(
            "/api/v1/auth/reset-password",
            json={
                "reset_token": session_token,
                "password": password,
                "confirm_password": password,
            },
        )

        assert response.status_code == 401


class TestProfile:
    def test_updates_the_display_name(self, client: TestClient) -> None:
        signup(client)

        response = client.patch("/api/v1/users/me", json={"full_name": "Priya S."})

        assert response.status_code == 200
        assert response.json()["full_name"] == "Priya S."

    def test_changing_password_requires_the_current_one(self, client: TestClient) -> None:
        signup(client)
        password = "Rot4ted!Password"

        response = client.post(
            "/api/v1/users/me/password",
            json={
                "current_password": "Wr0ng!Password",
                "password": password,
                "confirm_password": password,
            },
        )

        assert response.status_code == 401
        assert error_of(response)["code"] == "INVALID_CREDENTIALS"

    def test_changes_the_password(self, client: TestClient, db: Session) -> None:
        signup(client)
        password = "Rot4ted!Password"

        response = client.post(
            "/api/v1/users/me/password",
            json={
                "current_password": VALID_PASSWORD,
                "password": password,
                "confirm_password": password,
            },
        )

        assert response.status_code == 200
        user = db.execute(select(User).where(User.login_id == "manager1")).scalar_one()
        assert user.password_hash.startswith("$2b$")


class TestErrorContract:
    def test_every_error_has_the_same_shape(self, client: TestClient) -> None:
        body = client.get("/api/v1/auth/me").json()

        assert set(body) == {"error"}
        assert set(body["error"]) == {"code", "message", "details", "request_id"}
        assert body["error"]["request_id"]

    def test_responses_carry_security_headers(self, client: TestClient) -> None:
        headers = client.get("/api/v1/health").headers

        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
