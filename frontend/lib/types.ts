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

export type HistoryCapture = {
  saved: boolean;
  history_id?: string;
  notice?: string;
  evicted_count?: number;
};

export type ExcelResult = {
  result_id: string;
  filename: string;
  size: number;
  expires_at: string;
  download_url: string;
  output_count: number;
  row_count?: number;
  history?: HistoryCapture;
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

export type AuthUser = {
  id: number;
  username: string;
  role: "user" | "admin";
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  last_login_at: string | null;
};

export type LoginResult = {
  access_token: string;
  user: AuthUser;
};

export type HistoryItem = {
  id: string;
  tool: string;
  operation: string;
  result_filename: string;
  size_bytes: number;
  summary: Record<string, unknown>;
  status: "active" | "expired";
  completed_at: string;
  expires_at: string;
  expired_at: string | null;
  expire_reason: "timeout" | "quota_count" | "quota_size" | null;
  purge_after: string | null;
};

export type AuditLogItem = {
  id: number;
  request_id: string;
  event: string;
  outcome: "success" | "failure";
  actor_user_id: number | null;
  target_user_id: number | null;
  actor_username: string | null;
  target_username: string | null;
  ip: string;
  details: Record<string, unknown>;
  created_at: string;
};

export type PaginatedItems<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type RuntimeErrorItem = {
  timestamp?: string;
  level?: string;
  logger?: string;
  message?: string;
  event?: string;
  [key: string]: unknown;
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

