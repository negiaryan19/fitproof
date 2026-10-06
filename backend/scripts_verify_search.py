import asyncio
from app.config import get_settings
from app.services.serpapi.client import SerpApiClient
from app.services.errors import ServiceError

async def main():
    api = SerpApiClient(get_settings())
    try:
        data = await api.search('site:psref.lenovo.com "ThinkPad T480" memory')
    except ServiceError as error:
        print(error.code + ": " + error.message)
        return
    print({"requests": api.requests_used, "result_count": len(data["organic_results"]),
           "response_id": data["search_metadata"]["id"]})

if __name__ == "__main__":
    asyncio.run(main())

