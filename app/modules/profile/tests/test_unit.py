import pytest
import pyotp

from app import db
from app.modules.auth.models import User
from app.modules.conftest import login, logout
from app.modules.profile.models import UserProfile


@pytest.fixture(scope="module")
def test_client(test_client):
    """
    Extends the test_client fixture to add additional specific data for module testing.
    for module testing (por example, new users)
    """
    with test_client.application.app_context():
        user_test = User(email="user@example.com", password="test1234")
        db.session.add(user_test)
        db.session.commit()

        profile = UserProfile(user_id=user_test.id, name="Name", surname="Surname")
        db.session.add(profile)
        db.session.commit()

    yield test_client


def test_edit_profile_page_get(test_client):
    """
    Tests access to the profile editing page via a GET request.
    """
    login_response = login(test_client, "user@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful."

    response = test_client.get("/profile/edit")
    assert response.status_code == 200, "The profile editing page could not be accessed."
    assert b"Edit profile" in response.data, "The expected content is not present on the page"

    logout(test_client)


def test_setup_2fa_stores_temp_secret_and_qr_in_session(test_client):
    """
    /profile/setup-2fa debe generar un secret temporal y un QR en sesión
    y redirigir a la página de edición de perfil.
    """
    login_response = login(test_client, "user@example.com", "test1234")
    assert login_response.status_code == 200

    response = test_client.get("/profile/setup-2fa", follow_redirects=False)
    # Redirige a /profile/edit
    assert response.status_code == 302
    assert "/profile/edit" in response.headers["Location"]

    # Comprobamos que se han guardado los valores en sesión
    with test_client.session_transaction() as sess:
        assert "temp_otp_secret" in sess
        assert "qr_b64" in sess
        temp_secret = sess["temp_otp_secret"]

    assert isinstance(temp_secret, str) and len(temp_secret) > 0

    logout(test_client)


def test_verify_2fa_enables_2fa_and_clears_session(test_client, monkeypatch):
    """
    /profile/verify-2fa con un código válido debe habilitar 2FA
    en el usuario y limpiar los datos temporales de sesión.
    """

    # Forzamos que pyotp.random_base32 genere siempre un secreto de 16 chars
    # que cabe en la columna otp_secret (String(16)).
    # Nota: bypass total del chequeo de 160 bits de pyotp.random_base32.
    fixed_secret = "JBSWY3DPEHPK3PXP"  # 16 caracteres base32

    def fake_random_base32(*args, **kwargs):
        return fixed_secret

    monkeypatch.setattr(pyotp, "random_base32", fake_random_base32)

    login_response = login(test_client, "user@example.com", "test1234")
    assert login_response.status_code == 200

    # Primero llamamos a setup_2fa para generar el secret temporal (ya de 16 chars)
    test_client.get("/profile/setup-2fa")

    with test_client.session_transaction() as sess:
        temp_secret = sess.get("temp_otp_secret")
        assert temp_secret is not None
        assert len(temp_secret) == 16

    # Generamos un OTP válido usando el mismo secreto
    totp = pyotp.TOTP(temp_secret)
    code = totp.now()

    # POST a /profile/verify-2fa
    response = test_client.post(
        "/profile/verify-2fa",
        data={"verification_code": code},
        follow_redirects=True,
    )

    # Debe redirigir de vuelta a /profile/edit
    assert response.request.path == "/profile/edit"

    # El usuario debe tener 2FA habilitado y el secret guardado
    with test_client.application.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        assert user.twofa_enabled is True
        assert user.otp_secret == temp_secret

    # La sesión ya no debe contener los datos temporales
    with test_client.session_transaction() as sess:
        assert "temp_otp_secret" not in sess
        assert "qr_b64" not in sess

    logout(test_client)
