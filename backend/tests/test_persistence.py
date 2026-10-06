import pytest
from app.db.store import SQLiteStore
from app.config import Settings
from app.schemas.domain import RunInput
from app.services.investigation.runner import Investigation,initial_state

@pytest.mark.asyncio
async def test_restart_preserves_evidence_and_normalized_rows(tmp_path):
    store=SQLiteStore(tmp_path/"test.sqlite")
    settings=Settings(_env_file=None)
    state=initial_state("saved",RunInput(device_model="Lenovo ThinkPad T480",installed_modules_gb=[8],free_slots=1,mode="replay"),settings)
    await Investigation(state,settings,sink=store.save).execute()
    reopened=SQLiteStore(tmp_path/"test.sqlite")
    persisted=reopened.get("saved")
    assert persisted["offers"][1]["result"]=="CONFLICT_FOUND"
    with reopened.connect() as db:
        assert db.execute("SELECT count(*) FROM facts").fetchone()[0]>10
        assert db.execute("SELECT count(*) FROM sources").fetchone()[0]==3

def test_interrupted_run_is_not_left_running(tmp_path):
    store=SQLiteStore(tmp_path/"test.sqlite")
    state=initial_state("unfinished",RunInput(device_model="Exact Model 1"),Settings(_env_file=None))
    store.save(state)
    store.recover()
    assert store.get("unfinished")["status"]=="interrupted"

