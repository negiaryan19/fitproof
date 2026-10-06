from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env", ROOT / "backend" / ".env"), extra="ignore", env_file_encoding="utf-8"
    )
    serpapi_key: SecretStr = SecretStr("")
    llm_api_key: SecretStr = SecretStr("")
    llm_provider: Literal["gemini", "claude"] = "gemini"
    llm_model: str = ""
    max_searches: int = Field(default=12, ge=1, le=50)
    max_followup_rounds: int = Field(default=2, ge=0, le=3)
    max_offers: int = Field(default=5, ge=1, le=5)
    search_cache_seconds: int = Field(default=3600, ge=0)
    enable_replay: bool = True
    cors_origins: str = "http://127.0.0.1:5177,http://localhost:5177"
    database_path: Path = ROOT / "data" / "fitproof.sqlite3"
    request_timeout: float = 25.0
    run_timeout: float = 240.0

    def readiness(self) -> dict:
        missing = []
        if not self.serpapi_key.get_secret_value():
            missing.append("SERPAPI_KEY")
        if not self.llm_api_key.get_secret_value():
            missing.append("LLM_API_KEY")
        if not self.llm_model:
            missing.append("LLM_MODEL")
        return {"live_ready": not missing, "missing": missing, "replay_available": self.enable_replay}


def get_settings() -> Settings:
    return Settings()
