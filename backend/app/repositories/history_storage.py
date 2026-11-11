import logging
import os
import shutil
from pathlib import Path

from app.config import Settings

logger = logging.getLogger(__name__)


class HistoryStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.history_root.resolve()

    def prepare(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _directory(self, user_id: int, history_id: str) -> Path:
        return self.root / str(user_id) / history_id

    def write(
        self,
        *,
        user_id: int,
        history_id: str,
        source_path: Path,
        filename: str,
    ) -> str:
        suffix = Path(filename).suffix.lower()[:16]
        stored_name = f"{history_id}{suffix}"
        directory = self._directory(user_id, history_id)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / stored_name
        try:
            os.link(source_path, target)
        except OSError:
            shutil.copyfile(source_path, target)
        return stored_name

    def resolve(self, user_id: int, history_id: str, filename: str | None = None) -> Path:
        directory = self._directory(user_id, history_id)
        if filename:
            candidate = (directory / Path(filename).name).resolve()
            if candidate.parent == directory.resolve() and candidate.is_file():
                return candidate
            raise FileNotFoundError(candidate)
        files = (
            [path for path in directory.iterdir() if path.is_file()]
            if directory.is_dir()
            else []
        )
        if not files:
            raise FileNotFoundError(directory)
        return files[0]

    def delete_history_dir(self, user_id: int, history_id: str) -> bool:
        directory = self._directory(user_id, history_id)
        if not directory.exists():
            return True
        try:
            shutil.rmtree(directory)
            return True
        except OSError:
            logger.warning(
                "History file deletion failed; will retry",
                extra={"event": "history_cleanup_retry", "history_id": history_id},
            )
            return False
