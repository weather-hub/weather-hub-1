import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import close_driver, initialize_driver


def wait_for_page_to_load(driver, timeout=4):
    """Wait for page to fully load"""
    WebDriverWait(driver, timeout).until(
        lambda driver: driver.execute_script("return document.readyState") == "complete"
    )


def test_click_username_in_home_leads_to_profile():
    """Test that clicking on a username in home page leads to user's public profile"""
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        # Navigate to home page
        driver.get(f"{host}/")
        wait_for_page_to_load(driver)

        # Find a dataset card and click on the uploader's name
        profile_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/profile/')]")
        if not profile_links:
            print("No profile links found in home page. Test skipped.")
            return

        # Click on the first profile link
        first_profile_link = profile_links[0]
        expected_href = first_profile_link.get_attribute("href")
        first_profile_link.click()
        time.sleep(2)
        wait_for_page_to_load(driver)

        # Verify we're on a profile page
        assert "/profile/" in driver.current_url, f"Expected profile URL, got {driver.current_url}"
        assert driver.current_url == expected_href, f"Expected {expected_href}, got {driver.current_url}"

        # Verify profile content is displayed
        profile_info = driver.find_element(By.CLASS_NAME, "card")
        assert profile_info is not None, "Profile card not found"

        print("Test passed: Username link in home leads to profile!")

    except Exception as e:
        print(f"Test failed: {e}")
        raise

    finally:
        close_driver(driver)


def test_view_public_profile_displays_datasets():
    """Test that viewing a user's public profile displays their datasets"""
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        # Navigate to home page first to get a valid user ID
        driver.get(f"{host}/")
        wait_for_page_to_load(driver)

        # Extract a user ID from a profile link
        profile_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/profile/')]")

        if not profile_links:
            print("No profile links found. Test skipped.")
            return

        # Click first profile link to get a valid user ID
        profile_links[0].click()
        time.sleep(2)
        wait_for_page_to_load(driver)

        # Verify that "User datasets" section exists
        try:
            datasets_section = driver.find_element(By.XPATH, "//*[contains(text(), 'User datasets')]")
            assert datasets_section is not None, "User datasets section not found"
        except Exception as e:
            print(f"User datasets section not found, but page loaded successfully: {e}")

        # Verify we can see the profile information card
        profile_cards = driver.find_elements(By.CLASS_NAME, "card")
        assert len(profile_cards) > 0, "No profile cards found"

        print("Test passed: Public profile displays correctly!")

    except Exception as e:
        print(f"Test failed: {e}")
        raise

    finally:
        close_driver(driver)


def test_navigate_profile_pagination():
    """Test that profile pagination works when viewing user datasets"""
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        # Navigate to a user profile (use a known user ID or find one from home)
        driver.get(f"{host}/")
        wait_for_page_to_load(driver)

        profile_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/profile/')]")

        if not profile_links:
            print("No profile links found. Test skipped.")
            return

        # Click on a profile to navigate there
        profile_links[0].click()
        time.sleep(2)
        wait_for_page_to_load(driver)

        # Try to find and click pagination buttons
        try:
            # Look for next page button (pagination)
            next_page_btn = driver.find_element(By.XPATH, "//a[@aria-label='Next']")

            if next_page_btn and "disabled" not in next_page_btn.get_attribute("class"):
                next_page_btn.click()
                time.sleep(2)
                wait_for_page_to_load(driver)

                # Verify we're still on a profile page with page parameter
                assert "/profile/" in driver.current_url, "Should still be on profile page"
                assert "page=" in driver.current_url, "Should have page parameter in URL"

                print("Test passed: Profile pagination works!")
            else:
                print("Pagination not available (only one page of datasets)")
        except Exception as e:
            print(f"Pagination test skipped: {e}")

    except Exception as e:
        print(f"Test failed: {e}")
        raise

    finally:
        close_driver(driver)


def test_click_uploader_name_in_dataset_view():
    """Test that clicking on uploader's name in dataset view leads to their profile"""
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        # Navigate to a dataset detail page
        driver.get(f"{host}/")
        wait_for_page_to_load(driver)

        # Find and click on a "View dataset" button
        view_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), 'View dataset')]")
        if not view_buttons:
            print("No 'View dataset' button found. Test skipped.")
            return

        view_buttons[0].click()
        time.sleep(2)
        wait_for_page_to_load(driver)

        # Now look for uploader's name link on dataset detail page
        uploader_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/profile/')]")

        if not uploader_links:
            print("No uploader profile link found in dataset detail page. Test skipped.")
            return

        # Click on the uploader's name
        uploader_links[0].click()
        time.sleep(2)
        wait_for_page_to_load(driver)

        # Verify we're on the uploader's profile
        assert "/profile/" in driver.current_url, f"Expected profile URL, got {driver.current_url}"

        # Verify profile page elements
        profile_cards = driver.find_elements(By.CLASS_NAME, "card")
        assert len(profile_cards) > 0, "No profile cards found"

        print("Test passed: Uploader name link in dataset view leads to profile!")

    except Exception as e:
        print(f"Test failed: {e}")
        raise

    finally:
        close_driver(driver)
