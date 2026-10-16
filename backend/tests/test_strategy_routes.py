"""Phase 70 item 4: uploads are off by default, refused cross-site, and every run is sandboxed."""
import pytest

from backend import store
from tests.test_strategy_engine import _store  # noqa: F401  (the stored universe fixture)

SOURCE = "def generate_weights(ctx):\n    return {'UP': 1.0}\n"
RUN = {"start": "2024-01-01", "end": "2024-06-30"}
EVIL = {"Origin": "http://evil.example"}


@pytest.fixture(autouse=True)
def _clean():
    def wipe():
        with store.connect() as conn:
            conn.execute("DELETE FROM strategy")
            conn.execute("DELETE FROM app_setting")
    wipe()
    yield
    wipe()


def _enable(client, on=True):
    assert client.put("/api/admin/strategy-uploads", json={"enabled": on}).status_code == 200


def test_uploads_are_off_by_default_but_the_bundled_example_runs(client):
    listing = client.get("/api/research/strategies").json()
    assert listing["uploadsEnabled"] is False and listing["sandbox"]["supported"]
    assert client.post("/api/research/strategies", json={"name": "x.py", "source": SOURCE}).status_code == 403
    example = next(s for s in listing["strategies"] if s["builtIn"])
    r = client.post("/api/research/strategies/run", json={"strategyId": example["id"], **RUN,
                                                          "params": {"top_n": 2, "lookback": 21, "skip": 0}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sandbox"]["mode"] == "subprocess" and body["strategy"]["sha256"] == example["sha256"]
    assert body["externalRequestsDuringRun"] == 0


def test_an_upload_is_stored_by_hash_runs_sandboxed_and_stops_running_when_uploads_go_off(client):
    _enable(client)
    up = client.post("/api/research/strategies", json={"name": "mine.py", "source": SOURCE})
    assert up.status_code == 200, up.text
    sid = up.json()["id"]
    assert client.post("/api/research/strategies", json={"name": "again.py", "source": SOURCE}).json()["id"] == sid
    r = client.post("/api/research/strategies/run", json={"strategyId": sid, **RUN})
    assert r.status_code == 200, r.text
    assert r.json()["sandbox"]["mode"] == "subprocess" and r.json()["metrics"]["totalReturn"] > 0
    _enable(client, False)
    assert client.post("/api/research/strategies/run", json={"strategyId": sid, **RUN}).status_code == 403
    assert client.delete(f"/api/research/strategies/{sid}").status_code == 200


def test_a_cross_site_page_can_neither_turn_uploads_on_nor_upload_nor_run(client):
    assert client.put("/api/admin/strategy-uploads", json={"enabled": True}, headers=EVIL).status_code == 403
    _enable(client)
    assert client.post("/api/research/strategies", json={"name": "x.py", "source": SOURCE},
                       headers=EVIL).status_code == 403
    assert client.post("/api/research/strategies/run", json={"strategyId": "example:example_momentum", **RUN},
                       headers=EVIL).status_code == 403
    ok = client.put("/api/admin/strategy-uploads", json={"enabled": False}, headers={"Origin": "http://localhost"})
    assert ok.status_code == 200


def test_a_form_post_is_not_parsed_as_json(client):
    _enable(client)
    r = client.post("/api/research/strategies", content='{"name": "x.py", "source": "def generate_weights(c): pass"}',
                    headers={"Content-Type": "text/plain"})
    assert r.status_code == 422  # a cross-site form can send text/plain without a preflight


@pytest.mark.parametrize("source, status", [("def generate_weights(ctx) return {}", 400),
                                            ("def other(ctx):\n    return {}\n", 400)])
def test_a_broken_file_is_refused_without_running(client, source, status):
    _enable(client)
    assert client.post("/api/research/strategies", json={"name": "x.py", "source": source}).status_code == status


def test_a_name_must_be_a_plain_py_file_name(client):
    _enable(client)
    assert client.post("/api/research/strategies", json={"name": "../evil.sh", "source": SOURCE}).status_code == 422
