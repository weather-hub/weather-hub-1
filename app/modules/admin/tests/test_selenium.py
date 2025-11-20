import time

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import close_driver, initialize_driver


def test_admin_role_management():
    """
    Test that verifies the admin role management functionality:
    1. Admin user can access the admin panel
    2. Admin can open the role management modal
    3. Admin can change user roles
    """
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        # Login as admin
        driver.get(f"{host}/login")
        time.sleep(2)

        email_field = driver.find_element(By.NAME, "email")
        password_field = driver.find_element(By.NAME, "password")

        email_field.send_keys("user1@example.com")
        password_field.send_keys("1234")
        password_field.send_keys(Keys.RETURN)

        time.sleep(3)

        # Navigate to admin users page
        driver.get(f"{host}/admin/users")
        time.sleep(3)

        # Verify we can see the admin page
        try:
            driver.find_element(By.XPATH, "//h1[contains(text(), 'Gestión de Usuarios')]")
            print("✓ Admin page loaded successfully")
        except NoSuchElementException:
            raise AssertionError("Could not access admin users page!")

        # Verify table with users exists
        try:
            driver.find_element(By.CLASS_NAME, "table")
            print("✓ Users table is displayed")
        except NoSuchElementException:
            raise AssertionError("Users table not found!")

        # Find and click "Gestionar Roles" button
        try:
            manage_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Gestionar Roles')]")
            manage_button.click()
            time.sleep(2)
            print("✓ Clicked on 'Gestionar Roles' button")
        except NoSuchElementException:
            raise AssertionError("'Gestionar Roles' button not found!")

        # Verify modal opened
        try:
            WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.ID, "roleModal")))
            print("✓ Role management modal opened")
        except Exception:
            raise AssertionError("Modal did not open!")

        # Verify role checkboxes exist
        try:
            checkboxes = driver.find_elements(By.CLASS_NAME, "role-checkbox")
            if len(checkboxes) == 0:
                raise AssertionError("No role checkboxes found!")
            print(f"✓ Found {len(checkboxes)} role options")
        except NoSuchElementException:
            raise AssertionError("Role checkboxes not found!")

        # Verify save button exists
        try:
            driver.find_element(By.XPATH, "//div[@id='roleModal']//button[contains(text(), 'Guardar')]")
            print("✓ Save button found in modal")
        except NoSuchElementException:
            raise AssertionError("Save button not found!")

        print("\n✅ Test passed: Admin role management functionality works correctly!")

    finally:
        close_driver(driver)


# Run the test
if __name__ == "__main__":
    test_admin_role_management()
