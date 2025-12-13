from locust import HttpUser, TaskSet, between, task

from core.environment.host import get_host_for_locust_testing
from core.locust.common import get_csrf_token

# Columnas requeridas por validator.py
REQUIRED_COLUMNS = [
    "_temp_mean",
    "_temp_max",
    "_temp_min",
    "_cloud_cover",
    "_global_radiation",
    "_humidity",
    "_pressure",
    "_precipitation",
    "_sunshine",
    "_wind_gust",
    "_wind_speed",
]


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
        self.ensure_logged_out()
        self.login()

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

    def ensure_logged_out(self):
        self.client.get("/logout")

    def login(self):
        response = self.client.get("/login")
        if response.status_code != 200:
            print(f"Login GET Failed: {response.status_code}")
            return

        csrf_token = get_csrf_token(response)

        response = self.client.post(
            "/login",
            data={
                "email": "user1@example.com",
                "password": "1234",
                "csrf_token": csrf_token,
            },
            allow_redirects=True,
        )

        if response.status_code not in (200, 302):
            print(f"Login POST Failed: {response.status_code}")

    @task
    def upload_dataset_flow(self):
        # 1. Obtener Token CSRF fresco para el formulario
        response = self.client.get("/dataset/upload")
        if response.status_code != 200:
            print(f"Upload Page Failed: {response.status_code}")
            return
        csrf_token = get_csrf_token(response)

        # -------------------------------------------------------
        # 2. Subir Archivo 1: CSV (AJAX)
        # -------------------------------------------------------
        header = "DATE," + ",".join(REQUIRED_COLUMNS)
        row = "2025-01-01," + ",".join(["0"] * len(REQUIRED_COLUMNS))
        csv_content = f"{header}\n{row}"

        files_csv = {"file": ("locust_data.csv", csv_content, "text/csv")}
        headers_ajax = {"X-CSRFToken": csrf_token}

        upload_resp_csv = self.client.post(
            "/dataset/file/upload", files=files_csv, headers=headers_ajax, name="/dataset/file/upload (CSV)"
        )
        if upload_resp_csv.status_code != 200:
            print(f"CSV Upload Failed: {upload_resp_csv.status_code}")
            return

        # Recuperamos el nombre real con el que se guardó en el servidor
        server_filename_csv = upload_resp_csv.json().get("filename")

        # -------------------------------------------------------
        # 3. Subir Archivo 2: README (AJAX)
        # -------------------------------------------------------
        readme_content = "Este es un dataset de prueba generado por Locust."
        files_readme = {"file": ("README.md", readme_content, "text/markdown")}

        upload_resp_readme = self.client.post(
            "/dataset/file/upload", files=files_readme, headers=headers_ajax, name="/dataset/file/upload (README)"
        )
        if upload_resp_readme.status_code != 200:
            print(f"README Upload Failed: {upload_resp_readme.status_code}")
            return

        server_filename_readme = upload_resp_readme.json().get("filename")

        # -------------------------------------------------------
        # 4. Enviar Formulario Final (Con ambos ficheros)
        # -------------------------------------------------------
        payload = {
            "csrf_token": csrf_token,
            "title": "Locust Load Test",
            "desc": "Automated load test description",
            "publication_type": "none",
            "tags": "loadtest",
            "version_number": "v1.0.0",
            "authors-0-name": "Locust User",
            "authors-0-affiliation": "Load Testing",
            "agreeCheckbox": "y",
            # --- Fichero 1: CSV ---
            "feature_models-0-filename": server_filename_csv,
            "feature_models-0-title": "CSV Data",
            "feature_models-0-desc": "Datos meteorológicos",
            "feature_models-0-publication_type": "none",
            "feature_models-0-version": "v1.0.0",
            "feature_models-0-tags": "data",
            # --- Fichero 2: README ---
            # Es obligatorio enviarlo como un segundo 'feature_model' en el form
            "feature_models-1-filename": server_filename_readme,
            "feature_models-1-title": "Readme",
            "feature_models-1-desc": "Documentación",
            "feature_models-1-publication_type": "none",
            "feature_models-1-version": "v1.0.0",
            "feature_models-1-tags": "doc",
        }

        final_resp = self.client.post("/dataset/upload", data=payload, name="/dataset/upload (Submit)")

        if final_resp.status_code not in (200, 302):
            print(f"Form Submit Failed: {final_resp.status_code} - {final_resp.text}")


class DatasetUser(HttpUser):
    tasks = [DatasetBehavior]
    wait_time = between(3, 7)
    host = get_host_for_locust_testing()
