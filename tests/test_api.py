"""Smoke tests for the API. Uses the seed dataset (no Reddit credentials)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    # One lifespan for the whole module (single event loop / engine).
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] in ("healthy", "unhealthy")


def test_summary_shape(client):
    r = client.get("/api/summary?hours=720")
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body
    assert "top_topics" in body
    assert "counts" in body["summary"]


def test_trends_shape(client):
    r = client.get("/api/trends?hours=720")
    assert r.status_code == 200
    assert "data" in r.json()


def test_trigger_rejected_without_token(client):
    assert client.post("/api/trigger/ingestion").status_code == 403


def test_trigger_runs_with_token(client):
    headers = {"X-Admin-Token": "test-token"}
    ing = client.post("/api/trigger/ingestion", headers=headers)
    assert ing.status_code == 200
    assert ing.json()["posts_ingested"] > 0
    proc = client.post("/api/trigger/process", headers=headers)
    assert proc.status_code == 200


def test_stats_shape(client):
    # Ensure the pipeline has run deterministically before asserting.
    headers = {"X-Admin-Token": "test-token"}
    client.post("/api/trigger/ingestion", headers=headers)
    client.post("/api/trigger/process", headers=headers)

    body = client.get("/api/stats").json()
    assert "ingestion" in body
    assert "processing" in body
    assert "reddit_requests" in body
    assert "database" in body
    assert body["database"]["total_posts"] > 0
