export type SheetInfo = {
  sheet_index: number;
  name: string;
  row_count: number;
  non_empty_row_count: number;
  column_count: number;
  headers: string[];
};

export type UploadedFile = {
  file_id: string;
  name: string;
  format: "xlsx" | "xls" | "csv";
  size: number;
  sheets: SheetInfo[];
};

export type ExcelUpload = {
  upload_id: string;
  expires_at: string;
  files: UploadedFile[];
};

export type ExcelResult = {
  result_id: string;
  filename: string;
  size: number;
  expires_at: string;
  download_url: string;
  output_count: number;
  row_count?: number;
};

export type SplitMode = "by_sheet" | "by_rows" | "by_column";
export type ExcelMode = SplitMode | "merge";
export type HeaderStrategy = "strict" | "by_name";

export type SheetRef = {
  file_id: string;
  sheet_index: number;
};

export type QrDecodedMac = {
  canonical: string;
  hyphenated: string;
  plain: string;
  cisco: string;
  multicast: boolean;
  locally_administered: boolean;
};

export type QrDecodedItem = {
  text: string;
  kind: "text" | "mac";
  mac?: QrDecodedMac;
};

export type ApiErrorBody = {
  success: false;
  data: null;
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
  request_id: string;
};

export type ApiSuccess<T> = {
  success: true;
  data: T;
  error: null;
  request_id: string;
};

