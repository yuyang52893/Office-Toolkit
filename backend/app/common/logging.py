import json
import logging
import re
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import Settings

_STANDARD_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__)
_RUNTIME_FILE_PATTERN = re.compile(r"^runtime-errors-(\d{4}-\d{2}-\d{2})\.jsonl$")
_LOCAL_TIMEZONE = timezone(timedelta(hours=8))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_FIELDS and key not in {"message", "asctime"}:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _json_handler(handler: logging.Handler) -> logging.Handler:
    handler.setFormatter(JsonFormatter())
    return handler


def _runtime_path(root: Path, day: date) -> Path:
    return root / f"runtime-errors-{day.isoformat()}.jsonl"


def cleanup_runtime_logs(
    root: Path,
    *,
    now: datetime,
    retention_days: int,
    total_max_bytes: int,
    preserve: Path | None = None,
) -> int:
    if not root.is_dir():
        return 0

    dated_files: list[tuple[date, Path]] = []
    for path in root.iterdir():
        match = _RUNTIME_FILE_PATTERN.fullmatch(path.name)
        if not match or not path.is_file():
            continue
        try:
            day = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        dated_files.append((day, path))

    cutoff = now.astimezone(_LOCAL_TIMEZONE).date() - timedelta(days=retention_days - 1)
    removed = 0
    for day, path in sorted(dated_files):
        if day < cutoff:
            path.unlink(missing_ok=True)
            removed += 1

    remaining = [(day, path) for day, path in sorted(dated_files) if path.exists()]
    total_size = sum(path.stat().st_size for _, path in remaining)
    preserved = preserve.resolve() if preserve is not None else None
    for _, path in remaining:
        if total_size <= total_max_bytes:
            break
        if preserved is not None and path.resolve() == preserved:
            continue
        size = path.stat().st_size
        path.unlink(missing_ok=True)
        total_size -= size
        removed += 1
    return removed


class DailyCappedFileHandler(logging.Handler):
    def __init__(
        self,
        root: Path,
        *,
        max_bytes: int,
        retention_days: int,
        total_max_bytes: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__(level=logging.WARNING)
        self.root = root
        self.max_bytes = max_bytes
        self.retention_days = retention_days
        self.total_max_bytes = total_max_bytes
        self.clock = clock or (lambda: datetime.now(_LOCAL_TIMEZONE))
        self._stream = None
        self._stream_day: date | None = None
        self._cap_notified: set[date] = set()
        root.mkdir(parents=True, exist_ok=True)
        self._cleanup()

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.WARNING:
            return
        try:
            day = datetime.fromtimestamp(record.created, _LOCAL_TIMEZONE).date()
            path = self._open_for_day(day)
            payload = (self.format(record) + "\n").encode("utf-8")
            self._cleanup(preserve=path)
            current_size = path.stat().st_size
            projected_size = current_size + len(payload)
            if projected_size > self.max_bytes or not self._make_total_room(
                path,
                projected_size,
            ):
                self._notify_capacity(day)
                return
            assert self._stream is not None
            self._stream.write(payload)
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def _make_total_room(self, current_path: Path, projected_size: int) -> bool:
        if projected_size > self.total_max_bytes:
            return False

        current = current_path.resolve()
        dated_files: list[tuple[date, Path]] = []
        for path in self.root.iterdir():
            match = _RUNTIME_FILE_PATTERN.fullmatch(path.name)
            if not match or not path.is_file() or path.resolve() == current:
                continue
            try:
                day = date.fromisoformat(match.group(1))
            except ValueError:
                continue
            dated_files.append((day, path))

        other_size = sum(path.stat().st_size for _, path in dated_files)
        for _, path in sorted(dated_files):
            if other_size + projected_size <= self.total_max_bytes:
                break
            size = path.stat().st_size
            path.unlink(missing_ok=True)
            other_size -= size
        return other_size + projected_size <= self.total_max_bytes

    def _notify_capacity(self, day: date) -> None:
        if day in self._cap_notified:
            return
        self._cap_notified.add(day)
        sys.stderr.write(f"runtime error log capacity reached for {day.isoformat()}\n")
        sys.stderr.flush()

    def _open_for_day(self, day: date):
        if self._stream is not None and self._stream_day == day:
            return _runtime_path(self.root, day)
        if self._stream is not None:
            self._stream.close()
        path = _runtime_path(self.root, day)
        self._stream = path.open("ab")
        self._stream_day = day
        self._cleanup()
        return path

    def _cleanup(self, *, preserve: Path | None = None) -> None:
        cleanup_runtime_logs(
            self.root,
            now=self.clock(),
            retention_days=self.retention_days,
            total_max_bytes=self.total_max_bytes,
            preserve=preserve,
        )

    def close(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None
            self._stream_day = None
        super().close()


def configure_logging(settings: Settings) -> None:
    settings.runtime_log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=settings.log_level.upper(),
        handlers=[
            _json_handler(logging.StreamHandler(sys.stdout)),
            _json_handler(
                DailyCappedFileHandler(
                    settings.runtime_log_dir,
                    max_bytes=settings.runtime_log_max_bytes,
                    retention_days=settings.runtime_log_retention_days,
                    total_max_bytes=settings.runtime_log_total_bytes,
                )
            ),
        ],
        force=True,
    )
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)

