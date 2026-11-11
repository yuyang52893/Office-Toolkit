import json
from datetime import date
from pathlib import Path
from typing import Any

from app.common.errors import AppError


class RuntimeLogRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for_day(self, day: date) -> Path:
        return self.root / f"runtime-errors-{day.isoformat()}.jsonl"

    def list_errors(
        self,
        day: date,
        *,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        path = self.path_for_day(day)
        if not path.is_file():
            return {"items": [], "page": page, "page_size": page_size, "total": 0}

        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as source:
            for line in source:
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    records.append(value)

        records.reverse()
        start = (page - 1) * page_size
        return {
            "items": records[start : start + page_size],
            "page": page,
            "page_size": page_size,
            "total": len(records),
            "date": day.isoformat(),
        }

    def resolve_download(self, day: date) -> Path:
        path = self.path_for_day(day)
        if not path.is_file():
            raise AppError(
                "RUNTIME_LOG_NOT_FOUND",
                "指定日期的运行错误日志不存在",
                status_code=404,
            )
        return path
