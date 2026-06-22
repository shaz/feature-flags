def test_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_project_and_environment_crud(client):
    r = client.post("/api/v1/projects", json={"key": "streaming", "name": "Streaming"})
    assert r.status_code == 201, r.text
    assert r.json()["key"] == "streaming"

    # duplicate key -> 409
    assert client.post(
        "/api/v1/projects", json={"key": "streaming", "name": "dupe"}
    ).status_code == 409

    r = client.post(
        "/api/v1/projects/streaming/environments",
        json={"key": "production", "name": "Production"},
    )
    assert r.status_code == 201, r.text

    envs = client.get("/api/v1/projects/streaming/environments").json()
    assert [e["key"] for e in envs] == ["production"]


def test_unknown_project_404(client):
    assert client.get("/api/v1/projects/nope").status_code == 404
