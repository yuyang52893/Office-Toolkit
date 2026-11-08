import json
import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from app.common.errors import AppError
from app.config import Settings

_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class TempStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.temp_root.resolve()

    def prepare(self) -> None:
        (self.root / "uploads").mkdir(parents=True, exist_ok=True)
        (self.root / "results").mkdir(parents=True, exist_ok=True)

    def create_upload(self) -> tuple[str, Path]:
        self.prepare()
        upload_id = uuid4().hex
        upload_dir = self.root / "uploads" / upload_id
        (upload_dir / "files").mkdir(parents=True)
        return upload_id, upload_dir

    def discard_upload(self, upload_id: str) -> None:
        if not _ID_PATTERN.fullmatch(upload_id):
            return
        upload_dir = self.root / "uploads" / upload_id
        if upload_dir.is_dir():
            shutil.rmtree(upload_dir, ignore_errors=True)

    def write_upload(
        self,
        upload_dir: Path,
        filename: str,
        stream: BinaryIO,
        max_bytes: int,
    ) -> tuple[str, Path, int]:
        suffix = Path(filename).suffix.lower()
        stored_name = f"{uuid4().hex}{suffix}"
        target = upload_dir / "files" / stored_name
        total = 0
        try:
            with target.open("wb") as output:
                while chunk := stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise AppError(
                            "FILE_TOO_LARGE",
                            f"单个文件不能超过 {self.settings.max_file_mb}MB",
                            status_code=413,
                            details={"filename": filename},
                        )
                    output.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        if total == 0:
            target.unlink(missing_ok=True)
            raise AppError("EMPTY_FILE", "不能上传空文件", details={"filename": filename})
        return stored_name, target, total

    def write_upload_metadata(self, upload_id: str, metadata: dict[str, Any]) -> None:
        upload_dir = self._validated_dir("uploads", upload_id)
        metadata = dict(metadata)
        metadata["upload_id"] = upload_id
        metadata["expires_at"] = self._expiry().isoformat()
        (upload_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False),
            encoding="utf-8",
        )

    def read_upload_metadata(self, upload_id: str) -> dict[str, Any]:
        upload_dir = self._validated_dir("uploads", upload_id)
        metadata = self._read_metadata(upload_dir)
        if self._is_expired(metadata.get("expires_at")):
            shutil.rmtree(upload_dir, ignore_errors=True)
            raise AppError("UPLOAD_EXPIRED", "文件已过期，请重新上传", status_code=410)
        return metadata

    def upload_file_path(self, upload_id: str, stored_name: str) -> Path:
        upload_dir = self._validated_dir("uploads", upload_id)
        candidate = (upload_dir / "files" / Path(stored_name).name).resolve()
        files_dir = (upload_dir / "files").resolve()
        if candidate.parent != files_dir or not candidate.is_file():
            raise AppError("FILE_NOT_FOUND", "上传文件不存在")
        return candidate

    def create_result(
        self,
        filename: str,
        writer,
    ) -> tuple[dict[str, Any], Path]:
        self.prepare()
        result_id = uuid4().hex
        result_dir = self.root / "results" / result_id
        result_dir.mkdir(parents=True)
        target = result_dir / Path(filename).name
        try:
            writer(target)
        except Exception:
            shutil.rmtree(result_dir, ignore_errors=True)
            raise
        size = target.stat().st_size
        metadata = {
            "result_id": result_id,
            "filename": target.name,
            "size": size,
            "expires_at": self._expiry().isoformat(),
        }
        (result_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False),
            encoding="utf-8",
        )
        return metadata, target

    def resolve_result(self, result_id: str) -> tuple[Path, dict[str, Any]]:
        result_dir = self._validated_dir("results", result_id)
        metadata = self._read_metadata(result_dir)
        if self._is_expired(metadata.get("expires_at")):
            shutil.rmtree(result_dir, ignore_errors=True)
            raise AppError("RESULT_EXPIRED", "下载结果已过期，请重新处理", status_code=410)
        filename = Path(str(metadata.get("filename", ""))).name
        path = (result_dir / filename).resolve()
        if not filename or path.parent != result_dir.resolve() or not path.is_file():
            raise AppError("RESULT_NOT_FOUND", "下载结果不存在", status_code=404)
        return path, metadata

    def cleanup_expired(self, now: datetime | None = None) -> int:
        current = now or datetime.now(UTC)
        removed = 0
        for category in ("uploads", "results"):
            parent = self.root / category
            if not parent.exists():
                continue
            for item in parent.iterdir():
                if not item.is_dir():
                    continue
                expired = self._directory_expired(item, current)
                if expired:
                    shutil.rmtree(item, ignore_errors=True)
                    removed += 1
        return removed

    def _validated_dir(self, category: str, item_id: str) -> Path:
        if category not in {"uploads", "results"} or not _ID_PATTERN.fullmatch(item_id):
            raise AppError("INVALID_TOKEN", "无效的临时任务标识", status_code=404)
        item = (self.root / category / item_id).resolve()
        expected_parent = (self.root / category).resolve()
        if item.parent != expected_parent or not item.is_dir():
            raise AppError("NOT_FOUND", "临时任务不存在", status_code=404)
        return item

    @staticmethod
    def _read_metadata(directory: Path) -> dict[str, Any]:
        path = directory / "metadata.json"
        if not path.is_file():
            raise AppError("NOT_FOUND", "临时任务不存在", status_code=404)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AppError("STORAGE_ERROR", "临时文件信息损坏", status_code=500) from exc

    def _expiry(self) -> datetime:
        return datetime.now(UTC) + timedelta(minutes=self.settings.retention_minutes)

    @staticmethod
    def _is_expired(value: object) -> bool:
        if not isinstance(value, str):
            return True
        try:
            return datetime.fromisoformat(value) <= datetime.now(UTC)
        except ValueError:
            return True

    def _directory_expired(self, directory: Path, now: datetime) -> bool:
        metadata_path = directory / "metadata.json"
        if metadata_path.is_file():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                expires_at = datetime.fromisoformat(str(metadata["expires_at"]))
                return expires_at <= now
            except (KeyError, OSError, ValueError):
                pass
        modified = datetime.fromtimestamp(directory.stat().st_mtime, tz=UTC)
        return modified + timedelta(minutes=self.settings.retention_minutes) <= now

