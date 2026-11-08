from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SheetRef(BaseModel):
    file_id: str = Field(min_length=32, max_length=32)
    sheet_index: int = Field(ge=0)


class CleanupOptions(BaseModel):
    has_header: bool = True
    remove_empty_rows: bool = False
    remove_duplicates: bool = False


class SplitRequest(CleanupOptions):
    upload_id: str = Field(min_length=32, max_length=32)
    sheets: list[SheetRef] = Field(min_length=1)
    mode: Literal["by_sheet", "by_rows", "by_column"]
    rows_per_file: int | None = Field(default=None, ge=1, le=50_000)
    column_index: int | None = Field(default=None, ge=0, le=999)

    @model_validator(mode="after")
    def validate_mode_options(self) -> "SplitRequest":
        if self.mode == "by_rows" and self.rows_per_file is None:
            raise ValueError("按行数拆分时必须填写每份行数")
        if self.mode == "by_column" and self.column_index is None:
            raise ValueError("按列拆分时必须选择列")
        return self


class MergeRequest(CleanupOptions):
    upload_id: str = Field(min_length=32, max_length=32)
    sheets: list[SheetRef] = Field(min_length=1)
    header_strategy: Literal["strict", "by_name"] = "strict"

