from locust import HttpUser, TaskSet, task

from core.environment.host import get_host_for_locust_testing


class CommunityBehavior(TaskSet):
    def on_start(self):
        self.login()

    def login(self):
        response = self.client.post("/login", json={"email": "user1@example.com", "password": "1234"})
        if response.status_code != 200:
            print(f"Login failed: {response.status_code}")

    @task
    def list_communities(self):
        response = self.client.get("/community/")
        if response.status_code != 200:
            print(f"Failed to list communities: {response.status_code}")

    @task
    def join_community(self):
        response = self.client.post(f"/community/{1}/join")
        if response.status_code not in [200, 302]:
            print(f"Failed to join community: {response.status_code}")

    @task
    def leave_community(self):
        response = self.client.post(f"/community/{1}/leave")
        if response.status_code not in [200, 302]:
            print(f"Failed to leave community: {response.status_code}")


class CommunityUser(HttpUser):
    tasks = [CommunityBehavior]
    min_wait = 3000
    max_wait = 7000
    host = get_host_for_locust_testing()
