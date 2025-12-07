from locust import HttpUser, TaskSet, task, between

from core.environment.host import get_host_for_locust_testing
from core.locust.common import fake, get_csrf_token


class CommentOnDatasetBehavior(TaskSet):
    # ---------- Datos de prueba (ajusta con DOIs reales) ----------
    DATASET_DOIS = [
        "10.seed/concept.1.v2/",
        "10.seed/concept.2.v1/",
    ]
    DATASET_ID = [3, 4]

    def on_start(self):
        self.login()

    # ---------- Login reutilizando el módulo auth ----------

    def login(self):
        response = self.client.get("/login")
        if response.status_code != 200 or "Login" not in response.text:
            print(f"Unexpected login page status: {response.status_code}")
            return

        csrf_token = get_csrf_token(response)

        email = "user1@example.com"
        password = "1234"

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
            print(f"Login failed in comments locust: {response.status_code}")
            return

    # ---------- Tareas sobre la vista de dataset (incluye comments) ----------

    @task
    def view_dataset_page(self):
        doi = fake.random_element(elements=self.DATASET_DOIS)
        path = f"/doi/{doi}/"
        response = self.client.get(path)
        if response.status_code != 200:
            print(f"Failed to load dataset page {path}: {response.status_code}")

    @task
    def post_comment_on_dataset(self):
        dataset_id = fake.random_element(elements=self.DATASET_ID)
        path = f"/dataset/{dataset_id}"

        response = self.client.get(path)
        if response.status_code != 200:
            print(f"Failed to get dataset page for commenting {path}: {response.status_code}")
            return

        try:
            csrf_token = get_csrf_token(response)
        except ValueError:
            print("CSRF token not found on dataset view page")
            return

        content = fake.text(max_nb_chars=200)

        response = self.client.post(
            path,
            data={
                "content": content,
                "csrf_token": csrf_token,
            },
            allow_redirects=True,
        )

        if response.status_code not in (200, 302):
            print(f"Post comment failed on {path}: {response.status_code}")


class CommentsUser(HttpUser):
    tasks = [CommentOnDatasetBehavior]
    wait_time = between(5, 9)
    host = get_host_for_locust_testing()
