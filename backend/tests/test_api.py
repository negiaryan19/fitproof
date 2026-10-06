import time
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings

def payload(**kwargs):
    return {"device_model":"Lenovo ThinkPad T480","installed_modules_gb":[8],"free_slots":1,"mode":"replay",**kwargs}
def wait(client,run_id):
    for _ in range(100):
        state=client.get("/api/runs/"+run_id).json()
        if state["status"]!="investigating":
            return state
        time.sleep(.01)
    raise AssertionError("Run did not finish")

def test_api_replay_clarification_report_and_sse(tmp_path):
    with TestClient(create_app(Settings(_env_file=None,database_path=tmp_path/'api.db'))) as client:
        created=client.post("/api/runs",json=payload())
        assert created.status_code==202
        run_id=created.json()["run_id"]
        state=wait(client,run_id)
        assert state["status"]=="completed"
        assert state["offers"][0]["result"]=="MATCHES_CHECKED_SPECIFICATIONS"
        assert "text" not in state["sources"][0]
        response=client.post(f"/api/runs/{run_id}/clarifications",json={"installed_modules_gb":None,"free_slots":None})
        assert response.status_code==200
        assert client.get("/api/runs/"+run_id).json()["offers"][0]["result"]=="NEEDS_INFORMATION"
        assert "event: done" in client.get(f"/api/runs/{run_id}/events").text
        assert "Recorded manufacturer" in client.get(f"/api/runs/{run_id}/report").text

def test_api_bad_input_and_missing_keys(tmp_path):
    from pydantic import SecretStr
    with TestClient(create_app(Settings(_env_file=None,database_path=tmp_path/'api.db',serpapi_key=SecretStr(""),llm_api_key=SecretStr("")))) as client:
        assert client.post("/api/runs",json=payload(installed_modules_gb=[-8])).status_code==422
        assert client.post("/api/runs",json=payload(mode="live")).status_code==503
        assert client.get("/api/runs/not-found").status_code==404
