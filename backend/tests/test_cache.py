import httpx
import pytest
from pydantic import SecretStr
from app.config import Settings
from app.db.store import SQLiteStore
from app.db.cache import SearchCache
from app.services.serpapi.client import SerpApiClient

@pytest.mark.asyncio
async def test_repeated_query_uses_cache_and_preserves_locale(tmp_path):
    calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(200,json={'search_metadata':{'id':'test-response'},'organic_results':[]})
    settings=Settings(_env_file=None,serpapi_key=SecretStr('test'))
    cache=SearchCache(SQLiteStore(tmp_path/'cache.db'))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        api=SerpApiClient(settings,http,cache)
        first=await api.search('model','google','IN')
        second=await api.search('model','google','IN')
        assert first==second
        assert api.records[-1]['origin']=='cache'
        assert api.requests_used==1
        await api.search('model','google','US')
        assert len(calls)==2

def test_expired_cache_is_not_returned(tmp_path):
    cache=SearchCache(SQLiteStore(tmp_path/'cache.db'),ttl=1)
    cache.set({'q':'x'},{'test':True})
    with cache.store.connect() as db:
        db.execute('UPDATE search_cache SET created_at=0')
    assert cache.get({'q':'x'}) is None
