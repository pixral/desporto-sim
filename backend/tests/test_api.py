from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_api_end_to_end(tmp_path):
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", ai_provider="mock",
                        frontend_dist=tmp_path / "no-dist")
    app = create_app(settings, autostart_run=False)
    with TestClient(app) as client:
        assert client.get("/api/state").status_code == 404
        meta = client.get("/api/meta").json()
        assert meta["paper_trading_only"] is True and len(meta["ceo_styles"]) == 4

        r = client.post("/api/runs", json={"company_name": "Test FC", "ceo_style": "chaotic_founder", "seed": 2})
        assert r.status_code == 200, r.text
        state = client.get("/api/state").json()
        assert state["run"]["company_name"] == "Test FC"
        assert state["kpis"]["tipsters"] == 8

        for _ in range(8):
            assert client.post("/api/control", json={"action": "step"}).status_code == 200
        state = client.get("/api/state").json()
        assert state["clock"]["day_index"] == 2

        emp = next(e for e in state["employees"] if e["role"] == "tipster")
        detail = client.get(f"/api/employees/{emp['id']}").json()
        assert detail["name"] == emp["name"] and "relationships" in detail and "strategy" in detail
        assert client.get("/api/employees/nope").status_code == 404

        for path in ("/api/finance", "/api/lab", "/api/history", "/api/management", "/api/summary",
                     "/api/bets", "/api/ai/stats", "/api/employees"):
            assert client.get(path).status_code == 200, path
        calls = client.get("/api/ai/calls").json()
        assert calls and client.get(f"/api/ai/calls/{calls[0]['id']}").json()["prompt"]

        save_id = client.post("/api/saves", json={"label": "checkpoint"}).json()["save_id"]
        client.post("/api/control", json={"action": "day"})
        assert client.get("/api/state").json()["clock"]["day_index"] == 3
        assert client.post(f"/api/saves/{save_id}/load").status_code == 200
        assert client.get("/api/state").json()["clock"]["day_index"] == 2
        assert any(s["id"] == save_id for s in client.get("/api/saves").json())

        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "state" and msg["data"]["run"]["company_name"] == "Test FC"

        assert client.post("/api/control", json={"action": "speed", "speed": "warp"}).status_code == 400


def test_api_city_office_and_sandbox(tmp_path):
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", ai_provider="mock",
                        frontend_dist=tmp_path / "no-dist")
    app = create_app(settings, autostart_run=False)
    with TestClient(app) as client:
        client.post("/api/runs", json={"company_name": "Sandbox FC", "seed": 4})
        for _ in range(5):
            client.post("/api/control", json={"action": "step"})
        paper = client.get("/api/newspaper").json()
        assert paper["available"] and paper["stocks"] and paper["items"]
        state = client.get("/api/state").json()
        assert state["city"]["headline"] and len(state["office"]["facilities"]) == 3
        assert state["sandbox"]["god_actions"] == 0
        catalog = client.get("/api/god").json()
        assert "invest" in catalog["actions"] and catalog["facilities"]
        r = client.post("/api/god", json={"action": "invest", "params": {"amount": 5000}})
        assert r.status_code == 200 and r.json()["god_actions"] == 1
        assert client.post("/api/god", json={"action": "nope"}).status_code == 400
        assert client.post("/api/god", json={"action": "disaster", "params": {"kind": "meteor"}}).status_code == 400
        assert client.get("/api/state").json()["sandbox"]["god_actions"] == 1
        assert client.get("/api/office").json()["desk_rooms"] == 6


def test_api_player_mode(tmp_path):
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", ai_provider="mock",
                        frontend_dist=tmp_path / "no-dist")
    app = create_app(settings, autostart_run=False)
    with TestClient(app) as client:
        meta = client.get("/api/meta").json()
        assert [m["key"] for m in meta["pause_modes"]] == ["monthly", "every_review", "events_only"]
        r = client.post("/api/runs", json={"company_name": "Player FC", "seed": 5, "player_ceo": True,
                                           "player_name": "Alex", "pause_mode": "every_review", "ironman": True})
        assert r.status_code == 200, r.text
        state = client.get("/api/state").json()
        assert state["run"]["player_ceo"] and state["player"]["name"] == "Alex"
        assert state["sandbox"]["locked"] and client.post("/api/god", json={"action": "windfall"}).status_code == 400
        assert client.get("/api/review").json() == {"open": False}
        assert client.post("/api/review", json={"actions": [], "memo": ""}).status_code == 400

        first_save = client.post("/api/saves", json={"label": "day 0"}).json()["save_id"]
        for _ in range(4):
            client.post("/api/control", json={"action": "day"})
        state = client.get("/api/state").json()
        assert state["player"]["review_open"] and state["clock"]["weekday"] == "Monday"
        review = client.get("/api/review").json()
        assert review["open"] and review["scope"] == "weekly" and review["advisor"]["label"]

        tipster = next(p for p in review["people"] if p["role"] == "tipster")
        act = client.post("/api/act", json={"action": {"type": "TALK", "employee_id": tipster["id"]}}).json()
        assert act["applied"], act
        refused = client.post("/api/act", json={"action": {"type": "PROMOTE", "employee_id": tipster["id"]}}).json()
        assert not refused["applied"] and "monthly review" in refused["result"]
        assert client.post("/api/queue", json={"action": {"type": "PROMOTE", "employee_id": tipster["id"]}}).status_code == 200
        assert len(client.get("/api/state").json()["player"]["queue"]) == 1
        assert client.delete("/api/queue/0").status_code == 200
        assert client.delete("/api/queue/0").status_code == 400

        signed = client.post("/api/review", json={"actions": [{"type": "WARN", "employee_id": tipster["id"]}],
                                                  "memo": "Eyes on the prize."}).json()
        assert signed["results"][0]["applied"]
        state = client.get("/api/state").json()
        assert not state["player"]["review_open"]
        mgmt = client.get("/api/management").json()
        assert mgmt[0]["by"] == "player" or any(m["by"] == "player" for m in mgmt)
        detail = client.get(f"/api/employees/{tipster['id']}").json()
        assert detail["advisor_note"] and detail["under_review"]

        client.post("/api/saves", json={"label": "later"})
        assert client.post(f"/api/saves/{first_save}/load").status_code == 403  # ironman: latest save only


def test_unknown_api_route_is_a_404_not_the_page(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>app</title>")
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", ai_provider="mock",
                        frontend_dist=dist)
    with TestClient(create_app(settings, autostart_run=False)) as client:
        assert client.get("/api/does-not-exist").status_code == 404
        assert "<title>app</title>" in client.get("/office/anything").text


def test_startup_loads_the_latest_save_and_never_founds_a_company(tmp_path):
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", ai_provider="mock",
                        frontend_dist=tmp_path / "no-dist")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/state").status_code == 404  # the title screen offers "New game"
        client.post("/api/runs", json={"company_name": "First FC", "seed": 3})
        client.post("/api/runs", json={"company_name": "Second FC", "seed": 4})
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/state").json()["run"]["company_name"] == "Second FC"
