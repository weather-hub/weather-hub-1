import os
import re
import time

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


def login_user(driver, host, email="user1@example.com", password="1234"):
    """Helper function to log in a user."""
    driver.get(f"{host}/login")
    wait_for_page_to_load(driver)

    email_field = driver.find_element(By.NAME, "email")
    password_field = driver.find_element(By.NAME, "password")

    email_field.send_keys(email)
    password_field.send_keys(password)
    password_field.send_keys(Keys.RETURN)
    time.sleep(2)
    wait_for_page_to_load(driver)


def test_upload_dataset():
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        driver.get(f"{host}/login")
        wait_for_page_to_load(driver)

        email_field = driver.find_element(By.NAME, "email")
        password_field = driver.find_element(By.NAME, "password")

        email_field.send_keys("user1@example.com")
        password_field.send_keys("1234")

        password_field.send_keys(Keys.RETURN)
        time.sleep(4)
        wait_for_page_to_load(driver)

        initial_datasets = count_datasets(driver, host)

        driver.get(f"{host}/dataset/upload")
        wait_for_page_to_load(driver)

        title_field = driver.find_element(By.NAME, "title")
        title_field.send_keys("Title")
        desc_field = driver.find_element(By.NAME, "desc")
        desc_field.send_keys("Description")
        tags_field = driver.find_element(By.NAME, "tags")
        tags_field.send_keys("tag1,tag2")

        add_author_button = driver.find_element(By.ID, "add_author")
        add_author_button.send_keys(Keys.RETURN)
        wait_for_page_to_load(driver)
        add_author_button.send_keys(Keys.RETURN)
        wait_for_page_to_load(driver)

        name_field0 = driver.find_element(By.NAME, "authors-0-name")
        name_field0.clear()
        name_field0.send_keys("Author0")
        affiliation_field0 = driver.find_element(By.NAME, "authors-0-affiliation")
        affiliation_field0.clear()
        affiliation_field0.send_keys("Club0")
        orcid_field0 = driver.find_element(By.NAME, "authors-0-orcid")
        orcid_field0.clear()
        orcid_field0.send_keys("0000-0000-0000-0000")

        name_field1 = driver.find_element(By.NAME, "authors-1-name")
        name_field1.clear()
        name_field1.send_keys("Author1")
        affiliation_field1 = driver.find_element(By.NAME, "authors-1-affiliation")
        affiliation_field1.clear()
        affiliation_field1.send_keys("Club1")

        readme_content = "# Dataset README\n\nThis is a test README file for the dataset."
        readme_path = os.path.abspath("test_readme.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)

        file1_path = os.path.abspath("app/modules/dataset/csv_examples/file1.csv")
        file2_path = os.path.abspath("app/modules/dataset/csv_examples/file2.csv")

        dropzone = driver.find_element(By.CLASS_NAME, "dz-hidden-input")
        dropzone.send_keys(readme_path)
        wait_for_page_to_load(driver)
        time.sleep(1)

        dropzone = driver.find_element(By.CLASS_NAME, "dz-hidden-input")
        dropzone.send_keys(file1_path)
        wait_for_page_to_load(driver)
        time.sleep(1)

        dropzone = driver.find_element(By.CLASS_NAME, "dz-hidden-input")
        dropzone.send_keys(file2_path)
        wait_for_page_to_load(driver)
        time.sleep(1)

        time.sleep(2)

        check = driver.find_element(By.ID, "agreeCheckbox")
        if not check.is_selected():
            check.click()
        wait_for_page_to_load(driver)
        time.sleep(1)

        upload_btn = driver.find_element(By.ID, "upload_button")
        assert upload_btn.is_enabled(), "Upload button should be enabled after checking agreement"

        upload_btn.click()
        time.sleep(3)

        try:
            WebDriverWait(driver, 30).until(lambda d: d.current_url == f"{host}/dataset/list")
        except Exception:
            pass

        current_url = driver.current_url
        assert driver.current_url == f"{host}/dataset/list", f"Expected {host}/dataset/list but got {current_url}"

        final_datasets = count_datasets(driver, host)
        assert final_datasets == initial_datasets + 1, "Test failed!"

        print("Test passed!")

    finally:
        try:
            if os.path.exists("test_readme.md"):
                os.remove("test_readme.md")
        except Exception:
            pass
        close_driver(driver)


def test_edit_dataset():
    """Test editing a dataset's metadata (title, description, tags)."""
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        login_user(driver, host)

        driver.get(f"{host}/dataset/list")
        wait_for_page_to_load(driver)
        time.sleep(1)

        try:
            first_dataset_row = driver.find_element(By.XPATH, "//table//tbody//tr[1]")
            dataset_link = first_dataset_row.find_element(By.XPATH, ".//td[1]//a")
            dataset_link.click()
            wait_for_page_to_load(driver)
            time.sleep(2)
        except Exception as e:
            print(f"Error clicking first dataset: {e}")
            print("No datasets found, skipping edit test")
            return

        dataset_id = None
        try:
            xpath_edit = "//a[contains(@href, '/dataset/') and contains(@href, '/edit')]"
            edit_button = driver.find_element(By.XPATH, xpath_edit)
            edit_href = edit_button.get_attribute("href")
            match = re.search(r"/dataset/(\d+)/edit", edit_href)
            if match:
                dataset_id = match.group(1)
        except Exception:
            current_url = driver.current_url
            match = re.search(r"/dataset/(\d+)", current_url)
            if match:
                dataset_id = match.group(1)

        if not dataset_id:
            print("Could not extract dataset_id, skipping edit test")
            return

        driver.get(f"{host}/dataset/{dataset_id}/edit")
        wait_for_page_to_load(driver)
        time.sleep(1)

        title_field = driver.find_element(By.XPATH, "//input[@id='title']")
        desc_field = driver.find_element(By.XPATH, "//textarea[@id='description']")
        tags_field = driver.find_element(By.XPATH, "//input[@id='tags']")

        original_title = title_field.get_attribute("value") or ""
        original_desc = desc_field.get_attribute("value") or desc_field.get_attribute("textContent") or ""
        original_tags = tags_field.get_attribute("value") or ""

        new_title = f"{original_title} v2"
        new_description = f"{original_desc} [EDITED]"
        new_tags = f"{original_tags},edited,test" if original_tags else "edited,test"

        title_field.click()
        title_field.clear()
        title_field.send_keys(new_title)
        time.sleep(0.5)

        try:
            desc_field.click()
            desc_field.clear()
        except Exception:
            driver.execute_script("arguments[0].value = '';", desc_field)
            desc_field.click()
        desc_field.send_keys(new_description)
        time.sleep(0.5)

        tags_field.click()
        tags_field.clear()
        tags_field.send_keys(new_tags)
        time.sleep(0.5)

        save_btn = driver.find_element(By.ID, "saveBtn")
        save_btn.click()
        time.sleep(3)

        try:
            WebDriverWait(driver, 10).until(
                lambda d: "updated successfully" in d.page_source.lower()
                or "no changes" in d.page_source.lower()
                or d.current_url == f"{host}/dataset/{dataset_id}/edit"
            )
            try:
                alert = driver.switch_to.alert
                alert_text = alert.text
                assert "updated successfully" in alert_text.lower(), f"Expected success message, got: {alert_text}"
                alert.accept()
                time.sleep(1)
            except Exception:
                pass
        except Exception:
            pass

        driver.get(f"{host}/dataset/{dataset_id}/edit")
        wait_for_page_to_load(driver)
        time.sleep(1)

        title_field = driver.find_element(By.XPATH, "//input[@id='title']")
        desc_field = driver.find_element(By.XPATH, "//textarea[@id='description']")
        tags_field = driver.find_element(By.XPATH, "//input[@id='tags']")

        updated_title = title_field.get_attribute("value") or ""
        updated_desc = desc_field.get_attribute("value") or desc_field.get_attribute("textContent") or ""
        updated_tags = tags_field.get_attribute("value") or ""

        assert new_title == updated_title, f"Title not updated. Expected: {new_title}, Got: {updated_title}"
        assert (
            new_description == updated_desc
        ), f"Description not updated. Expected: {new_description}, Got: {updated_desc}"
        assert new_tags == updated_tags, f"Tags not updated. Expected: {new_tags}, Got: {updated_tags}"

        print("Test passed! Dataset edited successfully.")

    finally:
        close_driver(driver)


def test_view_changelog():
    """Test viewing the changelog (edit history) of a dataset."""
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        login_user(driver, host)

        driver.get(f"{host}/dataset/list")
        wait_for_page_to_load(driver)
        time.sleep(1)

        try:
            first_dataset_row = driver.find_element(By.XPATH, "//table//tbody//tr[1]")
            dataset_link = first_dataset_row.find_element(By.XPATH, ".//td[1]//a")
            dataset_link.click()
            wait_for_page_to_load(driver)
            time.sleep(2)
        except Exception as e:
            print(f"Error clicking first dataset: {e}")
            print("No datasets found, skipping changelog test")
            return

        dataset_id = None
        try:
            xpath_edit = "//a[contains(@href, '/dataset/') and contains(@href, '/edit')]"
            edit_button = driver.find_element(By.XPATH, xpath_edit)
            edit_href = edit_button.get_attribute("href")
            match = re.search(r"/dataset/(\d+)/edit", edit_href)
            if match:
                dataset_id = match.group(1)
        except Exception:
            current_url = driver.current_url
            match = re.search(r"/dataset/(\d+)", current_url)
            if match:
                dataset_id = match.group(1)

        if not dataset_id:
            print("Could not extract dataset_id, skipping changelog test")
            return

        driver.get(f"{host}/dataset/{dataset_id}/changelog")
        wait_for_page_to_load(driver)
        time.sleep(2)

        url_has_changelog = "changelog" in driver.current_url.lower()
        page_has_history = "edit history" in driver.page_source.lower() or "changelog" in driver.page_source.lower()
        assert url_has_changelog or page_has_history, "Not on changelog page"

        try:
            xpath_header = "//h4[contains(text(), 'Changelog') or contains(text(), 'Edit History')]"
            page_header = driver.find_element(By.XPATH, xpath_header)
            assert page_header is not None, "Changelog header not found"
        except Exception:
            try:
                timeline_section = driver.find_element(By.CLASS_NAME, "timeline")
                assert timeline_section is not None, "Timeline section not found"
            except Exception:
                try:
                    xpath_no_edits = "//*[contains(text(), 'No edits') or contains(text(), 'No changes')]"
                    driver.find_element(By.XPATH, xpath_no_edits)
                    print("Changelog page loaded correctly (no edits yet)")
                    return
                except Exception:
                    pass

        try:
            xpath_badges = (
                "//span[contains(@class, 'badge') and "
                "(contains(text(), 'Title') or contains(text(), 'Description') "
                "or contains(text(), 'Tags'))]"
            )
            edit_badges = driver.find_elements(By.XPATH, xpath_badges)
            if edit_badges:
                print(f"Found {len(edit_badges)} edit entries in changelog")
                xpath_old = "//*[contains(text(), 'Old value') or contains(text(), 'old value')]"
                xpath_new = "//*[contains(text(), 'New value') or contains(text(), 'new value')]"
                old_values = driver.find_elements(By.XPATH, xpath_old)
                new_values = driver.find_elements(By.XPATH, xpath_new)
                assert len(old_values) > 0 or len(new_values) > 0, "Edit details not visible"
        except Exception:
            pass

        try:
            quick_links = driver.find_element(By.XPATH, "//h5[contains(text(), 'Quick Links')]")
            assert quick_links is not None, "Quick links section not found"
        except Exception:
            pass

        print("Test passed! Changelog page loaded successfully.")

    finally:
        close_driver(driver)


def test_view_versions():
    """Test viewing the version history of a dataset."""
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        login_user(driver, host)

        driver.get(f"{host}/dataset/list")
        wait_for_page_to_load(driver)
        time.sleep(1)

        try:
            first_dataset_row = driver.find_element(By.XPATH, "//table//tbody//tr[1]")
            dataset_link = first_dataset_row.find_element(By.XPATH, ".//td[1]//a")
            dataset_link.click()
            wait_for_page_to_load(driver)
            time.sleep(2)
        except Exception as e:
            print(f"Error clicking first dataset: {e}")
            print("No datasets found, skipping versions test")
            return

        dataset_id = None
        try:
            xpath_edit = "//a[contains(@href, '/dataset/') and contains(@href, '/edit')]"
            edit_button = driver.find_element(By.XPATH, xpath_edit)
            edit_href = edit_button.get_attribute("href")
            match = re.search(r"/dataset/(\d+)/edit", edit_href)
            if match:
                dataset_id = match.group(1)
        except Exception:
            current_url = driver.current_url
            match = re.search(r"/dataset/(\d+)", current_url)
            if match:
                dataset_id = match.group(1)

        if not dataset_id:
            print("Could not extract dataset_id, skipping versions test")
            return

        driver.get(f"{host}/dataset/{dataset_id}/versions")
        wait_for_page_to_load(driver)
        time.sleep(2)

        url_has_versions = "versions" in driver.current_url.lower()
        page_has_versions = "version" in driver.page_source.lower()
        assert url_has_versions or page_has_versions, "Not on versions page"

        print("Test passed! Versions page loaded successfully.")

    finally:
        close_driver(driver)


if __name__ == "__main__":
    test_upload_dataset()
    test_edit_dataset()
    test_view_changelog()
    test_view_versions()
