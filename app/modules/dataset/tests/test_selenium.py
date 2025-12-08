import os
import time

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import close_driver, initialize_driver


def wait_for_page_to_load(driver, timeout=4):
    WebDriverWait(driver, timeout).until(
        lambda driver: driver.execute_script("return document.readyState") == "complete"
    )


def count_datasets(driver, host):
    driver.get(f"{host}/dataset/list")
    wait_for_page_to_load(driver)

    try:
        amount_datasets = len(driver.find_elements(By.XPATH, "//table//tbody//tr"))
    except Exception:
        amount_datasets = 0
    return amount_datasets


def test_upload_dataset():
    driver = initialize_driver()
    # Nombre temporal para el readme
    readme_path = os.path.abspath("dummy_readme.txt")

    try:
        host = get_host_for_selenium_testing()

        # Crear un README temporal para la prueba (Requerido por el validador)
        with open(readme_path, "w") as f:
            f.write("Este es un fichero README de prueba para Selenium.")

        # Open the login page
        driver.get(f"{host}/login")
        wait_for_page_to_load(driver)

        # Find the username and password field and enter the values
        email_field = driver.find_element(By.NAME, "email")
        password_field = driver.find_element(By.NAME, "password")

        email_field.send_keys("user1@example.com")
        password_field.send_keys("1234")

        # Send the form
        password_field.send_keys(Keys.RETURN)
        time.sleep(4)
        wait_for_page_to_load(driver)

        # Count initial datasets
        initial_datasets = count_datasets(driver, host)

        # Open the upload dataset
        driver.get(f"{host}/dataset/upload")
        wait_for_page_to_load(driver)

        # Find basic info and UVL model and fill values
        title_field = driver.find_element(By.NAME, "title")
        title_field.send_keys("Selenium Test Dataset")
        desc_field = driver.find_element(By.NAME, "desc")
        desc_field.send_keys("Description via Selenium")
        tags_field = driver.find_element(By.NAME, "tags")
        tags_field.send_keys("tag1,tag2")

        # Add two authors and fill
        add_author_button = driver.find_element(By.ID, "add_author")
        add_author_button.send_keys(Keys.RETURN)
        wait_for_page_to_load(driver)
        add_author_button.send_keys(Keys.RETURN)
        wait_for_page_to_load(driver)

        name_field0 = driver.find_element(By.NAME, "authors-0-name")
        name_field0.send_keys("Author0")
        affiliation_field0 = driver.find_element(By.NAME, "authors-0-affiliation")
        affiliation_field0.send_keys("Club0")
        orcid_field0 = driver.find_element(By.NAME, "authors-0-orcid")
        orcid_field0.send_keys("0000-0000-0000-0000")

        name_field1 = driver.find_element(By.NAME, "authors-1-name")
        name_field1.send_keys("Author1")
        affiliation_field1 = driver.find_element(By.NAME, "authors-1-affiliation")
        affiliation_field1.send_keys("Club1")

        # Obtén las rutas absolutas de los archivos CSV de ejemplo
        file1_path = os.path.abspath("app/modules/dataset/csv_examples/file1.csv")
        file2_path = os.path.abspath("app/modules/dataset/csv_examples/file2.csv")

        # --- SUBIDA DE FICHEROS CON RE-BÚSQUEDA ---

        # 1. Subir el primer archivo
        dropzone = driver.find_element(By.CLASS_NAME, "dz-hidden-input")
        dropzone.send_keys(file1_path)
        wait_for_page_to_load(driver)

        # 2. Subir el segundo archivo (BUSCAMOS EL ELEMENTO DE NUEVO)
        dropzone = driver.find_element(By.CLASS_NAME, "dz-hidden-input")
        dropzone.send_keys(file2_path)
        wait_for_page_to_load(driver)

        # 3. Subir el README (BUSCAMOS EL ELEMENTO DE NUEVO)
        dropzone = driver.find_element(By.CLASS_NAME, "dz-hidden-input")
        dropzone.send_keys(readme_path)
        wait_for_page_to_load(driver)

        # ---------------------------------------------

        # Check I agree and send form
        check = driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        time.sleep(1)  # Pequeña espera para UI

        upload_btn = driver.find_element(By.ID, "upload_button")

        if upload_btn.is_enabled():
            upload_btn.send_keys(Keys.RETURN)

        wait_for_page_to_load(driver)
        time.sleep(2)  # Force wait time para redirección

        # Diagnóstico de errores si no redirige
        if driver.current_url != f"{host}/dataset/list":
            try:
                error_elem = driver.find_element(By.ID, "upload_error")
                if error_elem.is_displayed():
                    print(f"DEBUG: Error mostrado en UI: {error_elem.text}")
            except NoSuchElementException:
                print(f"DEBUG: No redirigió y no se encontró mensaje de error. URL: {driver.current_url}")

        assert driver.current_url == f"{host}/dataset/list", "Test failed! No se redirigió a la lista de datasets."

        # Count final datasets
        final_datasets = count_datasets(driver, host)
        assert final_datasets == initial_datasets + 1, "Test failed! El contador de datasets no incrementó."

        print("Test passed!")

    finally:
        # Limpieza
        if os.path.exists(readme_path):
            os.remove(readme_path)
        # Close the browser
        close_driver(driver)


if __name__ == "__main__":
    test_upload_dataset()
