from locust import HttpUser, TaskSet, between, task

from core.environment.host import get_host_for_locust_testing


class FollowBehavior(TaskSet):
    def on_start(self):
        self.following()

    @task
    def following(self):
        resp = self.client.get("/following")
        if resp.status_code != 200:
            print(f"[ERROR] /following devolvió {resp.status_code}")


class FollowUser(HttpUser):
    """
    Clase que Locust necesita encontrar: hereda de HttpUser.
    """

    tasks = [FollowBehavior]
    wait_time = between(5, 9)
    host = get_host_for_locust_testing()
