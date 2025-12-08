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
    def on_start(self):
        self.ensure_logged_out()
        self.login()

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
    wait_time = between(2, 5)
    host = get_host_for_locust_testing()
