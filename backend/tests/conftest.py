import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
import xlwt
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from app.config import Settings
from app.main import create_app


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        temp_root=tmp_path / "storage",
        log_dir=tmp_path / "logs",
        retention_minutes=30,
        cleanup_interval_seconds=3600,
    )


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(test_settings)) as test_client:
        yield test_client


def make_xlsx_bytes() -> bytes:
    workbook = Workbook()
    first = workbook.active
    first.title = "销售"
    first.append(["地区", "金额", "备注"])
    first.append(["华东", 100, "A"])
    first.append(["华南", 200, "B"])
    first.append(["华东", 300, "C"])
    second = workbook.create_sheet("库存")
    second.append(["商品", "数量"])
    second.append(["铅笔", 20])
    second.append(["本子", 10])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def make_xls_bytes() -> bytes:
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("旧表")
    rows = [
        ["姓名", "部门"],
        ["张三", "研发"],
        ["李四", "销售"],
    ]
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            sheet.write(row_index, column_index, value)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def make_csv_bytes(encoding: str = "utf-8-sig") -> bytes:
    content = "名称,数量\n苹果,3\n香蕉,5\n苹果,3\n"
    return content.encode(encoding)


def upload_files(client: TestClient, files: list[tuple[str, bytes, str]]) -> dict:
    response = client.post(
        "/api/v1/excel/inspect",
        files=[("files", item) for item in files],
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def sheet_refs(upload: dict) -> list[dict[str, int | str]]:
    return [
        {"file_id": file["file_id"], "sheet_index": sheet["sheet_index"]}
        for file in upload["files"]
        for sheet in file["sheets"]
    ]


def read_zip_files(content: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def read_xlsx_rows(content: bytes) -> dict[str, list[list[object]]]:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        return {
            sheet.title: [list(row) for row in sheet.iter_rows(values_only=True)]
            for sheet in workbook.worksheets
        }
    finally:
        workbook.close()


def add_xlsx_padding(content: bytes, size: int) -> bytes:
    output = io.BytesIO(content)
    with zipfile.ZipFile(output, "a") as archive:
        archive.writestr("padding.bin", b"0" * size, compress_type=zipfile.ZIP_STORED)
    return output.getvalue()

