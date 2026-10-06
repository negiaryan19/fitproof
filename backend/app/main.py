from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings, Settings
from app.routers.runs import router
from app.services.investigation.manager import RunManager
from app.db.store import SQLiteStore
from app.db.cache import SearchCache

def create_app(settings: Settings | None = None):
    provider = (lambda: settings) if settings is not None else get_settings
    store = SQLiteStore(provider().database_path)
    manager = RunManager(provider, store=store, cache=SearchCache(store,provider().search_cache_seconds))

    @asynccontextmanager
    async def lifespan(app):
        manager.store.recover()
        yield
        await manager.shutdown()

    app = FastAPI(title="FitProof", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.manager = manager
    app.add_middleware(CORSMiddleware, allow_origins=provider().cors_origins.split(","),
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    app.include_router(router)

    @app.get("/api/health")
    def health():
        return {"status":"ok", "app":"FitProof", **provider().readiness()}
    return app

app = create_app()
