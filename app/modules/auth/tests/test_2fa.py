import pyotp
import pytest
from flask import url_for

import app.modules.auth.routes as auth_routes


@pytest.fixture
def twofa_dummy_user():
    class DummyUser:
        id = 123
        email = "2fa@example.com"
        otp_secret = "JBSWY3DPEHPK3PXP"
        twofa_enabled = True

        # Flask-Login required attributes
        is_active = True
        is_authenticated = True
        is_anonymous = False

        def get_id(self):
            return str(self.id)

        def check_password(self, password):
            return True

        def __init__(self):
            self.profile = type("P", (), {"surname": "Test", "name": "User"})()

    return DummyUser()


def test_verify_2fa_redirects_to_login_if_no_session(test_client):
    response = test_client.get("/verify-2fa", follow_redirects=True)
    assert response.request.path == url_for("auth.login")


def test_verify_2fa_redirects_to_login_if_user_not_found(test_client, monkeypatch):
    def fake_get_user_by_id(_):
        return None

    monkeypatch.setattr(auth_routes.authentication_service, "get_user_by_id", fake_get_user_by_id, raising=False)

    with test_client.session_transaction() as sess:
        sess["2fa_user_id"] = 999

    response = test_client.get("/verify-2fa", follow_redirects=True)
    assert response.request.path == url_for("auth.login")


def test_verify_2fa_successful_login(test_client, monkeypatch, twofa_dummy_user):
    def fake_get_user_by_id(_):
        return twofa_dummy_user

    monkeypatch.setattr(auth_routes.authentication_service, "get_user_by_id", fake_get_user_by_id, raising=False)

    with test_client.session_transaction() as sess:
        sess["2fa_user_id"] = twofa_dummy_user.id

    valid_otp = pyotp.TOTP(twofa_dummy_user.otp_secret).now()

    response = test_client.post(
        "/verify-2fa",
        data=dict(otp_code=valid_otp),
        follow_redirects=True,
    )

    assert response.request.path == url_for("public.index")

    with test_client.session_transaction() as sess:
        assert "2fa_user_id" not in sess


def test_verify_2fa_invalid_code_shows_error(test_client, monkeypatch, twofa_dummy_user):
    def fake_get_user_by_id(_):
        return twofa_dummy_user

    monkeypatch.setattr(auth_routes.authentication_service, "get_user_by_id", fake_get_user_by_id, raising=False)

    with test_client.session_transaction() as sess:
        sess["2fa_user_id"] = twofa_dummy_user.id

    response = test_client.post(
        "/verify-2fa",
        data=dict(otp_code="000000"),
        follow_redirects=True,
    )

    assert response.request.path == url_for("auth.verify_2fa")
    assert b"Invalid 2FA code" in response.data
