"""
tests/load/locustfile.py – Load test scenarios for SignSpeak backend.

Run with:
    pip install locust
    locust -f tests/load/locustfile.py --host http://localhost:8081

Visit http://localhost:8089 to control the test via Locust's UI.
"""
import json
import random
import string

from locust import HttpUser, between, task


def _random_channel_id() -> str:
    return "ch-" + "".join(random.choices(string.ascii_lowercase, k=8))


# ── Fake Firebase token (will be rejected by real servers; use a real token) ──
FAKE_TOKEN = "Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6InRlc3QifQ.stub.stub"


class AIServerUser(HttpUser):
    """Simulates a user hitting the AI Server endpoints."""

    wait_time = between(0.5, 2.0)
    host = "http://localhost:8081"

    @task(3)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task(5)
    def translate(self):
        self.client.post(
            "/translate",
            json={
                "text": "Hello, how are you?",
                "source_lang": "en",
                "target_lang": "hi",
            },
            headers={"Authorization": FAKE_TOKEN},
            name="/translate",
        )

    @task(3)
    def text_to_sign(self):
        self.client.post(
            "/text-to-sign",
            json={"text": "Good morning", "locale": "en-US"},
            headers={"Authorization": FAKE_TOKEN},
            name="/text-to-sign",
        )

    @task(1)
    def tts(self):
        self.client.post(
            "/tts",
            json={"text": "SignSpeak is amazing!"},
            headers={"Authorization": FAKE_TOKEN},
            name="/tts",
        )


class TokenServerUser(HttpUser):
    """Simulates a user hitting the Token Server."""

    wait_time = between(1.0, 3.0)
    host = "http://localhost:8080"

    @task(2)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task(5)
    def request_token(self):
        self.client.post(
            "/token",
            json={
                "channelId": _random_channel_id(),
                "uid": "load-test-uid",
                "role": "publisher",
                "ttlSeconds": 3600,
            },
            headers={"Authorization": FAKE_TOKEN},
            name="/token",
        )
