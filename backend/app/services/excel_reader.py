import csv
import io
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

from charset_normalizer import from_bytes
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from xlrd import XL_CELL_DATE, XL_CELL_TEXT, open_workbook, xldate_as_datetime
from xlrd.biffh import XLRDError

from app.common.errors import AppError
from app.config import Settings

CellValue = str | int | float | bool | date | datetime | None
SUPPORTED_SUFFIXES = {".xlsx", ".xls", ".csv"}

_XLS_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
_XLSX_SIGNATURE = b"PK"
_CSV_SAMPLE_SIZE = 64 * 1024
_MAX_CSV_FIELD_SIZE = 1_000_000


class ExcelReader:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        csv.field_size_limit(_MAX_CSV_FIELD_SIZE)

    def inspect(self, path: Path) -> tuple[list[dict[str, Any]], int]:
        suffix = path.suffix.lower()
        uncompressed_size = self._validate_container(path, suffix)
        try:
            if suffix == ".xlsx":
                return self._inspect_xlsx(path), uncompressed_size
            if suffix == ".xls":
                return self._inspect_xls(path), uncompressed_size
            return [self._inspect_csv(path)], uncompressed_size
        except AppError:
            raise
        except (InvalidFileException, XLRDError, OSError, ValueError, csv.Error) as exc:
            raise AppError(
                "INVALID_SPREADSHEET",
                "文件损坏、已加密或不是有效的表格文件",
                details={"filename": path.name},
            ) from exc

    @contextmanager
    def stream_table(
        self,
        path: Path,
        *,
        sheet_index: int,
        sheet_name: str,
        has_header: bool,
        width: int,
    ) -> Iterator[tuple[list[str], Iterator[list[CellValue]]]]:
        suffix = path.suffix.lower()
        workbook = None
        try:
            if suffix == ".xlsx":
                workbook = load_workbook(path, read_only=True, data_only=True)
                if sheet_index >= len(workbook.worksheets):
                    raise AppError("SHEET_NOT_FOUND", "所选工作表不存在")
                rows = self._iter_xlsx_sheet(workbook.worksheets[sheet_index])
            elif suffix == ".xls":
                workbook = open_workbook(path, on_demand=True)
                if sheet_index >= workbook.nsheets:
                    raise AppError("SHEET_NOT_FOUND", "所选工作表不存在")
                rows = self._iter_xls_sheet(workbook, workbook.sheet_by_index(sheet_index))
            elif suffix == ".csv":
                rows = self._iter_csv_rows(path)
            else:
                raise AppError("UNSUPPORTED_FILE", "仅支持 xlsx、xls 和 csv 文件")

            header_source, data_rows = self._split_header(rows, has_header)
            headers = self._normalize_headers(header_source, width)
            yield headers, (self._normalize_row(row, width) for row in data_rows)
        finally:
            if workbook is not None:
                workbook.close()

    def _inspect_xlsx(self, path: Path) -> list[dict[str, Any]]:
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            if not workbook.worksheets:
                raise AppError("EMPTY_WORKBOOK", "文件中没有工作表")
            results = []
            for index, sheet in enumerate(workbook.worksheets):
                info = self._scan_rows(
                    sheet.title,
                    index,
                    self._iter_xlsx_sheet(sheet),
                )
                results.append(info)
            return results
        finally:
            workbook.close()

    def _inspect_xls(self, path: Path) -> list[dict[str, Any]]:
        workbook = open_workbook(path, on_demand=True)
        try:
            if workbook.nsheets == 0:
                raise AppError("EMPTY_WORKBOOK", "文件中没有工作表")
            return [
                self._scan_rows(
                    workbook.sheet_by_index(index).name,
                    index,
                    self._iter_xls_sheet(workbook, workbook.sheet_by_index(index)),
                )
                for index in range(workbook.nsheets)
            ]
        finally:
            workbook.release_resources()

    def _inspect_csv(self, path: Path) -> dict[str, Any]:
        return self._scan_rows(
            path.stem[:31] or "CSV",
            0,
            self._iter_csv_rows(path),
        )

    def _scan_rows(
        self,
        name: str,
        index: int,
        rows: Iterator[tuple[CellValue, ...]],
    ) -> dict[str, Any]:
        non_empty_count = 0
        width = 0
        header_source: list[CellValue] = []
        for row_number, row in enumerate(rows, start=1):
            if row_number > self.settings.max_sheet_rows + 1:
                raise AppError(
                    "SHEET_TOO_LARGE",
                    f"单个工作表不能超过 {self.settings.max_sheet_rows} 行",
                )
            trimmed = self._trim_row(row)
            if len(trimmed) > self.settings.max_sheet_columns:
                raise AppError(
                    "SHEET_TOO_WIDE",
                    f"单个工作表不能超过 {self.settings.max_sheet_columns} 列",
                )
            if not trimmed:
                continue
            if not header_source:
                header_source = trimmed
            width = max(width, len(trimmed))
            non_empty_count += 1

        headers = self._normalize_headers(header_source, max(width, len(header_source)))
        return {
            "sheet_index": index,
            "name": name,
            "row_count": max(non_empty_count - 1, 0),
            "non_empty_row_count": non_empty_count,
            "column_count": len(headers),
            "headers": headers,
        }

    def _validate_container(self, path: Path, suffix: str) -> int:
        if suffix not in SUPPORTED_SUFFIXES:
            raise AppError("UNSUPPORTED_FILE", "仅支持 xlsx、xls 和 csv 文件", status_code=415)
        if not path.is_file():
            raise AppError("FILE_NOT_FOUND", "上传文件不存在", status_code=404)
        if suffix == ".xlsx":
            with path.open("rb") as source:
                if source.read(2) != _XLSX_SIGNATURE:
                    raise AppError("INVALID_FILE_TYPE", "文件内容与 .xlsx 扩展名不匹配")
            try:
                with zipfile.ZipFile(path) as archive:
                    entries = archive.infolist()
                    if len(entries) > self.settings.max_xlsx_entries:
                        raise AppError("XLSX_TOO_COMPLEX", "xlsx 压缩条目过多")
                    unpacked = sum(item.file_size for item in entries)
                    if unpacked > self.settings.max_xlsx_uncompressed_mb * 1024 * 1024:
                        raise AppError("XLSX_TOO_LARGE", "xlsx 解压后体积超过安全限制")
                    return unpacked
            except zipfile.BadZipFile as exc:
                raise AppError("INVALID_XLSX", "xlsx 文件已损坏或已加密") from exc
        elif suffix == ".xls":
            with path.open("rb") as source:
                if source.read(8) != _XLS_SIGNATURE:
                    raise AppError("INVALID_FILE_TYPE", "文件内容与 .xls 扩展名不匹配")
        return path.stat().st_size

    def _iter_xlsx_sheet(self, sheet) -> Iterator[tuple[CellValue, ...]]:
        if sheet.max_row > self.settings.max_sheet_rows + 1:
            raise AppError(
                "SHEET_TOO_LARGE",
                f"单个工作表不能超过 {self.settings.max_sheet_rows} 行",
            )
        if sheet.max_column > self.settings.max_sheet_columns:
            raise AppError(
                "SHEET_TOO_WIDE",
                f"单个工作表不能超过 {self.settings.max_sheet_columns} 列",
            )
        for row in sheet.iter_rows(values_only=True):
            yield tuple(row)

    def _iter_xls_sheet(self, workbook, sheet) -> Iterator[tuple[CellValue, ...]]:
        if sheet.nrows > self.settings.max_sheet_rows + 1:
            raise AppError(
                "SHEET_TOO_LARGE",
                f"单个工作表不能超过 {self.settings.max_sheet_rows} 行",
            )
        if sheet.ncols > self.settings.max_sheet_columns:
            raise AppError(
                "SHEET_TOO_WIDE",
                f"单个工作表不能超过 {self.settings.max_sheet_columns} 列",
            )
        for row_index in range(sheet.nrows):
            values: list[CellValue] = []
            for cell in sheet.row(row_index):
                if cell.ctype == XL_CELL_DATE:
                    values.append(xldate_as_datetime(cell.value, workbook.datemode))
                elif cell.ctype == XL_CELL_TEXT:
                    values.append(cell.value)
                else:
                    values.append(cell.value)
            yield tuple(values)

    def _iter_csv_rows(self, path: Path) -> Iterator[tuple[CellValue, ...]]:
        encoding, text = self._decode_csv(path)
        del encoding
        sample = text[:8192]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        except csv.Error:
            dialect = csv.excel
        stream = io.StringIO(text)
        try:
            for row_number, row in enumerate(csv.reader(stream, dialect), start=1):
                if row_number > self.settings.max_sheet_rows + 1:
                    raise AppError(
                        "SHEET_TOO_LARGE",
                        f"单个工作表不能超过 {self.settings.max_sheet_rows} 行",
                    )
                yield tuple(row)
        finally:
            stream.close()

    @staticmethod
    def _decode_csv(path: Path) -> tuple[str, str]:
        raw = path.read_bytes()
        if b"\x00" in raw[:4096]:
            raise AppError("INVALID_CSV", "CSV 文件包含无法识别的二进制内容")
        candidates: list[str] = []
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            candidates.append("utf-16")
        detected = from_bytes(raw).best()
        if detected is not None:
            candidates.append(str(detected.encoding))
        candidates = ["utf-8-sig", "gb18030", *candidates]
        for encoding in dict.fromkeys(candidates):
            try:
                return encoding, raw.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                continue
        raise AppError("INVALID_CSV_ENCODING", "无法识别 CSV 文件编码")

    @staticmethod
    def _trim_row(row: tuple[CellValue, ...] | list[CellValue]) -> list[CellValue]:
        values = list(row)
        while values and ExcelReader._is_blank(values[-1]):
            values.pop()
        return values

    @staticmethod
    def _is_blank(value: CellValue) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    @staticmethod
    def _normalize_row(
        row: tuple[CellValue, ...] | list[CellValue],
        width: int,
    ) -> list[CellValue]:
        values = list(row[:width])
        if len(values) < width:
            values.extend([None] * (width - len(values)))
        return values

    @staticmethod
    def _normalize_headers(
        header_source: list[CellValue],
        width: int,
    ) -> list[str]:
        headers: list[str] = []
        counts: dict[str, int] = {}
        for index in range(width):
            raw = header_source[index] if index < len(header_source) else None
            base = str(raw).strip() if raw is not None and str(raw).strip() else f"列{index + 1}"
            count = counts.get(base, 0) + 1
            counts[base] = count
            headers.append(base if count == 1 else f"{base}_{count}")
        return headers

    @staticmethod
    def _split_header(
        rows: Iterator[tuple[CellValue, ...]],
        has_header: bool,
    ) -> tuple[list[CellValue], Iterator[tuple[CellValue, ...]]]:
        if not has_header:
            return [], rows
        iterator = iter(rows)
        for row in iterator:
            if ExcelReader._trim_row(row):
                return list(row), iterator
        return [], iter(())

