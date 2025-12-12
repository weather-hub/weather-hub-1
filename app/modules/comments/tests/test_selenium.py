import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait

from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import initialize_driver, close_driver


def click_safely(driver, by, selector):
    elem = WebDriverWait(driver, 10).until(
        lambda d: d.find_element(by, selector)
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
    time.sleep(0.2)
    elem.click()


def test_comments_flow():
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        driver.get(f"{host}")
        driver.set_window_size(1374, 868)

        click_safely(driver, By.LINK_TEXT, "Login")

        driver.find_element(By.ID, "email").send_keys("user2@example.com")
        driver.find_element(By.ID, "password").send_keys("1234")
        click_safely(driver, By.ID, "submit")

        driver.find_element(By.LINK_TEXT, "Explore").click()
        click_safely(driver, By.LINK_TEXT, "Weather Data (V2)")

        driver.find_element(By.ID, "content").send_keys("esto es una prueba")
        click_safely(driver, By.CSS_SELECTOR, "form > .btn")

        driver.find_element(By.LINK_TEXT, "Explore").click()
        click_safely(driver, By.LINK_TEXT, "UVL Models (V1)")
        click_safely(driver, By.XPATH, "//button[contains(text(), 'Approve') or contains(@class, 'btn-success')]")

        time.sleep(2)

    except NoSuchElementException as e:
        raise AssertionError(f"Elemento no encontrado: {e}")

    finally:
        close_driver(driver)


if __name__ == "__main__":
    test_comments_flow()
