import pytest


@pytest.fixture()
def project_env(client):
    client.post("/api/v1/projects", json={"key": "streaming", "name": "Streaming"})
    client.post(
        "/api/v1/projects/streaming/environments",
        json={"key": "production", "name": "Production"},
    )
    return client


def _boolean_flag_body():
    return {
        "key": "paywall-v3",
        "name": "Paywall v3",
        "kind": "boolean",
        "variations": [{"name": "On", "value": True}, {"name": "Off", "value": False}],
    }


def test_create_flag_seeds_env_config(project_env):
    client = project_env
    r = client.post("/api/v1/projects/streaming/flags", json=_boolean_flag_body())
    assert r.status_code == 201, r.text

    # A default (off) config exists for the environment.
    cfg = client.get(
        "/api/v1/projects/streaming/flags/paywall-v3/environments/production"
    ).json()
    assert cfg["enabled"] is False
    assert cfg["version"] == 1


def test_update_targeting_with_rollout(project_env):
    client = project_env
    client.post("/api/v1/projects/streaming/flags", json=_boolean_flag_body())

    body = {
        "enabled": True,
        "rules": [
            {
                "clauses": [
                    {"contextKind": "user", "attribute": "country",
                     "op": "in", "values": ["US", "CA"]}
                ],
                "variation": 0,
            }
        ],
        "fallthrough": {
            "rollout": {
                "contextKind": "user",
                "bucketBy": "key",
                "variations": [
                    {"variation": 0, "weight": 60000},
                    {"variation": 1, "weight": 40000},
                ],
            }
        },
        "offVariation": 1,
    }
    r = client.put(
        "/api/v1/projects/streaming/flags/paywall-v3/environments/production", json=body
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["enabled"] is True
    assert out["version"] == 2  # bumped from the seeded version 1
    assert out["rules"][0]["clauses"][0]["attribute"] == "country"


def test_rollout_weights_must_sum_to_100k(project_env):
    client = project_env
    client.post("/api/v1/projects/streaming/flags", json=_boolean_flag_body())
    body = {
        "enabled": True,
        "fallthrough": {
            "rollout": {
                "variations": [
                    {"variation": 0, "weight": 50000},
                    {"variation": 1, "weight": 40000},  # sums to 90k
                ]
            }
        },
    }
    r = client.put(
        "/api/v1/projects/streaming/flags/paywall-v3/environments/production", json=body
    )
    assert r.status_code == 422


def test_variation_index_out_of_range(project_env):
    client = project_env
    client.post("/api/v1/projects/streaming/flags", json=_boolean_flag_body())
    body = {"enabled": True, "fallthrough": {"variation": 5}}  # only 0,1 exist
    r = client.put(
        "/api/v1/projects/streaming/flags/paywall-v3/environments/production", json=body
    )
    assert r.status_code == 422
    assert "out of range" in r.text
