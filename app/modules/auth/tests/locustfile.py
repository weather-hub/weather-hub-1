import random

from bs4 import BeautifulSoup
from locust import HttpUser, TaskSet, task

from core.environment.host import get_host_for_locust_testing
from core.locust.common import fake, get_csrf_token


class SignupBehavior(TaskSet):
    def on_start(self):
        self.signup()

    @task
    def signup(self):
        response = self.client.get("/signup")
        csrf_token = get_csrf_token(response)

        response = self.client.post(
            "/signup", data={"email": fake.email(), "password": fake.password(), "csrf_token": csrf_token}
        )
        if response.status_code != 200:
            print(f"Signup failed: {response.status_code}")


class LoginBehavior(TaskSet):
    def on_start(self):
        self.ensure_logged_out()
        self.login()

    @task
    def ensure_logged_out(self):
        response = self.client.get("/logout")
        if response.status_code != 200:
            print(f"Logout failed or no active session: {response.status_code}")

    @task
    def login(self):
        response = self.client.get("/login")
        if response.status_code != 200 or "Login" not in response.text:
            print("Already logged in or unexpected response, redirecting to logout")
            self.ensure_logged_out()
            response = self.client.get("/login")

        csrf_token = get_csrf_token(response)

        response = self.client.post(
            "/login", data={"email": "user1@example.com", "password": "1234", "csrf_token": csrf_token}
        )
        if response.status_code != 200:
            print(f"Login failed: {response.status_code}")


class SessionBehavior(TaskSet):
    """Simulate session management actions: view sessions, close one, close all others."""

    def on_start(self):
        # Ensure the user is logged in before performing session actions
        self.ensure_logged_out()
        self.login()

    @task(3)
    def view_sessions(self):
        response = self.client.get("/sessions")
        if response.status_code != 200:
            print(f"View sessions failed: {response.status_code}")

    @task(1)
    def close_random_session(self):
        # Load sessions page and find any close forms to extract a session_id
        response = self.client.get("/sessions")
        if response.status_code != 200:
            return
        soup = BeautifulSoup(response.text, "html.parser")
        # find form actions that contain '/sessions/close/'
        forms = soup.find_all("form", action=True)
        close_forms = [f for f in forms if "/sessions/close/" in f["action"]]
        if not close_forms:
            return
        chosen = random.choice(close_forms)
        action = chosen["action"]
        # attempt to get CSRF token from the page
        try:
            csrf = get_csrf_token(response)
        except Exception:
            csrf = None

        data = {"csrf_token": csrf} if csrf else {}
        # POST to the action URL
        self.client.post(action, data=data)

    @task(1)
    def close_all_others(self):
        # Close all other sessions via the dedicated endpoint
        response = self.client.get("/sessions")
        if response.status_code != 200:
            return
        try:
            csrf = get_csrf_token(response)
        except Exception:
            csrf = None
        data = {"csrf_token": csrf} if csrf else {}
        self.client.post("/sessions/close-all", data=data)


class AuthUser(HttpUser):
    tasks = [SignupBehavior, LoginBehavior, SessionBehavior]
    min_wait = 5000
    max_wait = 9000
    host = get_host_for_locust_testing()
