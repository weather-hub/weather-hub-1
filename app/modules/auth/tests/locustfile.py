from locust import HttpUser, TaskSet, task, between

import pyotp  # asegúrate de tenerlo en requirements

from core.environment.host import get_host_for_locust_testing
from core.locust.common import fake, get_csrf_token


# Mapea usuarios de prueba 2FA a su secreto TOTP
# Deben coincidir con los que tengas en la base de datos
TWOFA_TEST_USERS = {
    "user1@example.com": "JBSWY3DPEHPK3PXP",  # ejemplo base32
}


class SignupBehavior(TaskSet):
    def on_start(self):
        self.signup()

    @task
    def signup(self):
        response = self.client.get("/signup")
        csrf_token = get_csrf_token(response)

        response = self.client.post(
            "/signup",
            data={
                "email": fake.email(),
                "password": fake.password(),
                "csrf_token": csrf_token,
            },
        )
        if response.status_code not in (200, 302):
            print(f"Signup failed: {response.status_code}")


class LoginBehavior(TaskSet):
    def on_start(self):
        self.ensure_logged_out()
        self.login()

    @task
    def ensure_logged_out(self):
        response = self.client.get("/logout")
        if response.status_code not in (200, 302):
            # 502 aquí suele indicar que el backend no estaba listo o que no había sesión;
            # para carga suele bastar con loguearlo y seguir.
            print(f"Logout failed or no active session: {response.status_code}")

    @task
    def login(self):
        # 1) Pantalla de login
        response = self.client.get("/login")
        if response.status_code != 200 or "Login" not in response.text:
            # Si no vemos la página de login, intentamos forzar logout y reintentar
            print("Already logged in or unexpected response, redirecting to logout")
            self.ensure_logged_out()
            response = self.client.get("/login")

        csrf_token = get_csrf_token(response)

        email = "user1@example.com"
        password = "1234"

        # 2) POST /login
        response = self.client.post(
            "/login",
            data={
                "email": email,
                "password": password,
                "csrf_token": csrf_token,
            },
            allow_redirects=True,  # por claridad; es True por defecto
        )

        if response.status_code not in (200, 302):
            print(f"Login failed: {response.status_code}")
            return

        # 3) Si el usuario tiene 2FA activado, la app redirige a /verify-2fa
        final_url = getattr(response, "url", "")
        if "/verify-2fa" in final_url or "otp_code" in response.text or "2FA" in response.text:
            otp_secret = TWOFA_TEST_USERS.get(email)
            if not otp_secret:
                print(f"2FA required for {email} but no test secret configured")
                return

            # Llamamos al helper interno, NO es @task
            self._complete_2fa_flow(otp_secret)
        else:
            # Flujo sin 2FA; ya estaríamos dentro
            pass

    # <<< IMPORTANTE: sin @task >>>
    def _complete_2fa_flow(self, otp_secret: str):
        """
        Completa el flujo de /verify-2fa: GET formulario + POST con OTP y csrf_token.
        """
        # GET /verify-2fa para obtener el formulario y el csrf
        response = self.client.get("/verify-2fa")
        if response.status_code != 200:
            print(f"2FA verify page failed: {response.status_code}")
            return

        csrf_token = get_csrf_token(response)

        # Generar OTP válido para el secreto
        totp = pyotp.TOTP(otp_secret)
        otp_code = totp.now()

        # POST /verify-2fa con OTP y csrf
        response = self.client.post(
            "/verify-2fa",
            data={
                "otp_code": otp_code,
                "csrf_token": csrf_token,
            },
            allow_redirects=True,
        )

        if response.status_code not in (200, 302):
            print(f"2FA verification failed: {response.status_code}")


class AuthUser(HttpUser):
    tasks = [SignupBehavior, LoginBehavior]
    wait_time = between(5, 9)
    host = get_host_for_locust_testing()
