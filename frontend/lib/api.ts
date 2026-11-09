import type {
  ApiErrorBody,
  ApiSuccess,
  ExcelResult,
  ExcelUpload,
  HeaderStrategy,
  QrDecodedItem,
  SheetRef,
  SplitMode,
} from "@/lib/types";
import { demoMode } from "@/lib/config";
import {
  decodeDemoQrCode,
  generateDemoQrCode,
  inspectDemoSpreadsheets,
  mergeDemoSpreadsheets,
  splitDemoSpreadsheets,
} from "@/lib/demo-api";
import { ApiError } from "@/lib/errors";

export { demoMode } from "@/lib/config";
export { ApiError } from "@/lib/errors";

async function readJson<T>(response: Response): Promise<T> {
  let body: ApiSuccess<T> | ApiErrorBody;
  try {
    body = (await response.json()) as ApiSuccess<T> | ApiErrorBody;
  } catch {
    throw new ApiError("服务器返回了无法识别的内容", "INVALID_RESPONSE", response.status);
  }
  if (!response.ok || !body.success) {
    const error = body.success ? null : body.error;
    throw new ApiError(
      error?.message ?? "请求失败，请稍后重试",
      error?.code ?? "REQUEST_FAILED",
      response.status,
      error?.details,
    );
  }
  return body.data;
}

async function readError(response: Response): Promise<never> {
  try {
    const body = (await response.json()) as ApiErrorBody;
    throw new ApiError(
      body.error?.message ?? "请求失败，请稍后重试",
      body.error?.code,
      response.status,
      body.error?.details,
    );
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError("请求失败，请稍后重试", "REQUEST_FAILED", response.status);
  }
}

export async function inspectSpreadsheets(files: File[]): Promise<ExcelUpload> {
  if (demoMode) {
    return inspectDemoSpreadsheets(files);
  }
  const form = new FormData();
  for (const file of files) {
    form.append("files", file, file.name);
  }
  const response = await fetch("/api/v1/excel/inspect", {
    method: "POST",
    body: form,
  });
  return readJson<ExcelUpload>(response);
}

type SplitPayload = {
  upload_id: string;
  sheets: SheetRef[];
  mode: SplitMode;
  has_header: boolean;
  remove_empty_rows: boolean;
  remove_duplicates: boolean;
  rows_per_file?: number;
  column_index?: number;
};

export async function splitSpreadsheets(payload: SplitPayload): Promise<ExcelResult> {
  if (demoMode) {
    return splitDemoSpreadsheets(payload);
  }
  const response = await fetch("/api/v1/excel/split", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<ExcelResult>(response);
}

type MergePayload = {
  upload_id: string;
  sheets: SheetRef[];
  has_header: boolean;
  remove_empty_rows: boolean;
  remove_duplicates: boolean;
  header_strategy: HeaderStrategy;
};

export async function mergeSpreadsheets(payload: MergePayload): Promise<ExcelResult> {
  if (demoMode) {
    return mergeDemoSpreadsheets(payload);
  }
  const response = await fetch("/api/v1/excel/merge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<ExcelResult>(response);
}

function saveDownload(url: string, filename: string) {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
}

export async function downloadExcelResult(result: ExcelResult): Promise<void> {
  if (result.download_url.startsWith("blob:")) {
    saveDownload(result.download_url, result.filename);
    return;
  }

  const response = await fetch(result.download_url);
  if (!response.ok) {
    return readError(response);
  }

  const objectUrl = URL.createObjectURL(await response.blob());
  try {
    saveDownload(objectUrl, result.filename);
  } finally {
    setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
  }
}

export async function generateQrCode(
  content: string,
  size: number,
  mode: "text" | "mac",
): Promise<{ blob: Blob; normalizedMac: string | null }> {
  if (demoMode) {
    return generateDemoQrCode(content, size, mode);
  }
  const response = await fetch("/api/v1/qrcode/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, size, mode }),
  });
  if (!response.ok) {
    return readError(response);
  }
  return {
    blob: await response.blob(),
    normalizedMac: response.headers.get("X-MAC-Normalized"),
  };
}

export async function decodeQrCode(
  file: File,
): Promise<{ items: QrDecodedItem[]; count: number }> {
  if (demoMode) {
    return decodeDemoQrCode();
  }
  const form = new FormData();
  form.append("file", file, file.name);
  const response = await fetch("/api/v1/qrcode/decode", {
    method: "POST",
    body: form,
  });
  return readJson<{ items: QrDecodedItem[]; count: number }>(response);
}

