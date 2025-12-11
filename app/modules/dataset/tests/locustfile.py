from locust import HttpUser, TaskSet, between, task

from core.environment.host import get_host_for_locust_testing
from core.locust.common import get_csrf_token


class DatasetBehavior(TaskSet):
    def on_start(self):
        # Warm up: hit list page to establish session and capture CSRF
        response = self.client.get("/dataset/list")
        get_csrf_token(response)

    @task(3)
    def list_datasets(self):
        self.client.get("/dataset/list")

    @task(2)
    def view_dataset_detail(self):
        # Try to access the first dataset detail if present
        # Fallback to list page if no id can be inferred
        resp = self.client.get("/dataset/list")
        _ = get_csrf_token(resp)
        # naive extraction of first dataset link id if server renders links like /dataset/<id>
        dataset_id = None
        try:
            # very lightweight heuristic to find an id in the HTML
            import re

            match = re.search(rb"/dataset/(\d+)", resp.content or b"")
            if match:
                dataset_id = match.group(1).decode("utf-8")
        except Exception:
            dataset_id = None

        if dataset_id:
            self.client.get(f"/dataset/{dataset_id}")
        else:
            # If we can't find a dataset id, just revisit list
            self.client.get("/dataset/list")

    @task(1)
    def open_upload_form(self):
        response = self.client.get("/dataset/upload")
        get_csrf_token(response)

    @task(1)
    def post_comment_if_possible(self):
        # Attempt to post a comment on the first dataset if logged-in flow permits.
        # If the app redirects unauthenticated users, this still exercises the endpoint.
        list_resp = self.client.get("/dataset/list")
        csrf = get_csrf_token(list_resp)

        dataset_id = None
        try:
            import re

            match = re.search(rb"/dataset/(\d+)", list_resp.content or b"")
            if match:
                dataset_id = match.group(1).decode("utf-8")
        except Exception:
            dataset_id = None

        if dataset_id:
            headers = {}
            if csrf:
                headers["X-CSRFToken"] = csrf
            self.client.post(
                f"/dataset/{dataset_id}/comments",
                json={"content": "Locust test comment"},
                headers=headers,
                name="post_comment",
            )
        else:
            # Exercise comments list even if we cannot post
            self.client.get("/dataset/list")


class DatasetUser(HttpUser):
    tasks = [DatasetBehavior]
    wait_time = between(5, 9)
    host = get_host_for_locust_testing()
