from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "轻办公工具箱 API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = (
        "mysql+pymysql://office_tools:office_tools_dev@127.0.0.1:3306/"
        "office_tools?charset=utf8mb4"
    )
    jwt_secret: str = "development-only-change-this-secret-32"
    jwt_expire_minutes: int = Field(default=720, ge=1, le=24 * 60)
    auth_login_per_minute: int = Field(default=10, ge=1)
    auth_recovery_question_per_minute: int = Field(default=5, ge=1)
    auth_recovery_password_per_minute: int = Field(default=5, ge=1)
    auth_recovery_password_window_seconds: int = Field(default=900, ge=60, le=3600)
    temp_root: Path = Path("./tmp")
    log_dir: Path = Path("./logs")
    log_file_name: str = "app.jsonl"
    log_level: str = "INFO"
    log_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    log_backup_count: int = Field(default=7, ge=1, le=100)
    trust_proxy_headers: bool = False
    rate_limit_per_minute: int = Field(default=60, ge=1)
    excel_rate_limit_per_minute: int = Field(default=10, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    rate_limit_max_entries: int = Field(default=10_000, ge=100, le=1_000_000)
    cors_origins: str = ""
    alert_webhook_url: str = ""
    alert_webhook_timeout_seconds: int = Field(default=3, ge=1, le=30)
    alert_cooldown_seconds: int = Field(default=60, ge=1, le=3600)
    retention_minutes: int = Field(default=30, ge=1, le=1440)
    cleanup_interval_seconds: int = Field(default=60, ge=10, le=3600)
    max_file_mb: int = Field(default=50, ge=1, le=500)
    max_task_mb: int = Field(default=100, ge=1, le=1000)
    max_files: int = Field(default=20, ge=1, le=100)
    max_sheets: int = Field(default=100, ge=1, le=500)
    max_output_files: int = Field(default=1000, ge=1, le=5000)
    max_sheet_rows: int = Field(default=200_000, ge=1, le=1_000_000)
    max_sheet_columns: int = Field(default=1000, ge=1, le=5000)
    max_xlsx_uncompressed_mb: int = Field(default=250, ge=1, le=2000)
    max_xlsx_entries: int = Field(default=10_000, ge=1, le=100_000)
    max_task_uncompressed_mb: int = Field(default=500, ge=1, le=5000)
    max_task_cells: int = Field(default=2_000_000, ge=1, le=50_000_000)
    excel_timeout_seconds: int = Field(default=120, ge=5, le=900)
    excel_concurrency: int = Field(default=2, ge=1, le=8)
    qr_max_mb: int = Field(default=10, ge=1, le=100)
    qr_max_pixels: int = Field(default=40_000_000, ge=1_000_000, le=200_000_000)

    @model_validator(mode="after")
    def reject_insecure_production_secrets(self) -> "Settings":
        if self.app_env != "production":
            return self
        if "office_tools_dev" in self.database_url:
            raise ValueError("生产环境必须使用独立数据库连接信息")
        if self.jwt_secret.startswith("development-only") or len(self.jwt_secret) < 32:
            raise ValueError("生产环境必须配置至少 32 个字符的独立 JWT_SECRET")
        return self

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024

    @property
    def max_task_bytes(self) -> int:
        return self.max_task_mb * 1024 * 1024

    @property
    def max_task_uncompressed_bytes(self) -> int:
        return self.max_task_uncompressed_mb * 1024 * 1024

    @property
    def qr_max_bytes(self) -> int:
        return self.qr_max_mb * 1024 * 1024

    @property
    def log_path(self) -> Path:
        return self.log_dir / self.log_file_name

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [
            item.strip().rstrip("/") for item in self.cors_origins.split(",") if item.strip()
        ]
        if "*" in origins:
            raise ValueError("CORS_ORIGINS 不允许通配符")
        for origin in origins:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"无效的 CORS 来源: {origin}")
        return origins

