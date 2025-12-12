import logging

import pyotp
from bs4 import BeautifulSoup
from locust import HttpUser, between, task

logger = logging.getLogger(__name__)


class ExploreSearchUser(HttpUser):
    """Locust user for load testing the Explore dataset search functionality."""

    wait_time = between(1, 3)

    def on_start(self):
        """Authenticate once at the beginning of the test run."""
        logger.info("Starting authentication sequence...")

        try:
            login_page = self.client.get("/login", name="/login")
            soup = BeautifulSoup(login_page.text, "html.parser")
            csrf = soup.find("input", {"name": "csrf_token"})
            csrf_token = csrf["value"] if csrf else ""
            logger.debug(f"CSRF token obtained: {csrf_token[:10]}...")
        except Exception as e:
            logger.error(f"Error fetching CSRF token: {e}")
            csrf_token = ""

        try:
            login_response = self.client.post(
                "/login",
                data={
                    "email": "user1@example.com",
                    "password": "1234",
                    "csrf_token": csrf_token,
                },
                name="/login (POST)",
            )
            logger.debug(f"Login POST status: {login_response.status_code}")
        except Exception as e:
            logger.error(f"Error during login POST: {e}")
            return

        try:
            totp = pyotp.TOTP("JBSWY3DPEHPK3PXP")
            code = totp.now()
            logger.debug(f"Generated TOTP code: {code}")

            verify_page = self.client.get("/verify-2fa", name="/verify-2fa (GET)")
            soup = BeautifulSoup(verify_page.text, "html.parser")
            csrf = soup.find("input", {"name": "csrf_token"})
            csrf_token = csrf["value"] if csrf else ""

            verify_response = self.client.post(
                "/verify-2fa",
                data={"code": code, "csrf_token": csrf_token},
                name="/verify-2fa (POST)",
            )
            logger.debug(f"2FA verification status: {verify_response.status_code}")
            logger.info("Authentication sequence completed successfully")
        except Exception as e:
            logger.error(f"Error during 2FA: {e}")

    @task(3)
    def search_by_query(self):
        """Perform search by query (title/description) on the explore page."""
        query = "security"
        url = f"/explore/?query={query}&publication_type=any&tags=&start_date=&end_date=&sort_by=newest"
        try:
            response = self.client.get(url, name="/explore/?query=security")
            if response.status_code != 200:
                logger.warning(f"Unexpected status for query search: {response.status_code}")
        except Exception as e:
            logger.error(f"Error in search_by_query: {e}")

    @task(2)
    def search_by_tag(self):
        """Perform search by tag on the explore page."""
        tag = "climate"
        url = f"/explore/?query=&publication_type=any&tags={tag}&start_date=&end_date=&sort_by=newest"
        try:
            response = self.client.get(url, name="/explore/?tags=climate")
            if response.status_code != 200:
                logger.warning(f"Unexpected status for tag search: {response.status_code}")
        except Exception as e:
            logger.error(f"Error in search_by_tag: {e}")

    @task(2)
    def search_combined_query_and_tag(self):
        """Perform combined search by query and tag on the explore page."""
        query = "security"
        tag = "climate"
        url = f"/explore/?query={query}&publication_type=any&tags={tag}&start_date=&end_date=&sort_by=newest"
        try:
            response = self.client.get(url, name="/explore/?query=security&tags=climate")
            if response.status_code != 200:
                logger.warning(f"Unexpected status for combined search: {response.status_code}")
        except Exception as e:
            logger.error(f"Error in search_combined_query_and_tag: {e}")

    @task(1)
    def search_by_publication_type(self):
        """Perform search by publication type on the explore page."""
        pub_type = "national"
        url = f"/explore/?query=&publication_type={pub_type}&tags=&start_date=&end_date=&sort_by=newest"
        try:
            response = self.client.get(url, name="/explore/?publication_type=national")
            if response.status_code != 200:
                logger.warning(f"Unexpected status for publication type search: {response.status_code}")
        except Exception as e:
            logger.error(f"Error in search_by_publication_type: {e}")

    @task(1)
    def search_with_date_range(self):
        """Perform search with date range filter."""
        url = "/explore/?query=&publication_type=any&tags=&start_date=2023-01-01&end_date=2024-12-31&sort_by=newest"
        try:
            response = self.client.get(url, name="/explore/?date_range=2023-2024")
            if response.status_code != 200:
                logger.warning(f"Unexpected status for date range search: {response.status_code}")
        except Exception as e:
            logger.error(f"Error in search_with_date_range: {e}")

    @task(1)
    def search_no_filters(self):
        """Perform search with no filters to load all datasets."""
        url = "/explore/?query=&publication_type=any&tags=&start_date=&end_date=&sort_by=newest"
        try:
            response = self.client.get(url, name="/explore/?no_filters")
            if response.status_code != 200:
                logger.warning(f"Unexpected status for no-filter search: {response.status_code}")
        except Exception as e:
            logger.error(f"Error in search_no_filters: {e}")

    @task(1)
    def search_sorting_oldest(self):
        """Perform search with 'oldest' sorting."""
        url = "/explore/?query=&publication_type=any&tags=&start_date=&end_date=&sort_by=oldest"
        try:
            response = self.client.get(url, name="/explore/?sort_by=oldest")
            if response.status_code != 200:
                logger.warning(f"Unexpected status for oldest sort: {response.status_code}")
        except Exception as e:
            logger.error(f"Error in search_sorting_oldest: {e}")
