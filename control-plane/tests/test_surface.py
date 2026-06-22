"""Segments, SDK credentials, audit read, and flag salt."""
import pytest


@pytest.fixture()
def project_env(client):
    client.post("/api/v1/projects", json={"key": "streaming", "name": "Streaming"})
    client.post(
        "/api/v1/projects/streaming/environments",
        json={"key": "production", "name": "Production"},
    )
    return client


def test_flag_gets_salt(project_env):
    client = project_env
    r = client.post(
        "/api/v1/projects/streaming/flags",
        json={
            "key": "f1", "name": "F1", "kind": "boolean",
            "variations": [{"name": "On", "value": True}, {"name": "Off", "value": False}],
        },
    )
    assert r.status_code == 201, r.text
    assert len(r.json()["salt"]) >= 8  # server-generated bucketing salt


def test_segment_create_and_config(project_env):
    client = project_env
    assert client.post(
        "/api/v1/projects/streaming/segments",
        json={"key": "power-viewers", "name": "Power viewers"},
    ).status_code == 201

    r = client.put(
        "/api/v1/projects/streaming/segments/power-viewers/environments/production",
        json={
            "contextKind": "user",
            "included": ["u-1", "u-2"],
            "rules": [
                {"clauses": [{"attribute": "plan", "op": "in", "values": ["premium"]}]}
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == 1
    assert body["included"] == ["u-1", "u-2"]


def test_credential_issue_list_revoke(project_env):
    client = project_env
    base = "/api/v1/projects/streaming/environments/production/credentials"

    r = client.post(base, json={"kind": "server"})
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["key"].startswith("srv-production-")  # plaintext shown once
    cred_id = created["id"]

    listed = client.get(base).json()
    assert len(listed) == 1
    assert "key" not in listed[0]  # never returned again

    r = client.post(f"{base}/{cred_id}/revoke")
    assert r.status_code == 200
    assert r.json()["revoked_at"] is not None


def test_audit_log_read(project_env):
    client = project_env
    entries = client.get("/api/v1/projects/streaming/audit").json()
    actions = {e["action"] for e in entries}
    assert {"project.created", "environment.created"} <= actions
