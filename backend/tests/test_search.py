import httpx
import pytest
from pydantic import SecretStr
from app.config import Settings
from app.services.errors import ServiceError
from app.services.serpapi.client import SerpApiClient


def settings(**kwargs):
    return Settings(_env_file=None, serpapi_key=SecretStr("test-key"), **kwargs)


@pytest.mark.asyncio
async def test_actual_contract_fields_and_secret_redaction():
    def handler(request):
        assert request.url.params["engine"] == "google"
        assert request.url.params["gl"] == "in"
        return httpx.Response(
            200,
            json={
                "search_metadata": {"id": "recorded-test"},
                "organic_results": [
                    {"title": "Manual", "link": "https://example.com/manual", "snippet": "DDR4"}
                ],
                "shopping_results": [
                    {"product_id": "google-identifier", "title": "Generic RAM", "serpapi_link": "secret"}
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        api = SerpApiClient(settings(), http)
        data = await api.search("exact model")
    assert api.requests_used == 1
    assert api.records[0]["response_id"] == "recorded-test"
    assert data["shopping_results"][0]["product_id"] == "google-identifier"
    assert "serpapi_link" not in data["shopping_results"][0]


@pytest.mark.asyncio
async def test_retries_cannot_exceed_budget():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(429))) as http:
        api = SerpApiClient(settings(max_searches=2), http)
        with pytest.raises(ServiceError, match="limit reached"):
            await api.search("q")
        assert api.requests_used == 2


@pytest.mark.asyncio
async def test_missing_key_does_not_search():
    api = SerpApiClient(Settings(_env_file=None, serpapi_key=SecretStr("")))
    with pytest.raises(ServiceError, match="SERPAPI_KEY"):
        await api.search("q")
    assert api.requests_used == 0


@pytest.mark.asyncio
async def test_failed_auth_does_not_leak_credentials():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(401))) as http:
        api = SerpApiClient(settings(), http)
        with pytest.raises(ServiceError) as exc:
            await api.search("q")
        assert "test-key" not in str(exc.value)
        assert api.requests_used == 1
