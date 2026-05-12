from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    JUMPCLOUD_API_KEY: str = ""

    @model_validator(mode="after")
    def check_api_key(self) -> "Settings":
        if not self.JUMPCLOUD_API_KEY:
            import warnings
            warnings.warn(
                "JUMPCLOUD_API_KEY is not set — all API calls will return 401. "
                "Set it in .env or via environment variable.",
                stacklevel=2,
            )
        return self

    JUMPCLOUD_ORG_ID: str = ""  # x-org-id for multi-tenant

    MCP_TRANSPORT: str = "stdio"
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8002
    MCP_SECRET_TOKEN: str = ""

    LOG_LEVEL: str = "INFO"

    # Write guard — set ALLOW_WRITE=true in .env to enable mutations
    ALLOW_WRITE: bool = False

    # Prometheus metrics server
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    METRICS_COLLECT_INTERVAL: int = 300  # seconds between collection runs

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
