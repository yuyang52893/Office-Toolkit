import QRCode from "qrcode";

import { ApiError } from "@/lib/errors";
import { normalizeMac } from "@/lib/mac";
import type {
  ExcelResult,
  ExcelUpload,
  HeaderStrategy,
  QrDecodedItem,
  SheetRef,
  SplitMode,
  UploadedFile,
} from "@/lib/types";

const uploadStore = new Map<string, ExcelUpload>();

function wait(milliseconds: number) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function randomId(): string {
  return crypto.randomUUID().replaceAll("-", "");
}

function expiresAt(): string {
  return new Date(Date.now() + 30 * 60 * 1000).toISOString();
}

function numericSeed(value: string): number {
  return Array.from(value).reduce((total, character) => total + character.charCodeAt(0), 0);
}

async function inspectCsv(file: File): Promise<UploadedFile> {
  const text = await file.text();
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const delimiter = lines[0]?.includes("\t") ? "\t" : lines[0]?.includes(";") ? ";" : ",";
  const headers = (lines[0] ?? "地区,客户,金额,日期")
    .split(delimiter)
    .map((item) => item.replaceAll('"', "").trim())
    .filter(Boolean);
  const rowCount = Math.max(lines.length - 1, 18);
  return {
    file_id: randomId(),
    name: file.name,
    format: "csv",
    size: file.size,
    sheets: [
      {
        sheet_index: 0,
        name: file.name.replace(/\.csv$/i, ""),
        row_count: rowCount,
        non_empty_row_count: rowCount + 1,
        column_count: Math.max(headers.length, 2),
        headers: headers.length > 1 ? headers : ["地区", "客户", "金额", "日期"],
      },
    ],
  };
}

function inspectWorkbook(file: File): UploadedFile {
  const seed = numericSeed(file.name);
  const excel = file.name.toLowerCase().endsWith(".xlsx");
  const sheets = [
    {
      sheet_index: 0,
      name: "销售明细",
      row_count: 1200 + (seed % 860),
      non_empty_row_count: 1201 + (seed % 860),
      column_count: 5,
      headers: ["地区", "客户名称", "订单金额", "订单日期", "状态"],
    },
  ];
  if (excel) {
    sheets.push(
      {
        sheet_index: 1,
        name: "退款记录",
        row_count: 36 + (seed % 70),
        non_empty_row_count: 37 + (seed % 70),
        column_count: 4,
        headers: ["订单号", "退款金额", "原因", "处理日期"],
      },
      {
        sheet_index: 2,
        name: "客户汇总",
        row_count: 88 + (seed % 40),
        non_empty_row_count: 89 + (seed % 40),
        column_count: 4,
        headers: ["客户名称", "订单数", "总金额", "最近下单"],
      },
    );
  }
  return {
    file_id: randomId(),
    name: file.name,
    format: excel ? "xlsx" : "xls",
    size: file.size,
    sheets,
  };
}

export async function inspectDemoSpreadsheets(files: File[]): Promise<ExcelUpload> {
  await wait(700);
  const inspected = await Promise.all(
    files.map((file) => (file.name.toLowerCase().endsWith(".csv") ? inspectCsv(file) : inspectWorkbook(file))),
  );
  const upload: ExcelUpload = {
    upload_id: randomId(),
    expires_at: expiresAt(),
    files: inspected,
  };
  uploadStore.set(upload.upload_id, upload);
  return upload;
}

function selectedSheetRows(upload: ExcelUpload, sheets: SheetRef[]): number {
  return sheets.reduce((total, reference) => {
    const sheet = upload.files
      .find((file) => file.file_id === reference.file_id)
      ?.sheets.find((item) => item.sheet_index === reference.sheet_index);
    return total + (sheet?.row_count ?? 0);
  }, 0);
}

function mockDownloadResult(filename: string, outputCount: number, rowCount?: number): ExcelResult {
  const text = [
    "轻办公工具箱 - 演示结果",
    "",
    `模拟文件名：${filename}`,
    `模拟输出数量：${outputCount}`,
    ...(rowCount === undefined ? [] : [`模拟合并行数：${rowCount}`]),
    "",
    "当前为纯前端演示模式，没有生成真实 Excel/CSV 文件。",
    "接入真实后端后，这里会下载实际处理结果。",
  ].join("\r\n");
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const timestamp = new Date().toISOString().slice(0, 19).replaceAll(":", "").replace("T", "_");
  return {
    result_id: randomId(),
    filename: `演示结果说明_${timestamp}.txt`,
    size: blob.size,
    expires_at: expiresAt(),
    download_url: URL.createObjectURL(blob),
    output_count: outputCount,
    ...(rowCount === undefined ? {} : { row_count: rowCount }),
  };
}

export async function splitDemoSpreadsheets(payload: {
  upload_id: string;
  sheets: SheetRef[];
  mode: SplitMode;
  rows_per_file?: number;
}): Promise<ExcelResult> {
  await wait(1100);
  const upload = uploadStore.get(payload.upload_id);
  if (!upload) {
    throw new ApiError("演示数据已失效，请重新上传文件");
  }
  let outputCount = payload.sheets.length;
  if (payload.mode === "by_rows") {
    outputCount = payload.sheets.reduce((total, reference) => {
      const rowCount = selectedSheetRows(upload, [reference]);
      return total + Math.max(1, Math.ceil(rowCount / (payload.rows_per_file ?? 1)));
    }, 0);
  }
  if (payload.mode === "by_column") {
    outputCount = Math.max(payload.sheets.length * 3, 3);
  }
  const label =
    payload.mode === "by_sheet" ? "工作表拆分" : payload.mode === "by_rows" ? "按行拆分" : "按列拆分";
  return mockDownloadResult(`演示_${label}.zip`, outputCount);
}

export async function mergeDemoSpreadsheets(payload: {
  upload_id: string;
  sheets: SheetRef[];
  header_strategy: HeaderStrategy;
}): Promise<ExcelResult> {
  await wait(1200);
  const upload = uploadStore.get(payload.upload_id);
  if (!upload) {
    throw new ApiError("演示数据已失效，请重新上传文件");
  }
  if (payload.header_strategy === "strict" && payload.sheets.length > 1) {
    const headers = payload.sheets.map((reference) =>
      upload.files
        .find((file) => file.file_id === reference.file_id)
        ?.sheets.find((sheet) => sheet.sheet_index === reference.sheet_index)
        ?.headers.join("|"),
    );
    if (new Set(headers).size > 1) {
      throw new ApiError("演示提示：所选工作表表头不一致，请切换到“按列名对齐”");
    }
  }
  return mockDownloadResult("演示_合并结果.xlsx", 1, selectedSheetRows(upload, payload.sheets));
}

async function qrBlob(content: string, size: number): Promise<Blob> {
  const dataUrl = await QRCode.toDataURL(content, {
    width: size,
    margin: 4,
    errorCorrectionLevel: "M",
    color: { dark: "#000000", light: "#ffffff" },
  });
  const separator = dataUrl.indexOf(",");
  const metadata = dataUrl.slice(0, separator);
  const encoded = dataUrl.slice(separator + 1);
  const mimeType = metadata.match(/^data:([^;]+)/)?.[1] ?? "application/octet-stream";
  const binary = atob(encoded);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new Blob([bytes], { type: mimeType });
}

export async function generateDemoQrCode(
  content: string,
  size: number,
  mode: "text" | "mac",
): Promise<{ blob: Blob; normalizedMac: string | null }> {
  await wait(350);
  if (mode === "mac") {
    const mac = normalizeMac(content);
    if (!mac) {
      throw new ApiError("MAC 地址应为 12 位十六进制字符，例如 AA:BB:CC:DD:EE:FF");
    }
    return { blob: await qrBlob(mac.canonical, size), normalizedMac: mac.canonical };
  }
  if (!content.trim()) {
    throw new ApiError("请输入二维码内容");
  }
  return { blob: await qrBlob(content, size), normalizedMac: null };
}

export async function decodeDemoQrCode(): Promise<{
  items: QrDecodedItem[];
  count: number;
}> {
  await wait(900);
  const items: QrDecodedItem[] = [
    { text: "轻办公工具箱演示内容", kind: "text" },
    { text: "https://example.com/demo", kind: "text" },
    {
      text: "AA:BB:CC:DD:EE:FF",
      kind: "mac",
      mac: normalizeMac("AA:BB:CC:DD:EE:FF") ?? undefined,
    },
  ];
  return { items, count: items.length };
}

