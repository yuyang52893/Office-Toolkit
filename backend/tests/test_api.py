from datetime import UTC, datetime, timedelta

from conftest import (
    add_xlsx_padding,
    authenticated_headers,
    history_count,
    make_csv_bytes,
    make_xls_bytes,
    make_xlsx_bytes,
    read_xlsx_rows,
    read_zip_files,
    sheet_refs,
    upload_files,
)
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories.temp_storage import TempStorage
from app.services.excel_service import ExcelService


def test_health_and_request_id(client: TestClient):
    response = client.get("/api/v1/health", headers={"X-Request-ID": "request123"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request123"
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["error"] is None


def test_unknown_routes_and_methods_use_unified_error_contract(client: TestClient):
    missing = client.get("/api/v1/does-not-exist")
    assert missing.status_code == 404
    assert missing.json() == {
        "success": False,
        "data": None,
        "error": {
            "code": "NOT_FOUND",
            "message": "请求的接口不存在",
            "details": None,
        },
        "request_id": missing.headers["X-Request-ID"],
    }

    wrong_method = client.post("/api/v1/health")
    assert wrong_method.status_code == 405
    assert wrong_method.json()["success"] is False
    assert wrong_method.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_inspect_xlsx_xls_and_csv(client: TestClient):
    upload = upload_files(
        client,
        [
            (
                "销售.xlsx",
                make_xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            ("旧表.xls", make_xls_bytes(), "application/vnd.ms-excel"),
            ("清单.csv", make_csv_bytes("gb18030"), "text/csv"),
        ],
    )
    assert upload["upload_id"]
    assert len(upload["files"]) == 3
    assert upload["files"][0]["format"] == "xlsx"
    assert [sheet["name"] for sheet in upload["files"][0]["sheets"]] == ["销售", "库存"]
    assert upload["files"][0]["sheets"][0]["headers"] == ["地区", "金额", "备注"]
    assert upload["files"][0]["sheets"][0]["row_count"] == 3
    assert upload["files"][1]["format"] == "xls"
    assert upload["files"][1]["sheets"][0]["headers"] == ["姓名", "部门"]
    assert upload["files"][2]["format"] == "csv"
    assert upload["files"][2]["sheets"][0]["headers"] == ["名称", "数量"]


def test_inspect_rejects_mime_type_that_contradicts_extension(client: TestClient):
    response = client.post(
        "/api/v1/excel/inspect",
        files=[("files", ("清单.csv", make_csv_bytes(), "image/png"))],
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "FILE_TYPE_MISMATCH"


def test_rejects_task_when_combined_uncompressed_size_exceeds_budget(test_settings):
    settings = Settings(
        app_env="test",
        temp_root=test_settings.temp_root / "uncompressed-budget",
        max_task_uncompressed_mb=1,
    )
    padded = add_xlsx_padding(make_xlsx_bytes(), 600_000)
    with TestClient(create_app(settings)) as custom_client:
        response = custom_client.post(
            "/api/v1/excel/inspect",
            files=[
                ("files", ("第一份.xlsx", padded, "application/octet-stream")),
                ("files", ("第二份.xlsx", padded, "application/octet-stream")),
            ],
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "TASK_UNCOMPRESSED_TOO_LARGE"


def test_rejects_split_when_selected_sheets_exceed_cell_budget(test_settings):
    settings = Settings(
        app_env="test",
        temp_root=test_settings.temp_root / "cell-budget",
        max_task_cells=10,
    )
    with TestClient(create_app(settings)) as custom_client:
        upload = upload_files(
            custom_client,
            [("销售.xlsx", make_xlsx_bytes(), "application/octet-stream")],
        )
        response = custom_client.post(
            "/api/v1/excel/split",
            json={
                "upload_id": upload["upload_id"],
                "mode": "by_sheet",
                "sheets": [sheet_refs(upload)[0]],
                "has_header": True,
            },
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "TASK_TOO_COMPLEX"


def test_safe_component_prefixes_windows_reserved_names():
    assert ExcelService._safe_component("CON", "数据") == "_CON"
    assert ExcelService._safe_component("nul", "数据") == "_nul"


def test_split_by_sheet_creates_single_sheet_files(client: TestClient):
    upload = upload_files(client, [("销售.xlsx", make_xlsx_bytes(), "application/octet-stream")])
    response = client.post(
        "/api/v1/excel/split",
        json={
            "upload_id": upload["upload_id"],
            "mode": "by_sheet",
            "sheets": sheet_refs(upload),
            "has_header": True,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["output_count"] == 2

    download = client.get(result["download_url"])
    assert download.status_code == 200
    files = read_zip_files(download.content)
    assert len(files) == 2
    for content in files.values():
        assert len(read_xlsx_rows(content)) == 1


def test_split_by_rows_repeats_header_and_keeps_csv_format(client: TestClient):
    xlsx_upload = upload_files(
        client,
        [("销售.xlsx", make_xlsx_bytes(), "application/octet-stream")],
    )
    sales_sheet = sheet_refs(xlsx_upload)[0]
    response = client.post(
        "/api/v1/excel/split",
        json={
            "upload_id": xlsx_upload["upload_id"],
            "mode": "by_rows",
            "sheets": [sales_sheet],
            "rows_per_file": 2,
            "has_header": True,
        },
    )
    assert response.status_code == 200, response.text
    files = read_zip_files(client.get(response.json()["data"]["download_url"]).content)
    assert len(files) == 2
    chunks = sorted(read_xlsx_rows(content)["数据"] for content in files.values())
    assert chunks[0][0] == ["地区", "金额", "备注"]
    assert chunks[1][0] == ["地区", "金额", "备注"]
    assert sum(len(chunk) - 1 for chunk in chunks) == 3

    csv_upload = upload_files(
        client,
        [("清单.csv", make_csv_bytes("gb18030"), "text/csv")],
    )
    response = client.post(
        "/api/v1/excel/split",
        json={
            "upload_id": csv_upload["upload_id"],
            "mode": "by_rows",
            "sheets": sheet_refs(csv_upload),
            "rows_per_file": 2,
            "has_header": True,
        },
    )
    files = read_zip_files(client.get(response.json()["data"]["download_url"]).content)
    assert all(name.endswith(".csv") for name in files)
    assert all(content.startswith(b"\xef\xbb\xbf") for content in files.values())


def test_cleanup_options_remove_duplicate_and_empty_rows(client: TestClient):
    csv_content = "名称,数量\n苹果,3\n\n苹果,3\n香蕉,5\n"
    upload = upload_files(
        client,
        [("清单.csv", csv_content.encode("utf-8"), "text/csv")],
    )
    response = client.post(
        "/api/v1/excel/split",
        json={
            "upload_id": upload["upload_id"],
            "mode": "by_rows",
            "sheets": sheet_refs(upload),
            "rows_per_file": 10,
            "has_header": True,
            "remove_empty_rows": True,
            "remove_duplicates": True,
        },
    )
    files = read_zip_files(client.get(response.json()["data"]["download_url"]).content)
    csv_text = next(iter(files.values())).decode("utf-8-sig")
    assert csv_text.splitlines() == ["名称,数量", "苹果,3", "香蕉,5"]


def test_history_list_uses_unified_response_contract(client: TestClient):
    response = client.get(
        "/api/v1/history",
        headers=authenticated_headers(client),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {"items": []}
    assert body["error"] is None


def test_split_without_header_uses_all_rows_as_data(client: TestClient):
    upload = upload_files(
        client,
        [("无表头.csv", b"A,100\nB,200\n", "text/csv")],
    )
    response = client.post(
        "/api/v1/excel/split",
        json={
            "upload_id": upload["upload_id"],
            "mode": "by_sheet",
            "sheets": sheet_refs(upload),
            "has_header": False,
        },
    )
    files = read_zip_files(client.get(response.json()["data"]["download_url"]).content)
    csv_text = next(iter(files.values())).decode("utf-8-sig")
    assert csv_text.splitlines() == ["A,100", "B,200"]


def test_split_by_column_groups_values(client: TestClient):
    upload = upload_files(client, [("销售.xlsx", make_xlsx_bytes(), "application/octet-stream")])
    response = client.post(
        "/api/v1/excel/split",
        json={
            "upload_id": upload["upload_id"],
            "mode": "by_column",
            "sheets": [sheet_refs(upload)[0]],
            "column_index": 0,
            "has_header": True,
        },
    )
    assert response.status_code == 200, response.text
    files = read_zip_files(client.get(response.json()["data"]["download_url"]).content)
    assert len(files) == 2
    assert any("华东" in name for name in files)


def test_merge_strict_and_by_name(client: TestClient):
    upload = upload_files(
        client,
        [
            ("销售.xlsx", make_xlsx_bytes(), "application/octet-stream"),
            ("旧表.xls", make_xls_bytes(), "application/vnd.ms-excel"),
        ],
    )
    references = sheet_refs(upload)
    mismatch = client.post(
        "/api/v1/excel/merge",
        json={
            "upload_id": upload["upload_id"],
            "sheets": references[:2],
            "has_header": True,
            "header_strategy": "strict",
        },
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["error"]["code"] == "HEADER_MISMATCH"

    merged = client.post(
        "/api/v1/excel/merge",
        json={
            "upload_id": upload["upload_id"],
            "sheets": references[:2],
            "has_header": True,
            "header_strategy": "by_name",
        },
    )
    assert merged.status_code == 200, merged.text
    assert merged.json()["data"]["output_count"] == 1
    assert merged.json()["data"]["row_count"] == 5
    download = client.get(merged.json()["data"]["download_url"])
    rows = read_xlsx_rows(download.content)["合并结果"]
    assert rows[0] == ["地区", "金额", "备注", "商品", "数量"]
    assert rows[1][:3] == ["华东", 100, "A"]
    assert rows[4][3:] == ["铅笔", 20]


def test_invalid_and_oversized_files_return_structured_errors(client: TestClient):
    empty = client.post(
        "/api/v1/excel/inspect",
        files={"files": ("empty.csv", b"", "text/csv")},
    )
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "EMPTY_FILE"

    unsupported = client.post(
        "/api/v1/excel/inspect",
        files={"files": ("notes.txt", b"hello", "text/plain")},
    )
    assert unsupported.status_code == 415
    assert unsupported.json()["success"] is False
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_FILE"

    fake_xlsx = client.post(
        "/api/v1/excel/inspect",
        files={"files": ("fake.xlsx", b"not a zip", "application/octet-stream")},
    )
    assert fake_xlsx.status_code == 400
    assert fake_xlsx.json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_duplicate_sheet_selection_is_rejected(client: TestClient):
    upload = upload_files(client, [("销售.xlsx", make_xlsx_bytes(), "application/octet-stream")])
    sheet = sheet_refs(upload)[0]
    response = client.post(
        "/api/v1/excel/split",
        json={
            "upload_id": upload["upload_id"],
            "mode": "by_sheet",
            "sheets": [sheet, sheet],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DUPLICATE_SHEET"


def test_expired_upload_is_removed(client: TestClient, test_settings):
    upload = upload_files(client, [("清单.csv", make_csv_bytes(), "text/csv")])
    storage = TempStorage(test_settings)
    removed = storage.cleanup_expired(now=datetime.now(UTC) + timedelta(hours=1))
    assert removed >= 1
    response = client.post(
        "/api/v1/excel/split",
        json={
            "upload_id": upload["upload_id"],
            "mode": "by_sheet",
            "sheets": sheet_refs(upload),
        },
    )
    assert response.status_code in {404, 410}


def test_expired_result_cannot_be_downloaded(client: TestClient, test_settings):
    upload = upload_files(client, [("清单.csv", make_csv_bytes(), "text/csv")])
    generated = client.post(
        "/api/v1/excel/split",
        json={
            "upload_id": upload["upload_id"],
            "mode": "by_sheet",
            "sheets": sheet_refs(upload),
        },
    )
    download_url = generated.json()["data"]["download_url"]

    TempStorage(test_settings).cleanup_expired(now=datetime.now(UTC) + timedelta(hours=1))
    response = client.get(download_url)
    assert response.status_code in {404, 410}
    assert response.json()["success"] is False


def test_logged_in_excel_result_is_added_to_history(client: TestClient):
    upload = upload_files(client, [("销售.xlsx", make_xlsx_bytes(), "application/octet-stream")])
    headers = authenticated_headers(client)
    response = client.post(
        "/api/v1/excel/split",
        headers=headers,
        json={
            "upload_id": upload["upload_id"],
            "mode": "by_sheet",
            "sheets": sheet_refs(upload),
            "has_header": True,
        },
    )
    assert response.status_code == 200, response.text
    history = response.json()["data"]["history"]
    assert history["saved"] is True
    assert history["history_id"]
    assert history_count(client) == 1


def test_logged_in_excel_merge_result_is_added_to_history(client: TestClient):
    upload = upload_files(
        client,
        [("销售.xlsx", make_xlsx_bytes(), "application/octet-stream")],
    )
    headers = authenticated_headers(client)
    response = client.post(
        "/api/v1/excel/merge",
        headers=headers,
        json={
            "upload_id": upload["upload_id"],
            "sheets": sheet_refs(upload),
            "has_header": True,
            "header_strategy": "by_name",
        },
    )

    assert response.status_code == 200, response.text
    history = response.json()["data"]["history"]
    assert history["saved"] is True
    assert history["history_id"]
    assert history_count(client) == 1


def test_anonymous_excel_result_is_not_added_to_history(client: TestClient):
    upload = upload_files(client, [("销售.xlsx", make_xlsx_bytes(), "application/octet-stream")])
    response = client.post(
        "/api/v1/excel/split",
        json={
            "upload_id": upload["upload_id"],
            "mode": "by_sheet",
            "sheets": sheet_refs(upload),
            "has_header": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["data"].get("history") is None
    assert history_count(client) == 0


def test_history_save_failure_does_not_break_excel_download(
    client: TestClient,
    monkeypatch,
):
    upload = upload_files(client, [("销售.xlsx", make_xlsx_bytes(), "application/octet-stream")])
    headers = authenticated_headers(client)

    def fail_history_write(**_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(client.app.state.history_storage, "write", fail_history_write)
    response = client.post(
        "/api/v1/excel/split",
        headers=headers,
        json={
            "upload_id": upload["upload_id"],
            "mode": "by_rows",
            "sheets": sheet_refs(upload)[:1],
            "rows_per_file": 1,
            "has_header": True,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["download_url"]
    assert response.json()["data"]["history"]["saved"] is False
    assert "仍可下载" in response.json()["data"]["history"]["notice"]

