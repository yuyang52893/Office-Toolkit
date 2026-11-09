import csv
import re
import shutil
import tempfile
import threading
import time
import zipfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from openpyxl import Workbook

from app.common.errors import AppError
from app.config import Settings
from app.repositories.temp_storage import TempStorage
from app.schemas.excel import MergeRequest, SplitRequest
from app.services.excel_reader import SUPPORTED_SUFFIXES, CellValue, ExcelReader

_UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")
_ALLOWED_CONTENT_TYPES = {
    ".xlsx": {
        "application/octet-stream",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
    },
    ".xls": {
        "application/octet-stream",
        "application/vnd.ms-excel",
    },
    ".csv": {
        "application/csv",
        "application/octet-stream",
        "application/vnd.ms-excel",
        "text/csv",
        "text/plain",
    },
}


class ExcelService:
    def __init__(self, settings: Settings, storage: TempStorage) -> None:
        self.settings = settings
        self.storage = storage
        self.reader = ExcelReader(settings)
        self._excel_slots = threading.BoundedSemaphore(settings.excel_concurrency)

    def inspect(self, uploads: Iterable[Any]) -> dict[str, Any]:
        files = list(uploads)
        if not files:
            raise AppError("NO_FILES", "请至少选择一个文件")
        if len(files) > self.settings.max_files:
            raise AppError(
                "TOO_MANY_FILES",
                f"单次最多上传 {self.settings.max_files} 个文件",
                status_code=413,
            )

        with self._slot():
            upload_id, upload_dir = self.storage.create_upload()
            total_bytes = 0
            metadata_files: list[dict[str, Any]] = []
            try:
                for upload in files:
                    original_name = Path(str(getattr(upload, "filename", ""))).name
                    suffix = Path(original_name).suffix.lower()
                    if not original_name or suffix not in SUPPORTED_SUFFIXES:
                        raise AppError(
                            "UNSUPPORTED_FILE",
                            "仅支持 xlsx、xls 和 csv 文件",
                            status_code=415,
                            details={"filename": original_name or "未命名文件"},
                        )
                    content_type = (
                        str(getattr(upload, "content_type", "") or "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                    )
                    if content_type and content_type not in _ALLOWED_CONTENT_TYPES[suffix]:
                        raise AppError(
                            "FILE_TYPE_MISMATCH",
                            "文件扩展名与文件类型不一致，请选择正确的文件",
                            status_code=415,
                            details={"filename": original_name, "content_type": content_type},
                        )
                    stored_name, path, size = self.storage.write_upload(
                        upload_dir,
                        original_name,
                        upload.file,
                        self.settings.max_file_bytes,
                    )
                    total_bytes += size
                    if total_bytes > self.settings.max_task_bytes:
                        raise AppError(
                            "TASK_TOO_LARGE",
                            f"单次任务总文件不能超过 {self.settings.max_task_mb}MB",
                            status_code=413,
                        )
                    sheets = self.reader.inspect(path)
                    if not sheets:
                        raise AppError(
                            "EMPTY_WORKBOOK",
                            "文件中没有可读取的工作表",
                            details={"filename": original_name},
                        )
                    metadata_files.append(
                        {
                            "file_id": uuid4().hex,
                            "original_name": original_name,
                            "stored_name": stored_name,
                            "format": suffix.removeprefix("."),
                            "size": size,
                            "sheets": sheets,
                        }
                    )

                metadata = {
                    "files": metadata_files,
                    "total_size": total_bytes,
                }
                self.storage.write_upload_metadata(upload_id, metadata)
                stored = self.storage.read_upload_metadata(upload_id)
            except Exception:
                self.storage.discard_upload(upload_id)
                raise

        return {
            "upload_id": upload_id,
            "expires_at": stored["expires_at"],
            "files": [
                {
                    "file_id": item["file_id"],
                    "name": item["original_name"],
                    "format": item["format"],
                    "size": item["size"],
                    "sheets": item["sheets"],
                }
                for item in stored["files"]
            ],
        }

    def split(self, request: SplitRequest) -> dict[str, Any]:
        deadline = time.monotonic() + self.settings.excel_timeout_seconds
        with self._slot():
            upload, selected = self._load_selection(request.upload_id, request.sheets)
            if request.mode == "by_column":
                self._ensure_column_exists(selected, request.column_index or 0)
            with tempfile.TemporaryDirectory(dir=str(self.storage.root)) as temp_name:
                scratch = Path(temp_name)
                output_dir = scratch / "output"
                output_dir.mkdir()
                output_count = self._run_split(
                    upload,
                    selected,
                    request,
                    output_dir,
                    deadline,
                )
                archive_path = scratch / self._result_name("拆分结果", ".zip")
                self._zip_directory(output_dir, archive_path)
                metadata, _ = self.storage.create_result(
                    archive_path.name,
                    lambda target: shutil.copyfile(archive_path, target),
                )
        return self._public_result(metadata, output_count)

    def merge(self, request: MergeRequest) -> dict[str, Any]:
        deadline = time.monotonic() + self.settings.excel_timeout_seconds
        with self._slot():
            upload, selected = self._load_selection(request.upload_id, request.sheets)
            headers = self._target_headers(selected, request)
            with tempfile.TemporaryDirectory(dir=str(self.storage.root)) as temp_name:
                scratch = Path(temp_name)
                output_path = scratch / self._result_name("合并结果", ".xlsx")
                row_count = self._write_merge(
                    upload,
                    selected,
                    request,
                    headers,
                    output_path,
                    deadline,
                )
                metadata, _ = self.storage.create_result(
                    output_path.name,
                    lambda target: shutil.copyfile(output_path, target),
                )
        return self._public_result(metadata, 1, row_count=row_count)

    def _run_split(
        self,
        upload: dict[str, Any],
        selected: list[tuple[dict[str, Any], dict[str, Any]]],
        request: SplitRequest,
        output_dir: Path,
        deadline: float,
    ) -> int:
        used_names: set[str] = set()
        output_count = 0
        for file_meta, sheet_meta in selected:
            self._check_deadline(deadline)
            path = self.storage.upload_file_path(upload["upload_id"], file_meta["stored_name"])
            source_suffix = path.suffix.lower()
            output_suffix = ".csv" if source_suffix == ".csv" else ".xlsx"
            file_stem = self._safe_component(Path(file_meta["original_name"]).stem, "数据")
            sheet_part = self._safe_component(sheet_meta["name"], "工作表")
            with self.reader.stream_table(
                path,
                sheet_index=sheet_meta["sheet_index"],
                sheet_name=sheet_meta["name"],
                has_header=request.has_header,
                width=sheet_meta["column_count"],
            ) as (headers, rows):
                filtered = self._filter_rows(rows, request)
                if request.mode == "by_sheet":
                    filename = self._unique_filename(
                        f"{file_stem}_{sheet_part}{output_suffix}",
                        used_names,
                    )
                    self._write_table(
                        output_dir / filename,
                        headers,
                        filtered,
                        include_header=request.has_header,
                        deadline=deadline,
                    )
                    output_count += 1
                elif request.mode == "by_rows":
                    output_count += self._split_rows(
                        output_dir,
                        f"{file_stem}_{sheet_part}",
                        output_suffix,
                        headers,
                        filtered,
                        request,
                        used_names,
                        deadline,
                    )
                else:
                    output_count += self._split_column(
                        output_dir,
                        f"{file_stem}_{sheet_part}",
                        output_suffix,
                        headers,
                        filtered,
                        request,
                        used_names,
                        deadline,
                    )
                if output_count > self.settings.max_output_files:
                    raise AppError(
                        "TOO_MANY_OUTPUTS",
                        f"结果文件不能超过 {self.settings.max_output_files} 个",
                        status_code=413,
                    )
        return output_count

    def _split_rows(
        self,
        output_dir: Path,
        stem: str,
        suffix: str,
        headers: list[str],
        rows: Iterator[list[CellValue]],
        request: SplitRequest,
        used_names: set[str],
        deadline: float,
    ) -> int:
        chunk_size = request.rows_per_file or 1
        count = 0
        chunk: list[list[CellValue]] = []
        for row in rows:
            self._check_deadline(deadline)
            chunk.append(row)
            if len(chunk) >= chunk_size:
                count += 1
                self._write_chunk(
                    output_dir,
                    stem,
                    suffix,
                    headers,
                    chunk,
                    count,
                    request.has_header,
                    used_names,
                    deadline,
                )
                if count > self.settings.max_output_files:
                    raise AppError(
                        "TOO_MANY_OUTPUTS",
                        f"结果文件不能超过 {self.settings.max_output_files} 个",
                        status_code=413,
                    )
                chunk = []
        if chunk:
            count += 1
            self._write_chunk(
                output_dir,
                stem,
                suffix,
                headers,
                chunk,
                count,
                request.has_header,
                used_names,
                deadline,
            )
        if count == 0 and request.has_header:
            count = 1
            self._write_chunk(
                output_dir,
                stem,
                suffix,
                headers,
                [],
                1,
                True,
                used_names,
                deadline,
            )
        return count

    def _split_column(
        self,
        output_dir: Path,
        stem: str,
        suffix: str,
        headers: list[str],
        rows: Iterator[list[CellValue]],
        request: SplitRequest,
        used_names: set[str],
        deadline: float,
    ) -> int:
        column_index = request.column_index or 0
        groups: dict[str, list[list[CellValue]]] = {}
        for row in rows:
            self._check_deadline(deadline)
            raw = row[column_index] if column_index < len(row) else None
            label = self._group_label(raw)
            groups.setdefault(label, []).append(row)
            if len(groups) > self.settings.max_output_files:
                raise AppError(
                    "TOO_MANY_OUTPUTS",
                    f"结果文件不能超过 {self.settings.max_output_files} 个",
                    status_code=413,
                )
        if not groups:
            groups["空值"] = []

        for label, group_rows in groups.items():
            safe_label = self._safe_component(label, "空值")
            filename = self._unique_filename(
                f"{stem}_{safe_label}{suffix}",
                used_names,
            )
            self._write_table(
                output_dir / filename,
                headers,
                iter(group_rows),
                include_header=request.has_header,
                deadline=deadline,
            )
        return len(groups)

    def _write_chunk(
        self,
        output_dir: Path,
        stem: str,
        suffix: str,
        headers: list[str],
        rows: list[list[CellValue]],
        part: int,
        include_header: bool,
        used_names: set[str],
        deadline: float,
    ) -> None:
        filename = self._unique_filename(f"{stem}_第{part:03d}部分{suffix}", used_names)
        self._write_table(
            output_dir / filename,
            headers,
            iter(rows),
            include_header=include_header,
            deadline=deadline,
        )

    def _write_merge(
        self,
        upload: dict[str, Any],
        selected: list[tuple[dict[str, Any], dict[str, Any]]],
        request: MergeRequest,
        target_headers: list[str],
        output_path: Path,
        deadline: float,
    ) -> int:
        seen: set[tuple[CellValue, ...]] = set()
        row_count = 0
        workbook = Workbook(write_only=True)
        worksheet = workbook.create_sheet("合并结果")
        if request.has_header and target_headers:
            worksheet.append(target_headers)
        try:
            for file_meta, sheet_meta in selected:
                self._check_deadline(deadline)
                path = self.storage.upload_file_path(
                    upload["upload_id"],
                    file_meta["stored_name"],
                )
                with self.reader.stream_table(
                    path,
                    sheet_index=sheet_meta["sheet_index"],
                    sheet_name=sheet_meta["name"],
                    has_header=request.has_header,
                    width=sheet_meta["column_count"],
                ) as (source_headers, rows):
                    index_map = self._merge_index_map(
                        source_headers,
                        target_headers,
                        request.header_strategy,
                    )
                    for row in rows:
                        self._check_deadline(deadline)
                        aligned = [None] * len(target_headers)
                        for source_index, target_index in enumerate(index_map):
                            if target_index is not None and source_index < len(row):
                                aligned[target_index] = row[source_index]
                        if self._skip_row(aligned, request, seen):
                            continue
                        worksheet.append(aligned)
                        row_count += 1
            workbook.save(output_path)
        finally:
            workbook.close()
        return row_count

    def _load_selection(
        self,
        upload_id: str,
        references,
    ) -> tuple[dict[str, Any], list[tuple[dict[str, Any], dict[str, Any]]]]:
        upload = self.storage.read_upload_metadata(upload_id)
        file_map = {item["file_id"]: item for item in upload["files"]}
        selected = []
        seen: set[tuple[str, int]] = set()
        for reference in references:
            key = (reference.file_id, reference.sheet_index)
            if key in seen:
                raise AppError("DUPLICATE_SHEET", "不能重复选择同一个工作表")
            seen.add(key)
            file_meta = file_map.get(reference.file_id)
            if file_meta is None:
                raise AppError("FILE_NOT_FOUND", "所选文件不存在，请重新上传")
            sheet_meta = next(
                (
                    sheet
                    for sheet in file_meta["sheets"]
                    if sheet["sheet_index"] == reference.sheet_index
                ),
                None,
            )
            if sheet_meta is None:
                raise AppError("SHEET_NOT_FOUND", "所选工作表不存在")
            selected.append((file_meta, sheet_meta))
        if len(selected) > self.settings.max_sheets:
            raise AppError(
                "TOO_MANY_SHEETS",
                f"单次最多处理 {self.settings.max_sheets} 个工作表",
            )
        return upload, selected

    def _target_headers(
        self,
        selected: list[tuple[dict[str, Any], dict[str, Any]]],
        request: MergeRequest,
    ) -> list[str]:
        headers = [sheet["headers"] for _, sheet in selected]
        if request.header_strategy == "strict":
            first = headers[0] if request.has_header else self._positional_headers(selected[0][1])
            for file_meta, sheet_meta in selected[1:]:
                current = sheet_meta["headers"] if request.has_header else self._positional_headers(
                    sheet_meta
                )
                if current != first:
                    raise AppError(
                        "HEADER_MISMATCH",
                        "所选工作表的表头不一致，可改用“按列名对齐”",
                        details={
                            "first_sheet": selected[0][0]["original_name"]
                            + "/"
                            + selected[0][1]["name"],
                            "mismatched_sheet": (
                                file_meta["original_name"] + "/" + sheet_meta["name"]
                            ),
                        },
                    )
            return first

        if not request.has_header:
            max_width = max(sheet["column_count"] for _, sheet in selected)
            return [f"列{index + 1}" for index in range(max_width)]
        merged: list[str] = []
        for header_list in headers:
            for header in header_list:
                if header not in merged:
                    merged.append(header)
        return merged

    def _merge_index_map(
        self,
        source_headers: list[str],
        target_headers: list[str],
        strategy: str,
    ) -> list[int | None]:
        if strategy == "strict":
            return list(range(len(target_headers)))
        lookup = {value: index for index, value in enumerate(target_headers)}
        return [lookup.get(value) for value in source_headers]

    @staticmethod
    def _positional_headers(sheet_meta: dict[str, Any]) -> list[str]:
        return [f"列{index + 1}" for index in range(sheet_meta["column_count"])]

    @staticmethod
    def _ensure_column_exists(
        selected: list[tuple[dict[str, Any], dict[str, Any]]],
        column_index: int,
    ) -> None:
        invalid = [sheet["name"] for _, sheet in selected if column_index >= sheet["column_count"]]
        if invalid:
            raise AppError(
                "COLUMN_NOT_FOUND",
                "所选列在工作表中不存在",
                details={"sheets": invalid},
            )

    def _filter_rows(
        self,
        rows: Iterator[list[CellValue]],
        request: SplitRequest,
    ) -> Iterator[list[CellValue]]:
        seen: set[tuple[CellValue, ...]] = set()
        for row in rows:
            if self._skip_row(row, request, seen):
                continue
            yield row

    def _skip_row(
        self,
        row: list[CellValue],
        options,
        seen: set[tuple[CellValue, ...]],
    ) -> bool:
        if options.remove_empty_rows and all(self._is_blank(value) for value in row):
            return True
        if options.remove_duplicates:
            key = tuple(self._normalize_for_compare(value) for value in row)
            if key in seen:
                return True
            seen.add(key)
        return False

    @classmethod
    def _normalize_for_compare(cls, value: CellValue):
        if isinstance(value, str):
            return value.strip()
        return value

    def _write_table(
        self,
        target: Path,
        headers: list[str],
        rows: Iterator[list[CellValue]],
        *,
        include_header: bool,
        deadline: float,
    ) -> None:
        if target.suffix.lower() == ".csv":
            with target.open("w", encoding="utf-8-sig", newline="") as output:
                writer = csv.writer(output)
                if include_header:
                    writer.writerow(headers)
                for row in rows:
                    self._check_deadline(deadline)
                    writer.writerow([self._csv_value(value) for value in row])
            return

        workbook = Workbook(write_only=True)
        worksheet = workbook.create_sheet("数据")
        try:
            if include_header:
                worksheet.append(headers)
            for row in rows:
                self._check_deadline(deadline)
                worksheet.append(row)
            workbook.save(target)
        finally:
            workbook.close()

    def _zip_directory(self, directory: Path, archive_path: Path) -> None:
        with zipfile.ZipFile(
            archive_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for path in sorted(directory.iterdir()):
                if path.is_file():
                    archive.write(path, arcname=path.name)

    @staticmethod
    def _csv_value(value: CellValue) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.isoformat(sep=" ")
        if hasattr(value, "isoformat"):
            return str(value.isoformat())
        return str(value)

    @staticmethod
    def _group_label(value: CellValue) -> str:
        if ExcelService._is_blank(value):
            return "空值"
        return ExcelService._csv_value(value)

    @staticmethod
    def _is_blank(value: CellValue) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    @staticmethod
    def _safe_component(value: str, fallback: str) -> str:
        cleaned = _UNSAFE_FILENAME.sub("_", value).strip(" ._")
        cleaned = _WHITESPACE.sub(" ", cleaned)
        return (cleaned[:80] or fallback).strip()

    @staticmethod
    def _unique_filename(filename: str, used_names: set[str]) -> str:
        candidate = filename
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        index = 2
        while candidate.casefold() in used_names:
            candidate = f"{stem}_{index}{suffix}"
            index += 1
        used_names.add(candidate.casefold())
        return candidate

    @staticmethod
    def _result_name(prefix: str, suffix: str) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}{suffix}"

    @staticmethod
    def _public_result(
        metadata: dict[str, Any],
        output_count: int,
        row_count: int | None = None,
    ) -> dict[str, Any]:
        result = {
            "result_id": metadata["result_id"],
            "filename": metadata["filename"],
            "size": metadata["size"],
            "expires_at": metadata["expires_at"],
            "download_url": f"/api/v1/results/{metadata['result_id']}",
            "output_count": output_count,
        }
        if row_count is not None:
            result["row_count"] = row_count
        return result

    @staticmethod
    def _check_deadline(deadline: float) -> None:
        if time.monotonic() > deadline:
            raise AppError(
                "PROCESSING_TIMEOUT",
                "文件处理超时，请减少文件数量或拆分批次",
                status_code=408,
            )

    @contextmanager
    def _slot(self):
        acquired = self._excel_slots.acquire(timeout=3)
        if not acquired:
            raise AppError(
                "SERVER_BUSY",
                "当前处理任务较多，请稍后重试",
                status_code=429,
            )
        try:
            yield
        finally:
            self._excel_slots.release()

