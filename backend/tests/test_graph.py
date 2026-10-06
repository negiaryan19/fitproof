import pytest
from app.config import Settings
from app.schemas.domain import RunInput
from app.services.investigation.runner import Investigation, initial_state, possible_sku
from app.services.extraction.replay import ReplayExtractor, replay_sources


@pytest.mark.asyncio
async def test_replay_complete_chain_has_real_checks():
    settings = Settings(_env_file=None)
    state = initial_state(
        "test",
        RunInput(device_model="Lenovo ThinkPad T480", installed_modules_gb=[8], free_slots=1, mode="replay"),
        settings,
    )
    await Investigation(state, settings).execute()
    assert state["status"] == "completed"
    assert [o["result"] for o in state["offers"]] == [
        "MATCHES_CHECKED_SPECIFICATIONS",
        "CONFLICT_FOUND",
        "NEEDS_INFORMATION",
    ]
    assert state["queries_used"] == 0
    assert all(s["origin"] == "replay" for s in state["sources"])
    assert next(
        c for c in state["checks"] if c["check_type"] == "memory_form_factor" and c["status"] == "conflict"
    )["source_ids"]
    assert any(e["stage"] == "parts" for e in state["events"])


@pytest.mark.asyncio
async def test_mocked_live_search_to_final_result():
    class FakeSearch:
        requests_used = 0
        records = []

        async def search(self, q, engine, country):
            self.requests_used += 1
            self.records.append({"id": "mock-search", "origin": "live"})
            src = replay_sources()[0 if "ThinkPad" in q else 1]
            return {"organic_results": [{"title": src.title, "link": src.url}]}

    async def fetch(source):
        return next(s for s in replay_sources() if s.url == source.url)

    settings = Settings(_env_file=None)
    state = initial_state(
        "mock",
        RunInput(
            device_model="Lenovo ThinkPad T480",
            installed_modules_gb=[8],
            free_slots=1,
            part_number="KCP432SD8/16",
        ),
        settings,
    )
    await Investigation(
        state, settings, search=FakeSearch(), extractor=ReplayExtractor(), fetcher=fetch
    ).execute()
    assert state["status"] == "completed"
    assert state["offers"][0]["result"] == "MATCHES_CHECKED_SPECIFICATIONS"
    assert state["queries_used"] == 2


def test_google_product_id_is_never_a_sku():
    assert possible_sku("16GB DDR4 laptop memory") is None
    assert possible_sku("Kingston KCP432SD8/16 16GB") == "KCP432SD8/16"
