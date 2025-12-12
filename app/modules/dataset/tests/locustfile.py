from locust import HttpUser, TaskSet, between, task

from core.environment.host import get_host_for_locust_testing
from core.locust.common import get_csrf_token


class DatasetBehavior(TaskSet):
    def _login(self):
        """Authenticate using form-based login to enable commenting tasks.

        Credentials can be provided via environment variables:
        LOCUST_EMAIL, LOCUST_PASSWORD. Falls back to a known test user.
        """
        import os

        email = os.getenv("LOCUST_EMAIL", "testuser@example.com")
        password = os.getenv("LOCUST_PASSWORD", "password123")

        # Get login page to fetch CSRF token
        login_page = self.client.get("/auth/login")
        try:
            csrf = get_csrf_token(login_page)
        except Exception:
            csrf = None

        data = {
            "email": email,
            "password": password,
        }
        if csrf:
            data["csrf_token"] = csrf

        # Submit login form; follow redirects to land on index
        self.client.post(
            "/auth/login",
            data=data,
            name="login",
        )

    def _find_first_dataset_id(self):
        """Return first dataset id found in list page HTML, or None."""
        resp = self.client.get("/dataset/list")
        try:
            import re

            match = re.search(rb"/dataset/(\d+)", resp.content or b"")
            if match:
                return match.group(1).decode("utf-8")
        except Exception:
            return None
        return None

    def on_start(self):
        # Ensure we are authenticated so comment actions succeed
        self._login()

    @task(3)
    def list_datasets(self):
        self.client.get("/dataset/list")

    @task(2)
    def view_dataset_detail(self):
        dataset_id = self._find_first_dataset_id()
        if dataset_id:
            self.client.get(f"/dataset/{dataset_id}")
        else:
            self.client.get("/dataset/list")

    @task(1)
    def get_comments(self):
        dataset_id = self._find_first_dataset_id()
        if dataset_id:
            self.client.get(f"/dataset/{dataset_id}/comments", name="get_comments")
        else:
            self.client.get("/dataset/list")

    @task(1)
    def post_comment(self):
        # Post a comment to validate WI: user can comment a dataset
        dataset_id = self._find_first_dataset_id()
        if not dataset_id:
            self.client.get("/dataset/list")
            return

        # CSRF can be read from any authenticated page with form; use list
        list_resp = self.client.get("/dataset/list")
        try:
            csrf = get_csrf_token(list_resp)
        except Exception:
            csrf = None

        headers = {}
        if csrf:
            headers["X-CSRFToken"] = csrf

        self.client.post(
            f"/dataset/{dataset_id}/comments",
            json={"content": "This is a Locust comment."},
            headers=headers,
            name="post_comment",
        )


class DatasetUser(HttpUser):
    tasks = [DatasetBehavior]
    wait_time = between(3, 7)
    host = get_host_for_locust_testing()
