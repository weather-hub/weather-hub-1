import re

from locust import HttpUser, TaskSet, between, task

from core.environment.host import get_host_for_locust_testing
from core.locust.common import get_csrf_token


class ProfileBehavior(TaskSet):
    def on_start(self):
        """Warm up: hit home page to establish session and capture CSRF"""
        response = self.client.get("/")
        get_csrf_token(response)
        # Extract user IDs from home page datasets
        self.user_ids = self._extract_user_ids(response)
        if not self.user_ids:
            self.user_ids = [1, 2, 3]  # Fallback to common IDs

    def _extract_user_ids(self, response):
        """Extract user IDs from profile links in the response"""
        try:
            matches = re.findall(rb"/profile/(\d+)", response.content or b"")
            return list(set([m.decode("utf-8") for m in matches]))
        except Exception:
            return []

    @task(5)
    def view_public_profile(self):
        """View a public user profile with their datasets"""
        if self.user_ids:
            user_id = self.user_ids[0]  # Use first found user ID
            self.client.get(f"/profile/{user_id}", name="/profile/[user_id]")

    @task(3)
    def view_home_page(self):
        """View home page which displays users linked to datasets"""
        response = self.client.get("/")
        # Update user IDs from home page
        new_ids = self._extract_user_ids(response)
        if new_ids:
            self.user_ids = new_ids

    @task(2)
    def view_profile_paginated(self):
        """View a public profile with pagination"""
        if self.user_ids:
            user_id = self.user_ids[0]
            self.client.get(f"/profile/{user_id}?page=1", name="/profile/[user_id]?page=1")

    @task(1)
    def view_nonexistent_profile(self):
        """Test handling of non-existent profile (should redirect)"""
        self.client.get("/profile/99999", allow_redirects=False, name="/profile/[invalid_id]")


class ProfileUser(HttpUser):
    tasks = [ProfileBehavior]
    wait_time = between(2, 5)
    host = get_host_for_locust_testing()


class Profile2FABehavior(TaskSet):
    """
    Simula un usuario autenticado que entra a editar su perfil
    y dispara la generación del 2FA (QR + secret temporal) mediante /profile/setup-2fa.
    """

    def on_start(self):
        self.ensure_logged_out()
        self.login()

    @task
    def generate_2fa_setup(self):
        """
        Flujo básico:
        - Accede a /profile/edit (vista protegida con login_required).
        - Llama a /profile/setup-2fa, que genera el secret temporal y el QR en sesión
          y redirige de vuelta a /profile/edit.
        """
        # GET /profile/edit
        response = self.client.get("/profile/edit")
        if response.status_code not in (200, 302):
            print(f"Profile edit failed or redirected unexpectedly: {response.status_code}")

        # GET /profile/setup-2fa
        response = self.client.get("/profile/setup-2fa", allow_redirects=False)
        if response.status_code not in (302, 303):
            print(f"Setup 2FA did not redirect as expected: {response.status_code}")
        else:
            location = response.headers.get("Location", "")
            if "/profile/edit" not in location:
                print(f"Unexpected redirect after setup-2fa: {location}")

        # Opcional: seguir la redirección a /profile/edit para medir también ese tiempo
        self.client.get("/profile/edit")

    def ensure_logged_out(self):
        response = self.client.get("/logout")
        if response.status_code not in (200, 302):
            print(f"Logout failed or no active session: {response.status_code}")

    def login(self):
        """
        Login clásico con CSRF; asume que user@example.com NO tiene 2FA habilitado todavía,
        de forma que no entra en el flujo /verify-2fa.
        """
        # 1) GET /login para obtener el formulario y el csrf_token
        response = self.client.get("/login")
        if response.status_code != 200 or "Login" not in response.text:
            print("Unexpected login page response, retrying after logout")
            self.ensure_logged_out()
            response = self.client.get("/login")

        csrf_token = get_csrf_token(response)

        email = "user@example.com"
        password = "test1234"

        # 2) POST /login con CSRF
        response = self.client.post(
            "/login",
            data={
                "email": email,
                "password": password,
                "csrf_token": csrf_token,
            },
            allow_redirects=True,
        )

        if response.status_code not in (200, 302):
            print(f"Login failed: {response.status_code}")


class AuthUser(HttpUser):
    tasks = [Profile2FABehavior]
    wait_time = between(5, 9)
