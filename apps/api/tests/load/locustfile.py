"""Load test (Locust, free). NOT part of the pytest suite.

    pip install -r requirements-dev.txt
    LOADTEST_EMAIL=... LOADTEST_PASSWORD=... locust -f tests/load/locustfile.py --host http://localhost:8010

Then open http://localhost:8089, choose users/spawn rate, and watch p95 latency and failures.
Use a dedicated test account in a staging workspace; never run against production customer data.
Simulated outbound mode means no real calls/messages are made (APP_ENV must not be production).
The webhook scenario replays signed Twilio-style turn callbacks only when LOADTEST_CALL_ID and
TWILIO_AUTH_TOKEN/PUBLIC_WEBHOOK_BASE_URL are provided, to measure the voice turn path.
"""
import os

from locust import HttpUser, between, task


class AppUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self):
        r = self.client.post("/api/v1/auth/login", json={"email": os.environ["LOADTEST_EMAIL"],
                                                         "password": os.environ["LOADTEST_PASSWORD"]})
        tok = r.json()["access_token"]
        me = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
        self.h = {"Authorization": f"Bearer {tok}",
                  "X-Organization-Id": me["memberships"][0]["organization"]["id"]}

    @task(5)
    def dashboard(self):
        for p in ("/insights/overview?days=30", "/insights/pipeline-value", "/insights/briefing"):
            self.client.get(f"/api/v1{p}", headers=self.h, name=p.split("?")[0])

    @task(4)
    def leads(self):
        self.client.get("/api/v1/leads?page_size=25", headers=self.h, name="/leads")

    @task(2)
    def calls(self):
        self.client.get("/api/v1/calls?page_size=25", headers=self.h, name="/calls")

    @task(1)
    def health(self):
        self.client.get("/health/ready", name="/health/ready")
