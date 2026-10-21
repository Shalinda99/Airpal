from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    app_name: str = "Airpal API"
    database_url: str = "postgresql+psycopg://airpal:airpal@localhost:5432/airpal"
    redis_url: str = ""  # empty => in-memory cache (dev/tests)
    cors_origins: str = "http://localhost:5173,http://localhost:8081,http://localhost:8082"

    jwt_secret: str = "change-me-in-production-please-32b"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    # 32 byte key, base64 urlsafe. Generate: python -c "import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
    data_encryption_key: str = "ZGV2LW9ubHkta2V5LWRvLW5vdC11c2UtaW4tcHJvZA=="
    blind_index_key: str = "dev-blind-index-key"

    # Flights
    flight_provider: str = "mock"  # mock | aerodatabox
    aerodatabox_api_key: str = ""
    aerodatabox_host: str = "aerodatabox.p.rapidapi.com"
    flights_cache_ttl: int = 60
    weather_cache_ttl: int = 600

    # Routing
    routing_provider: str = "osrm"  # osrm | google | haversine
    osrm_url: str = "https://router.project-osrm.org"
    google_maps_api_key: str = ""

    # Rides
    uber_client_id: str = ""

    # LLM / embeddings
    llm_provider: str = "extractive"  # extractive | anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-latest"
    embedding_provider: str = "hash"  # hash | openai
    embedding_dim: int = 1024
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_embedding_model: str = "text-embedding-3-small"
    agent_min_score: float = 0.25
    agent_rate_per_minute: int = 12

    push_provider: str = "expo"
    review_reminder_days: int = 90
    ticket_retention_days: int = 3
    portal_url: str = "http://localhost:5173"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_prod and (s.jwt_secret.startswith("change-me") or s.data_encryption_key.startswith("ZGV2")):
        raise RuntimeError("Insecure default secrets in production")
    return s


settings = get_settings()
