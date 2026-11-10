from datetime import date
from pathlib import Path
from typing import Any

from app.config import Settings
from app.repositories.runtime_logs import RuntimeLogRepository


class RuntimeLogService:
    def __init__(self, settings: Settings) -> None:
        self.repository = RuntimeLogRepository(settings.runtime_log_dir)

    def list_errors(self, day: date, *, page: int, page_size: int) -> dict[str, Any]:
        return self.repository.list_errors(day, page=page, page_size=page_size)

    def resolve_download(self, day: date) -> Path:
        return self.repository.resolve_download(day)
