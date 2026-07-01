from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: str = "dev-secret-change-in-production"
    encryption_key: str = ""
    environment: str = "development"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    database_url: str = "postgresql+asyncpg://scalpdesk:scalpdesk@localhost:5432/scalpdesk"
    redis_url: str = "redis://localhost:6379/0"

    jwt_access_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    kite_redirect_url: str = "http://localhost:8000/accounts/callback"

    market_open_login_time: str = "08:45"
    instrument_sync_time: str = "08:50"
    eod_squareoff_time: str = "15:20"
    timezone: str = "Asia/Kolkata"

    kite_instruments_url: str = "https://api.kite.trade/instruments"
    instrument_sync_batch_size: int = 1000
    # Public websocket key used with enctoken (Zerodha blocks REST quote/ltp for enctoken)
    kite_ws_api_key: str = "TradeViaPython"

    default_paper_mode: bool = True
    max_accounts_per_user: int = 5

    fyers_redirect_url: str = "http://localhost:8000/accounts/fyers-callback"
    ventura_redirect_url: str = "http://localhost:8000/accounts/ventura-callback"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
