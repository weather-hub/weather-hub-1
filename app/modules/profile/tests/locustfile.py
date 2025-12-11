import re

from locust import HttpUser, TaskSet, between, task

from core.environment.host import get_host_for_locust_testing
from core.locust.common import get_csrf_token


class ProfileBehavior(TaskSet):
    def on_start(self):
        """Warm up: hit home page to establish session and capture CSRF"""
        response = self.client.get("/")
        get_csrf_token(response)
        # Extract user IDs from home page datasets
        self.user_ids = self._extract_user_ids(response)
        if not self.user_ids:
            self.user_ids = [1, 2, 3]  # Fallback to common IDs

    def _extract_user_ids(self, response):
        """Extract user IDs from profile links in the response"""
        try:
            matches = re.findall(rb"/profile/(\d+)", response.content or b"")
            return list(set([m.decode("utf-8") for m in matches]))
        except Exception:
            return []

    @task(5)
    def view_public_profile(self):
        """View a public user profile with their datasets"""
        if self.user_ids:
            user_id = self.user_ids[0]  # Use first found user ID
            self.client.get(f"/profile/{user_id}", name="/profile/[user_id]")

    @task(3)
    def view_home_page(self):
        """View home page which displays users linked to datasets"""
        response = self.client.get("/")
        # Update user IDs from home page
        new_ids = self._extract_user_ids(response)
        if new_ids:
            self.user_ids = new_ids

    @task(2)
    def view_profile_paginated(self):
        """View a public profile with pagination"""
        if self.user_ids:
            user_id = self.user_ids[0]
            self.client.get(f"/profile/{user_id}?page=1", name="/profile/[user_id]?page=1")

    @task(1)
    def view_nonexistent_profile(self):
        """Test handling of non-existent profile (should redirect)"""
        self.client.get("/profile/99999", allow_redirects=False, name="/profile/[invalid_id]")


class ProfileUser(HttpUser):
    tasks = [ProfileBehavior]
    wait_time = between(2, 5)
    host = get_host_for_locust_testing()
