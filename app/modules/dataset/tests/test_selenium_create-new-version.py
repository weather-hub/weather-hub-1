import os
import re
import time
from urllib.parse import urljoin

import pytest
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import close_driver, initialize_driver


def count_datasets(driver, host):
    driver.get(f"{host}/dataset/list")
    wait_for_page_to_load(driver)

    try:
        amount_datasets = len(driver.find_elements(By.XPATH, "//table//tbody//tr"))
    except Exception:
        amount_datasets = 0
    return amount_datasets


def wait_for_page_to_load(driver, timeout=10):
    """Espera a que el documento esté completamente cargado (readyState=complete)."""
    try:
        WebDriverWait(driver, timeout).until(lambda d: d.execute_script("return document.readyState") == "complete")
    except TimeoutException:
        print("WARN: La página tardó demasiado en cargar document.readyState.")


def login_user(driver, base_url, email="user1@example.com", password="1234"):
    """Loguea al usuario asegurando que estamos en la página correcta."""
    login_url = f"{base_url}/login"
    driver.get(login_url)
    wait_for_page_to_load(driver)

    if "/login" not in driver.current_url and "/login" not in driver.title.lower():
        driver.get(f"{base_url}/logout")
        wait_for_page_to_load(driver)
        driver.get(login_url)

    try:
        email_field = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.NAME, "email")))
    except TimeoutException:
        raise

    password_field = driver.find_element(By.NAME, "password")

    email_field.clear()
    email_field.send_keys(email)
    password_field.clear()
    password_field.send_keys(password)

    submit_btn = driver.find_element(By.ID, "submit")
    submit_btn.click()

    WebDriverWait(driver, 10).until(lambda d: "/login" not in d.current_url)


def navigate_to_new_version_page(driver, base_url):
    driver.get(f"{base_url}/dataset/list")
    wait_for_page_to_load(driver)

    try:
        first_ds_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//table//tbody//tr[1]//td[1]//a"))
        )
        first_ds_link.click()
    except TimeoutException:
        raise AssertionError("No hay datasets listados. Ejecuta los seeders primero.")

    wait_for_page_to_load(driver)

    try:
        new_version_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(@href, '/new-version') or contains(text(), 'New version')]")
            )
        )
        new_version_btn.click()
    except TimeoutException:
        raise AssertionError("No se encontró el botón 'New version'.")

    wait_for_page_to_load(driver)


def submit_form(driver):
    """
    Marca el checkbox 'agree' usando SPACE y pulsa el botón de subida.
    """
    try:
        agree_checkbox = driver.find_element(By.ID, "agreeCheckbox")
        driver.execute_script("arguments[0].scrollIntoView();", agree_checkbox)
        time.sleep(0.5)

        if not agree_checkbox.is_selected():
            agree_checkbox.send_keys(Keys.SPACE)
            time.sleep(0.5)

    except NoSuchElementException:
        print("WARN: No se encontró 'agreeCheckbox'.")

    try:
        upload_btn = driver.find_element(By.ID, "upload_button")
        WebDriverWait(driver, 2).until(lambda d: upload_btn.is_enabled())
        driver.execute_script("arguments[0].scrollIntoView();", upload_btn)
        upload_btn.send_keys(Keys.RETURN)

    except (NoSuchElementException, TimeoutException):
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            driver.execute_script("arguments[0].disabled = false;", btn)
            btn.click()
        except Exception:
            raise AssertionError("No se pudo enviar el formulario.")


def upload_to_dropzone(driver, file_path):
    """
    Sube un fichero al componente Dropzone buscando el input oculto
    y aplicando las esperas exactas definidas en el ejemplo funcional ('La Biblia').
    """
    dropzone = driver.find_element(By.CLASS_NAME, "dz-hidden-input")
    dropzone.send_keys(file_path)
    wait_for_page_to_load(driver)
    time.sleep(1)


# ---------------------------------------


class TestCreateVersionE2E:
    def setup_method(self):
        self.driver = initialize_driver()
        self.host = get_host_for_selenium_testing()

    def teardown_method(self):
        close_driver(self.driver)

    def test_required_fields_validation_title_empty(self):
        login_user(self.driver, self.host)
        navigate_to_new_version_page(self.driver, self.host)

        title_input = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.NAME, "title")))
        title_input.clear()

        check = self.driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        time.sleep(1)

        upload_btn = self.driver.find_element(By.ID, "upload_button")
        if upload_btn.is_enabled():
            upload_btn.send_keys(Keys.RETURN)

        msg = title_input.get_attribute("validationMessage")
        assert msg, "El navegador debería mostrar un error de campo requerido en el Título"

    def test_required_fields_validation_version_bad_entry(self):
        """Sad Path: Versión con formato incorrecto."""
        login_user(self.driver, self.host)
        navigate_to_new_version_page(self.driver, self.host)

        version_input = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.NAME, "version_number"))
        )
        version_input.clear()
        version_input.send_keys("v1")

        check = self.driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        time.sleep(1)

        upload_btn = self.driver.find_element(By.ID, "upload_button")
        if upload_btn.is_enabled():
            upload_btn.send_keys(Keys.RETURN)

        error_div = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, "upload_error")))

        assert (
            "version_number" in error_div.text and "formato debe ser vX.Y.Z" in error_div.text
        ), f"El mensaje de error no es el esperado. Se obtuvo: {error_div.text}"

    def test_sin_feature_model_version_minor(self):
        """Sad Path: Versión sin parte menor (Validation Error)."""
        login_user(self.driver, self.host)
        navigate_to_new_version_page(self.driver, self.host)

        check = self.driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        time.sleep(1)

        upload_btn = self.driver.find_element(By.ID, "upload_button")
        if upload_btn.is_enabled():
            upload_btn.send_keys(Keys.RETURN)

        try:
            error_div = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, "upload_error")))
            assert (
                "Upload error: The new version number must be different from the original." in error_div.text
                or "version" in error_div.text.lower()
            ), f"El mensaje de error no es el esperado. Se obtuvo: '{error_div.text}'"

        except TimeoutException:
            pytest.fail("El mensaje de error ('upload_error') no apareció en el tiempo esperado.")

        assert "/dataset/list" not in self.driver.current_url, "No debería redirigir en caso de error."

    def test_invalid_feature_model_version_format(self):
        """Sad Path: Formato de versión incorrecto en el fichero."""
        login_user(self.driver, self.host)
        navigate_to_new_version_page(self.driver, self.host)

        file_path = os.path.abspath("test_sad_path.csv")
        with open(file_path, "w") as f:
            f.write("feature, value\nroot, 1")

        try:
            version_field = self.driver.find_element(By.NAME, "version_number")
            version_field.clear()
            version_field.send_keys("v2.0.0")

            upload_to_dropzone(self.driver, file_path)

            try:
                show_info_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "info-button"))
                )
                show_info_btn.click()

                fm_version = WebDriverWait(self.driver, 5).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name$='uvl_version']"))
                )
            except TimeoutException:
                raise AssertionError("No se encontraron los campos de metadatos del fichero.")

            fm_version.clear()
            fm_version.send_keys("v1")

            check = self.driver.find_element(By.ID, "agreeCheckbox")
            check.send_keys(Keys.SPACE)
            time.sleep(1)

            upload_btn = self.driver.find_element(By.ID, "upload_button")
            if upload_btn.is_enabled():
                upload_btn.send_keys(Keys.RETURN)

            error_div = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, "upload_error")))

            error_text = error_div.text.lower()
            assert (
                "error" in error_text or "version" in error_text
            ), f"Se esperaba un mensaje de error de validación, pero se obtuvo: '{error_div.text}'"

            assert "/dataset/list" not in self.driver.current_url

        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    def test_happy_path_create_new_version(self):
        """Happy Path: Crear versión con éxito (usando Dropzone Helper)."""
        login_user(self.driver, self.host)
        navigate_to_new_version_page(self.driver, self.host)

        new_version_url = self.driver.current_url

        title_field = self.driver.find_element(By.NAME, "title")
        title_field.clear()
        title_field.send_keys("Selenium Version Update")

        desc_field = self.driver.find_element(By.NAME, "desc")
        desc_field.clear()
        desc_field.send_keys("Description updated via Selenium")

        version_field = self.driver.find_element(By.NAME, "version_number")

        current_version_str = version_field.get_attribute("value")
        try:
            major_version_num = int(current_version_str.lstrip("v").split(".")[0])
            new_version_str = f"v{major_version_num + 1}.0.0"
        except (ValueError, IndexError) as e:
            pytest.fail(
                f"No se pudo calcular la siguiente versión mayor a partir de '{current_version_str}'. Error: {e}"
            )

        version_field.clear()
        version_field.send_keys(new_version_str)

        publication_type_field = self.driver.find_element(By.NAME, "publication_type")
        publication_type_field.send_keys("REGIONAL")

        file_path = os.path.abspath("test_file_selenium.txt")
        with open(file_path, "w") as f:
            f.write("feature, value\nroot, 1")

        try:
            upload_to_dropzone(self.driver, file_path)

            show_info_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "info-button"))
            )
            show_info_btn.click()

            file_version_input = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name$='uvl_version']"))
            )
            file_version_input.clear()
            file_version_input.send_keys("v1.0.0")

            check = self.driver.find_element(By.ID, "agreeCheckbox")
            check.send_keys(Keys.SPACE)
            time.sleep(1)

            upload_btn = self.driver.find_element(By.ID, "upload_button")
            if upload_btn.is_enabled():
                upload_btn.send_keys(Keys.RETURN)

            try:
                WebDriverWait(self.driver, 15).until(EC.url_changes(new_version_url))
            except TimeoutException:
                error_message = "El test falló. No se redirigió tras crear la versión."
                try:
                    error_elem = self.driver.find_element(By.ID, "upload_error")
                    if error_elem.is_displayed():
                        error_message += f"\nError en UI: {error_elem.text}"
                except NoSuchElementException:
                    error_message += "\nNo se encontró un elemento de error visible en la página."

                pytest.fail(error_message)

            final_url = self.driver.current_url
            assert "dataset" in final_url or "doi" in final_url, f"Redirección a una URL inesperada: {final_url}"

        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    def test_happy_path_create_minor_version(self):
        """Happy Path: Crear una versión menor con éxito (sin subir ficheros)."""
        login_user(self.driver, self.host)
        navigate_to_new_version_page(self.driver, self.host)

        new_version_url = self.driver.current_url

        title_field = self.driver.find_element(By.NAME, "title")
        title_field.clear()
        title_field.send_keys("Selenium Minor Version Update")

        version_field = self.driver.find_element(By.NAME, "version_number")

        current_version_str = version_field.get_attribute("value")
        try:
            parts = current_version_str.lstrip("v").split(".")
            if len(parts) < 2:
                raise ValueError("Formato de versión incompleto.")
            major = int(parts[0])
            minor = int(parts[1])
            new_version_str = f"v{major}.{minor + 1}.0"
        except (ValueError, IndexError) as e:
            pytest.fail(
                f"No se pudo calcular la siguiente versión menor a partir de '{current_version_str}'. Error: {e}"
            )

        version_field.clear()
        version_field.send_keys(new_version_str)

        check = self.driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        time.sleep(1)

        upload_btn = self.driver.find_element(By.ID, "upload_button")
        if upload_btn.is_enabled():
            upload_btn.send_keys(Keys.RETURN)

        try:
            WebDriverWait(self.driver, 15).until(EC.url_changes(new_version_url))
        except TimeoutException:
            error_message = "El test de versión menor falló. No se redirigió tras crear la versión."
            try:
                error_elem = self.driver.find_element(By.ID, "upload_error")
                if error_elem.is_displayed():
                    error_message += f"\nError en UI: {error_elem.text}"
            except NoSuchElementException:
                pass
            pytest.fail(error_message)

        final_url = self.driver.current_url
        assert "dataset" in final_url or "doi" in final_url, f"Redirección a una URL inesperada: {final_url}"

    def test_sad_path_minor_version_no_change(self):
        """Sad Path: Falla al crear versión menor porque el número de versión no cambia."""
        login_user(self.driver, self.host)
        navigate_to_new_version_page(self.driver, self.host)

        title_field = self.driver.find_element(By.NAME, "title")
        title_field.clear()
        title_field.send_keys("Attempt to update with same version")

        check = self.driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        time.sleep(1)

        upload_btn = self.driver.find_element(By.ID, "upload_button")
        if upload_btn.is_enabled():
            upload_btn.send_keys(Keys.RETURN)

        try:
            error_div = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, "upload_error")))
            assert (
                "number must be different from the original" in error_div.text
            ), f"El mensaje de error no es el esperado. Se obtuvo: '{error_div.text}'"
        except TimeoutException:
            pytest.fail("El mensaje de error por versión no cambiada no apareció en el tiempo esperado.")

        assert "/new-version" in self.driver.current_url, "No debería redirigir en caso de error."

    def test_sad_path_minor_version_major_increment(self):
        """Sad Path: Falla al intentar crear una versión menor incrementando el número mayor."""
        login_user(self.driver, self.host)
        navigate_to_new_version_page(self.driver, self.host)

        version_field = self.driver.find_element(By.NAME, "version_number")
        current_version_str = version_field.get_attribute("value")

        try:
            parts = current_version_str.lstrip("v").split(".")
            if len(parts) < 2:
                raise ValueError("Formato de versión incompleto.")
            major = int(parts[0])
            minor = int(parts[1])
            new_version_str = f"v{major + 1}.{minor}.0"
        except (ValueError, IndexError) as e:
            pytest.fail(
                f"No se pudo calcular la siguiente versión (major inc) a partir de '{current_version_str}'. Error: {e}"
            )

        version_field.clear()
        version_field.send_keys(new_version_str)

        check = self.driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        time.sleep(1)

        upload_btn = self.driver.find_element(By.ID, "upload_button")
        if upload_btn.is_enabled():
            upload_btn.send_keys(Keys.RETURN)

        try:
            error_div = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, "upload_error")))
            assert (
                "minor or patch version must be increased" in error_div.text
            ), f"El mensaje de error no es el esperado. Se obtuvo: '{error_div.text}'"
        except TimeoutException:
            pytest.fail("El mensaje de error por incremento mayor en versión menor no apareció.")

        assert "/new-version" in self.driver.current_url, "No debería redirigir en caso de error."

    def test_sad_path_minor_version_large_increment(self):
        """Sad Path: Falla al intentar crear una versión menor incrementando el minor en más de uno."""
        login_user(self.driver, self.host)
        navigate_to_new_version_page(self.driver, self.host)

        version_field = self.driver.find_element(By.NAME, "version_number")
        current_version_str = version_field.get_attribute("value")

        try:
            parts = current_version_str.lstrip("v").split(".")
            if len(parts) < 2:
                raise ValueError("Formato de versión incompleto.")
            major = int(parts[0])
            minor = int(parts[1])
            new_version_str = f"v{major}.{minor + 2}.0"
        except (ValueError, IndexError) as e:
            pytest.fail(
                f"No se pudo calcular la siguiente versión (large inc) a partir de '{current_version_str}'. Error: {e}"
            )

        version_field.clear()
        version_field.send_keys(new_version_str)

        check = self.driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        time.sleep(1)

        upload_btn = self.driver.find_element(By.ID, "upload_button")
        if upload_btn.is_enabled():
            upload_btn.send_keys(Keys.RETURN)

        try:
            error_div = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, "upload_error")))
            assert (
                "can only be increased by one at a time" in error_div.text
            ), f"El mensaje de error no es el esperado. Se obtuvo: '{error_div.text}'"
        except TimeoutException:
            pytest.fail("El mensaje de error por incremento grande en versión menor no apareció.")

        assert "/new-version" in self.driver.current_url, "No debería redirigir en caso de error."

    def test_sad_path_invalid_publication_doi(self):
        """Sad Path: Falla si el Publication DOI no es una URL válida."""
        login_user(self.driver, self.host)
        navigate_to_new_version_page(self.driver, self.host)

        doi_field = self.driver.find_element(By.NAME, "publication_doi")
        doi_field.clear()
        doi_field.send_keys("esto-no-es-una-url")

        version_field = self.driver.find_element(By.NAME, "version_number")
        current_version_str = version_field.get_attribute("value")
        parts = current_version_str.lstrip("v").split(".")
        new_version_str = f"v{parts[0]}.{int(parts[1]) + 1}.0"
        version_field.clear()
        version_field.send_keys(new_version_str)

        check = self.driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        time.sleep(1)

        upload_btn = self.driver.find_element(By.ID, "upload_button")
        if upload_btn.is_enabled():
            upload_btn.send_keys(Keys.RETURN)

        try:
            error_div = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, "upload_error")))
            assert (
                "Invalid URL" in error_div.text
            ), f"El mensaje de error para DOI inválido no es el esperado. Se obtuvo: '{error_div.text}'"
        except TimeoutException:
            pytest.fail("No apareció el mensaje de error para Publication DOI inválido.")

    def test_sad_path_empty_description(self):
        """Sad Path: Falla si la descripción está vacía."""
        login_user(self.driver, self.host)
        navigate_to_new_version_page(self.driver, self.host)

        desc_field = self.driver.find_element(By.NAME, "desc")
        desc_field.clear()

        check = self.driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        time.sleep(1)

        upload_btn = self.driver.find_element(By.ID, "upload_button")
        if upload_btn.is_enabled():
            upload_btn.send_keys(Keys.RETURN)

        msg = desc_field.get_attribute("validationMessage")
        assert msg, "El navegador debería mostrar un error de campo requerido en la Descripción"

    def test_workflow_create_major_and_navigate_to_previous(self):
        """Workflow: Crea una versión mayor y luego navega a la versión anterior desde el historial."""
        login_user(self.driver, self.host)
        navigate_to_new_version_page(self.driver, self.host)

        original_version_field = self.driver.find_element(By.NAME, "version_number")
        original_version_str = original_version_field.get_attribute("value")
        original_title = self.driver.find_element(By.NAME, "title").get_attribute("value")

        new_version_url = self.driver.current_url
        major_version_num = int(original_version_str.lstrip("v").split(".")[0])
        new_version_str = f"v{major_version_num + 1}.0.0"
        original_version_field.clear()
        original_version_field.send_keys(new_version_str)

        file_path = os.path.abspath("test_workflow_file.txt")
        with open(file_path, "w") as f:
            f.write("feature, value\nroot, 1")

        try:
            upload_to_dropzone(self.driver, file_path)
            check = self.driver.find_element(By.ID, "agreeCheckbox")
            check.send_keys(Keys.SPACE)
            upload_btn = self.driver.find_element(By.ID, "upload_button")
            if upload_btn.is_enabled():
                upload_btn.send_keys(Keys.RETURN)

            WebDriverWait(self.driver, 15).until(EC.url_changes(new_version_url))
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

        self.driver.get(f"{self.host}/dataset/list")
        wait_for_page_to_load(self.driver)

        new_dataset_link = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, original_title))
        )
        new_dataset_link.click()
        wait_for_page_to_load(self.driver)

        try:
            previous_version_link = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, original_version_str))
            )
            previous_version_link.click()
            wait_for_page_to_load(self.driver)
        except TimeoutException:
            pytest.fail(f"No se encontró el enlace a la versión anterior '{original_version_str}' en el historial.")

        final_title = self.driver.find_element(By.TAG_NAME, "h1").text
        assert original_title in final_title, "El título de la página no coincide con el del dataset original."

    def test_workflow_create_minor_and_navigate_to_previous(self):
        """Workflow: Crea una versión menor y navega a la versión previa, verificando que la URL base no cambia."""
        login_user(self.driver, self.host)
        navigate_to_new_version_page(self.driver, self.host)

        new_version_url = self.driver.current_url
        version_field = self.driver.find_element(By.NAME, "version_number")
        original_version_str = version_field.get_attribute("value")

        try:
            parts = original_version_str.lstrip("v").split(".")
            if len(parts) < 2:
                raise ValueError("Formato de versión incompleto.")
            major = int(parts[0])
            minor = int(parts[1])
            new_version_str = f"v{major}.{minor + 1}.0"
        except (ValueError, IndexError) as e:
            pytest.fail(
                f"No se pudo calcular la siguiente versión menor a partir de '{original_version_str}'. Error: {e}"
            )

        version_field.clear()
        version_field.send_keys(new_version_str)

        check = self.driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        upload_btn = self.driver.find_element(By.ID, "upload_button")
        if upload_btn.is_enabled():
            upload_btn.send_keys(Keys.RETURN)

        WebDriverWait(self.driver, 15).until(EC.url_changes(new_version_url))

        cite_version_element = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//small[contains(text(), 'Cite this specific version')]"))
        )
        assert (
            new_version_str in cite_version_element.text
        ), f"La página no se actualizó a la nueva versión menor. Se esperaba '{new_version_str}' en el texto de cita."

        try:
            previous_version_link = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, original_version_str))
            )
            previous_version_link.click()
            wait_for_page_to_load(self.driver)
        except TimeoutException:
            pytest.fail(f"No se encontró el enlace a la versión anterior '{original_version_str}' en el historial.")
        latest_version_cite_element = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//small[contains(text(), 'Cite this specific version')]"))
        )
        assert (
            new_version_str in latest_version_cite_element.text
        ), "Al navegar a una versión minor anterior, se debe permanecer en la versión más reciente."


def open_first_dataset_new_version_page(driver, base_url):
    driver.get(urljoin(base_url, "/dataset/list"))
    wait_for_page_to_load(driver)

    first_row = WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.XPATH, "//table//tbody//tr[1]")))
    dataset_link = first_row.find_element(By.XPATH, ".//td[1]//a")
    dataset_link.click()
    wait_for_page_to_load(driver)

    current_url = driver.current_url
    try:
        new_version_link = WebDriverWait(driver, 2).until(
            EC.presence_of_element_located(
                (By.XPATH, "//a[contains(@href, '/new-version') or contains(text(), 'New Version')]")
            )
        )
        new_version_link.click()
        wait_for_page_to_load(driver)
    except Exception:
        m = re.search(r"/dataset/(\d+)", current_url)
        if not m:
            raise RuntimeError("Could not determine dataset_id for new version route.")
        dataset_id = int(m.group(1))
        driver.get(urljoin(base_url, f"/dataset/{dataset_id}/new-version"))
        wait_for_page_to_load(driver)
