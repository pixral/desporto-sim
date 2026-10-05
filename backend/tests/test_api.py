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
