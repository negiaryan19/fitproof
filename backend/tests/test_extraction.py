import httpx
import pytest
from pydantic import SecretStr
from app.config import Settings
from app.schemas.domain import Source
from app.services.extraction.llm import LLMExtractor


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["gemini", "claude"])
async def test_provider_adapter_structured_extraction(provider):
    def handle(request):
        assert b"test-secret" not in request.content
        data = '{"facts":[{"subject":"Model A","field":"memory_generation","value":"DDR4","evidence_span":"DDR4 memory"}]}'
        if provider == "gemini":
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": data}]}}]})
        return httpx.Response(200, json={"content": [{"type": "text", "text": data}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        settings = Settings(
            _env_file=None,
            llm_provider=provider,
            llm_api_key=SecretStr("test-secret"),
            llm_model="test-model",
        )
        ext = LLMExtractor(settings, http)
        result = await ext.extract(
            Source(
                url="https://lenovo.com/a",
                title="Model A",
                publisher="Lenovo",
                source_type="manufacturer",
                text="Model A DDR4 memory",
            ),
            "Model A",
            "device",
            "Model A",
        )
        assert result.facts[0].value == "DDR4"


@pytest.mark.asyncio
async def test_malformed_output_repairs_only_once():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "not json"}]}}]})

    from app.services.errors import ServiceError

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        ext = LLMExtractor(Settings(_env_file=None, llm_api_key=SecretStr("key"), llm_model="test"), http)
        with pytest.raises(ServiceError, match="schema validation"):
            await ext.extract(
                Source(url="https://lenovo.com/a", title="A", publisher="Lenovo", source_type="manufacturer"),
                "Model A",
                "device",
                "Model A",
            )
    assert len(calls) == 2
