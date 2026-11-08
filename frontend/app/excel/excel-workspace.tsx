"use client";

import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  Columns3,
  Download,
  FileSpreadsheet,
  Files,
  Layers3,
  Loader2,
  LockKeyhole,
  Merge,
  RefreshCw,
  Rows3,
  Table2,
  UploadCloud,
  X,
} from "lucide-react";
import type { ComponentType, DragEvent, KeyboardEvent } from "react";
import { useMemo, useRef, useState } from "react";

import { StatusBanner } from "@/components/status-banner";
import { Toggle } from "@/components/toggle";
import { BackToTools } from "@/components/back-to-tools";
import {
  getErrorMessage,
  formatBytes,
  formatExpiry,
  generatedHeaders,
} from "@/lib/format";
import {
  demoMode,
  inspectSpreadsheets,
  mergeSpreadsheets,
  splitSpreadsheets,
} from "@/lib/api";
import type {
  ExcelMode,
  ExcelResult,
  ExcelUpload,
  HeaderStrategy,
  SheetInfo,
  SheetRef,
} from "@/lib/types";

type Phase = "idle" | "inspecting" | "processing";
type SelectionMap = Record<string, number[]>;

type Operation = {
  id: ExcelMode;
  label: string;
  description: string;
  icon: ComponentType<{ size?: number; className?: string }>;
};

const operations: Operation[] = [
  {
    id: "by_sheet",
    label: "按工作表",
    description: "每个 Sheet 输出一个单表文件",
    icon: Layers3,
  },
  {
    id: "by_rows",
    label: "按行数",
    description: "按指定数据行数切分文件",
    icon: Rows3,
  },
  {
    id: "by_column",
    label: "按列值",
    description: "同一列值归入一个文件",
    icon: Columns3,
  },
  {
    id: "merge",
    label: "合并数据",
    description: "多个工作表按行追加合并",
    icon: Merge,
  },
];

const acceptedExtensions = [".xlsx", ".xls", ".csv"];
const maxFiles = 20;
const maxFileBytes = 50 * 1024 * 1024;
const maxTaskBytes = 100 * 1024 * 1024;

export function ExcelWorkspace({ initialMode = "by_sheet" }: { initialMode?: ExcelMode }) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [upload, setUpload] = useState<ExcelUpload | null>(null);
  const [selected, setSelected] = useState<SelectionMap>({});
  const [mode, setMode] = useState<ExcelMode>(initialMode);
  const [hasHeader, setHasHeader] = useState(true);
  const [removeEmptyRows, setRemoveEmptyRows] = useState(false);
  const [removeDuplicates, setRemoveDuplicates] = useState(false);
  const [rowsPerFile, setRowsPerFile] = useState("1000");
  const [columnIndex, setColumnIndex] = useState("0");
  const [headerStrategy, setHeaderStrategy] = useState<HeaderStrategy>("strict");
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<ExcelResult | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const busy = phase !== "idle";
  const selectedRefs = useMemo<SheetRef[]>(() => {
    if (!upload) {
      return [];
    }
    return upload.files.flatMap((file) =>
      [...(selected[file.file_id] ?? [])]
        .sort((a, b) => a - b)
        .map((sheetIndex) => ({
          file_id: file.file_id,
          sheet_index: sheetIndex,
        })),
    );
  }, [selected, upload]);

  const allSheets = useMemo(() => {
    if (!upload) {
      return [];
    }
    return upload.files.flatMap((file) =>
      file.sheets.map((sheet) => ({
        fileId: file.file_id,
        sheetIndex: sheet.sheet_index,
      })),
    );
  }, [upload]);

  const firstSelectedSheet = useMemo<SheetInfo | null>(() => {
    if (!upload || selectedRefs.length === 0) {
      return null;
    }
    const first = selectedRefs[0];
    return (
      upload.files
        .find((file) => file.file_id === first.file_id)
        ?.sheets.find((sheet) => sheet.sheet_index === first.sheet_index) ?? null
    );
  }, [selectedRefs, upload]);

  const columnOptions = useMemo(() => {
    if (!firstSelectedSheet) {
      return [];
    }
    return hasHeader
      ? firstSelectedSheet.headers
      : generatedHeaders(firstSelectedSheet.column_count);
  }, [firstSelectedSheet, hasHeader]);
  const effectiveColumnIndex =
    Number(columnIndex) < columnOptions.length ? columnIndex : "0";

  function resetUploadState() {
    setUpload(null);
    setSelected({});
    setResult(null);
    setError("");
  }

  function addFiles(incoming: File[]) {
    const candidates = incoming.filter((file) =>
      acceptedExtensions.some((extension) => file.name.toLowerCase().endsWith(extension)),
    );
    if (candidates.length !== incoming.length) {
      setError("仅支持 .xlsx、.xls 和 .csv 文件");
      return;
    }
    const existingKeys = new Set(files.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
    const unique = candidates.filter(
      (file) => !existingKeys.has(`${file.name}:${file.size}:${file.lastModified}`),
    );
    const nextFiles = [...files, ...unique];
    if (nextFiles.length > maxFiles) {
      setError(`一次最多上传 ${maxFiles} 个文件`);
      return;
    }
    if (nextFiles.some((file) => file.size > maxFileBytes)) {
      setError("单个文件不能超过 50MB");
      return;
    }
    if (nextFiles.reduce((total, file) => total + file.size, 0) > maxTaskBytes) {
      setError("本次上传的总文件不能超过 100MB");
      return;
    }
    setFiles(nextFiles);
    resetUploadState();
  }

  function handleFileInput(event: React.ChangeEvent<HTMLInputElement>) {
    addFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    if (!busy) {
      addFiles(Array.from(event.dataTransfer.files));
    }
  }

  function handleDropzoneKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fileInputRef.current?.click();
    }
  }

  function removeFile(index: number) {
    setFiles(files.filter((_, fileIndex) => fileIndex !== index));
    resetUploadState();
  }

  async function inspectFiles() {
    if (files.length === 0) {
      setError("请先选择需要处理的文件");
      return;
    }
    setPhase("inspecting");
    setError("");
    setResult(null);
    try {
      const data = await inspectSpreadsheets(files);
      const nextSelection: SelectionMap = {};
      for (const file of data.files) {
        nextSelection[file.file_id] = file.sheets.map((sheet) => sheet.sheet_index);
      }
      setUpload(data);
      setSelected(nextSelection);
    } catch (inspectError) {
      setUpload(null);
      setSelected({});
      setError(getErrorMessage(inspectError));
    } finally {
      setPhase("idle");
    }
  }

  function toggleSheet(fileId: string, sheetIndex: number) {
    setResult(null);
    setSelected((current) => {
      const currentSheets = current[fileId] ?? [];
      const exists = currentSheets.includes(sheetIndex);
      return {
        ...current,
        [fileId]: exists
          ? currentSheets.filter((index) => index !== sheetIndex)
          : [...currentSheets, sheetIndex],
      };
    });
  }

  function toggleAllSheets() {
    if (!upload) {
      return;
    }
    if (selectedRefs.length === allSheets.length) {
      setSelected({});
    } else {
      const next: SelectionMap = {};
      for (const file of upload.files) {
        next[file.file_id] = file.sheets.map((sheet) => sheet.sheet_index);
      }
      setSelected(next);
    }
    setResult(null);
  }

  async function runTool() {
    if (!upload) {
      setError("请先解析上传文件");
      return;
    }
    if (selectedRefs.length === 0) {
      setError("请至少选择一个工作表");
      return;
    }

    setError("");
    setResult(null);
    const common = {
      upload_id: upload.upload_id,
      sheets: selectedRefs,
      has_header: hasHeader,
      remove_empty_rows: removeEmptyRows,
      remove_duplicates: removeDuplicates,
    };

    try {
      if (mode === "merge") {
        setPhase("processing");
        const data = await mergeSpreadsheets({
          ...common,
          header_strategy: headerStrategy,
        });
        setResult(data);
        return;
      }

      const numericRows = Number(rowsPerFile);
      if (
        mode === "by_rows" &&
        (!Number.isInteger(numericRows) || numericRows < 1 || numericRows > 50_000)
      ) {
        setError("每份数据行数必须是 1 到 50000 之间的整数");
        return;
      }
      setPhase("processing");
      const data = await splitSpreadsheets({
        ...common,
        mode,
        ...(mode === "by_rows" ? { rows_per_file: numericRows } : {}),
        ...(mode === "by_column" ? { column_index: Number(effectiveColumnIndex) } : {}),
      });
      setResult(data);
    } catch (runError) {
      setError(getErrorMessage(runError));
    } finally {
      setPhase("idle");
    }
  }

  function resetAll() {
    setFiles([]);
    setUpload(null);
    setSelected({});
    setResult(null);
    setError("");
    setPhase("idle");
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="mb-5">
        <BackToTools />
      </div>
      <section className="fade-up mb-8">
        <div className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-blue-600">
          <FileSpreadsheet size={15} />
          Spreadsheet Workspace
        </div>
        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
          <div>
            <h1 className="text-3xl font-black tracking-[-0.035em] text-slate-950 sm:text-4xl">
              Excel / CSV 工作台
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">
              批量上传表格，按工作表、行数或列值拆分，也可以把多个表的数据合并到一起。
              所有处理结果均为值数据。
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            {["xlsx", "xls", "csv"].map((format) => (
              <span
                key={format}
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 font-bold uppercase text-slate-500"
              >
                {format}
              </span>
            ))}
            <span className="rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1.5 font-bold text-emerald-700">
              批量处理
            </span>
          </div>
        </div>
      </section>

      <div className="mb-7 grid grid-cols-3 gap-3">
        {[
          ["01", "上传并解析", "读取工作表信息"],
          ["02", "选择处理规则", "拆分或合并"],
          ["03", "下载结果", "结果保留 30 分钟"],
        ].map(([step, title, description], index) => {
          const active = index === 0 || (index === 1 && upload) || (index === 2 && result);
          return (
            <div
              key={step}
              className={`rounded-xl border px-3 py-3 transition sm:px-4 ${
                active
                  ? "border-blue-200 bg-blue-50/70"
                  : "border-slate-200/80 bg-white/60"
              }`}
            >
              <p className={`text-[10px] font-black ${active ? "text-blue-600" : "text-slate-400"}`}>
                STEP {step}
              </p>
              <p className="mt-1 text-xs font-bold text-slate-800 sm:text-sm">{title}</p>
              <p className="mt-1 hidden text-[11px] text-slate-500 sm:block">{description}</p>
            </div>
          );
        })}
      </div>

      <div className="space-y-5">
        <section className="surface-card rounded-2xl p-5 sm:p-7">
          <div className="mb-5 flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-black tracking-tight text-slate-950">上传文件</h2>
              <p className="mt-1 text-xs text-slate-500">
                最多 20 个文件，单个 50MB，总计 100MB
              </p>
            </div>
            {files.length > 0 ? (
              <button
                type="button"
                onClick={resetAll}
                className="text-xs font-semibold text-slate-500 transition hover:text-red-600"
              >
                清空全部
              </button>
            ) : null}
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            multiple
            className="sr-only"
            onChange={handleFileInput}
          />
          <div
            role="button"
            tabIndex={0}
            aria-label="选择 Excel 或 CSV 文件"
            onClick={() => !busy && fileInputRef.current?.click()}
            onKeyDown={handleDropzoneKeyDown}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={`relative grid min-h-44 place-items-center overflow-hidden rounded-2xl border-2 border-dashed px-5 py-8 text-center transition ${
              isDragging
                ? "border-blue-500 bg-blue-50"
                : "border-slate-200 bg-slate-50/70 hover:border-blue-300 hover:bg-blue-50/40"
            }`}
          >
            <div>
              <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-white text-blue-600 shadow-sm ring-1 ring-slate-200">
                {phase === "inspecting" ? (
                  <Loader2 size={23} className="animate-spin" />
                ) : (
                  <UploadCloud size={23} />
                )}
              </span>
              <p className="mt-4 text-sm font-bold text-slate-800">
                {phase === "inspecting" ? "正在读取工作表…" : "拖拽文件到这里，或点击选择"}
              </p>
              <p className="mt-2 text-xs text-slate-500">
                支持 Excel 多工作表与中文 CSV 编码
              </p>
            </div>
          </div>

          {files.length > 0 ? (
            <div className="mt-4 space-y-2">
              {files.map((file, index) => (
                <div
                  key={`${file.name}-${file.lastModified}`}
                  className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3.5 py-3"
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-emerald-50 text-emerald-700">
                    <FileSpreadsheet size={17} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-slate-800">{file.name}</p>
                    <p className="mt-0.5 text-[11px] text-slate-400">
                      {file.name.split(".").pop()?.toUpperCase()} · {formatBytes(file.size)}
                    </p>
                  </div>
                  <button
                    type="button"
                    aria-label={`移除 ${file.name}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      removeFile(index);
                    }}
                    disabled={busy}
                    className="grid size-8 place-items-center rounded-lg text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                  >
                    <X size={16} />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={inspectFiles}
                disabled={busy || Boolean(upload)}
                className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-slate-950 px-4 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-45 sm:w-auto"
              >
                {phase === "inspecting" ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : upload ? (
                  <CheckCircle2 size={16} />
                ) : (
                  <Table2 size={16} />
                )}
                {upload ? "文件已解析" : "读取工作表"}
              </button>
            </div>
          ) : null}
        </section>

        {upload ? (
          <section className="surface-card fade-up rounded-2xl p-5 sm:p-7">
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-black tracking-tight text-slate-950">选择工作表</h2>
                <p className="mt-1 text-xs text-slate-500">
                  已选择 {selectedRefs.length} / {allSheets.length} 个工作表
                </p>
              </div>
              <button
                type="button"
                onClick={toggleAllSheets}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 transition hover:border-blue-200 hover:text-blue-700"
              >
                {selectedRefs.length === allSheets.length ? "取消全选" : "全选工作表"}
              </button>
            </div>

            <div className="space-y-4">
              {upload.files.map((file) => (
                <div key={file.file_id} className="rounded-xl border border-slate-200 bg-slate-50/60 p-3.5">
                  <div className="mb-3 flex items-center gap-2.5">
                    <span className="grid size-8 place-items-center rounded-lg bg-white text-emerald-700 shadow-sm ring-1 ring-slate-200">
                      <FileSpreadsheet size={15} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-bold text-slate-800">{file.name}</p>
                      <p className="text-[10px] text-slate-400">{formatBytes(file.size)}</p>
                    </div>
                    <span className="rounded-md bg-white px-2 py-1 text-[10px] font-black uppercase text-slate-500 ring-1 ring-slate-200">
                      {file.format}
                    </span>
                  </div>
                  <div className="grid gap-2 lg:grid-cols-2">
                    {file.sheets.map((sheet) => {
                      const checked = (selected[file.file_id] ?? []).includes(sheet.sheet_index);
                      return (
                        <label
                          key={sheet.sheet_index}
                          className={`flex items-start gap-3 rounded-xl border p-3 transition ${
                            checked
                              ? "border-blue-200 bg-white shadow-sm"
                              : "border-slate-200 bg-white/50 hover:border-slate-300"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleSheet(file.file_id, sheet.sheet_index)}
                            className="sr-only"
                          />
                          <span
                            className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-md border ${
                              checked
                                ? "border-blue-600 bg-blue-600 text-white"
                                : "border-slate-300 bg-white text-transparent"
                            }`}
                          >
                            <Check size={13} strokeWidth={3} />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-semibold text-slate-800">
                              {sheet.name}
                            </span>
                            <span className="mt-1 block text-[11px] text-slate-500">
                              {sheet.row_count.toLocaleString("zh-CN")} 行 · {sheet.column_count} 列
                            </span>
                            <span className="mt-1 block truncate text-[10px] text-slate-400">
                              {sheet.headers.join(" / ") || "无表头"}
                            </span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {upload ? (
          <section className="surface-card fade-up rounded-2xl p-5 sm:p-7">
            <div className="mb-5">
              <h2 className="text-lg font-black tracking-tight text-slate-950">处理规则</h2>
              <p className="mt-1 text-xs text-slate-500">选择一种处理方式并设置规则</p>
            </div>

            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {operations.map(({ id, label, description, icon: Icon }) => {
                const active = mode === id;
                return (
                  <button
                    key={id}
                    type="button"
                    aria-pressed={active}
                    onClick={() => {
                      setMode(id);
                      setResult(null);
                      setError("");
                    }}
                    className={`rounded-xl border p-3.5 text-left transition ${
                      active
                        ? "border-blue-500 bg-blue-50 ring-2 ring-blue-100"
                        : "border-slate-200 bg-white hover:border-blue-200"
                    }`}
                  >
                    <Icon size={19} className={active ? "text-blue-600" : "text-slate-400"} />
                    <span className="mt-3 block text-sm font-bold text-slate-800">{label}</span>
                    <span className="mt-1 block text-[11px] leading-5 text-slate-500">
                      {description}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_1fr]">
              <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
                <Toggle
                  checked={hasHeader}
                  onChange={(checked) => {
                    setHasHeader(checked);
                    setResult(null);
                  }}
                  label="首行是表头"
                  description="拆分时每份文件重复表头；关闭后使用“列1、列2…”"
                />

                {mode === "by_rows" ? (
                  <label className="mt-3 block rounded-xl border border-slate-200 bg-white p-4">
                    <span className="block text-sm font-semibold text-slate-800">每份最大数据行数</span>
                    <span className="mt-1 block text-xs text-slate-500">
                      范围 1–50,000，表头不计数
                    </span>
                    <input
                      type="number"
                      min={1}
                      max={50000}
                      value={rowsPerFile}
                      onChange={(event) => {
                        setRowsPerFile(event.target.value);
                        setResult(null);
                      }}
                      className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-semibold text-slate-800 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                    />
                  </label>
                ) : null}

                {mode === "by_column" ? (
                  <label className="mt-3 block rounded-xl border border-slate-200 bg-white p-4">
                    <span className="block text-sm font-semibold text-slate-800">拆分依据列</span>
                    <span className="mt-1 block text-xs text-slate-500">
                      按列位置应用到所有选中的工作表
                    </span>
                    <select
                      value={effectiveColumnIndex}
                      onChange={(event) => {
                        setColumnIndex(event.target.value);
                        setResult(null);
                      }}
                      disabled={columnOptions.length === 0}
                      className="mt-3 w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-800 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                    >
                      {columnOptions.map((header, index) => (
                        <option key={`${header}-${index}`} value={index}>
                          第 {index + 1} 列 · {header}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}

                {mode === "merge" ? (
                  <div className="mt-3 rounded-xl border border-slate-200 bg-white p-4">
                    <p className="text-sm font-semibold text-slate-800">表头不一致时</p>
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setHeaderStrategy("strict");
                          setResult(null);
                        }}
                        className={`rounded-lg border px-3 py-2.5 text-xs font-bold ${
                          headerStrategy === "strict"
                            ? "border-blue-500 bg-blue-50 text-blue-700"
                            : "border-slate-200 text-slate-600"
                        }`}
                      >
                        拒绝并提示
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setHeaderStrategy("by_name");
                          setResult(null);
                        }}
                        className={`rounded-lg border px-3 py-2.5 text-xs font-bold ${
                          headerStrategy === "by_name"
                            ? "border-blue-500 bg-blue-50 text-blue-700"
                            : "border-slate-200 text-slate-600"
                        }`}
                      >
                        按列名对齐
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
                <Toggle
                  checked={removeEmptyRows}
                  onChange={(checked) => {
                    setRemoveEmptyRows(checked);
                    setResult(null);
                  }}
                  label="去除空行"
                  description="删除所有单元格为空或仅含空白的行"
                />
                <Toggle
                  checked={removeDuplicates}
                  onChange={(checked) => {
                    setRemoveDuplicates(checked);
                    setResult(null);
                  }}
                  label="去除重复行"
                  description="按所有输出列的实际值判断重复"
                />
              </div>
            </div>

            <div className="mt-5 flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="inline-flex items-center gap-1.5 text-[11px] text-slate-500">
                <LockKeyhole size={13} />
                原文件与结果均会在 30 分钟后自动删除
              </p>
              <button
                type="button"
                onClick={runTool}
                disabled={busy || selectedRefs.length === 0}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-blue-600/15 transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-45"
              >
                {phase === "processing" ? (
                  <Loader2 size={17} className="animate-spin" />
                ) : mode === "merge" ? (
                  <Files size={17} />
                ) : (
                  <ArrowRight size={17} />
                )}
                {phase === "processing"
                  ? "正在处理，请稍候…"
                  : mode === "merge"
                    ? "开始合并"
                    : "开始拆分"}
              </button>
            </div>
          </section>
        ) : null}

        {error ? (
          <StatusBanner tone="error">
            <span>{error}</span>
            {!upload && files.length > 0 ? (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="ml-2 font-bold underline underline-offset-2"
              >
                重新选择
              </button>
            ) : null}
          </StatusBanner>
        ) : null}

        {result ? (
          <section className="fade-up overflow-hidden rounded-2xl border border-emerald-200 bg-white shadow-xl shadow-emerald-950/5">
            <div className="bg-gradient-to-r from-emerald-50 to-cyan-50 px-5 py-5 sm:px-7">
              <div className="flex items-start gap-3">
                <span className="grid size-11 place-items-center rounded-xl bg-emerald-600 text-white shadow-sm">
                  <CheckCircle2 size={22} />
                </span>
                <div>
                  <h2 className="text-lg font-black text-slate-950">
                    {mode === "merge" ? "合并完成" : "拆分完成"}
                  </h2>
                  <p className="mt-1 text-xs leading-5 text-slate-600">
                    {mode === "merge"
                      ? `共合并 ${(result.row_count ?? 0).toLocaleString("zh-CN")} 行数据`
                      : `共生成 ${result.output_count.toLocaleString("zh-CN")} 个文件`}
                    ，请在 {formatExpiry(result.expires_at)} 前下载。
                  </p>
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-7">
              <div className="flex min-w-0 items-center gap-3">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-600">
                  {result.filename.endsWith(".zip") ? <Files size={19} /> : <FileSpreadsheet size={19} />}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-slate-800">{result.filename}</p>
                  <p className="mt-0.5 text-[11px] text-slate-400">
                    {formatBytes(result.size)}
                    {demoMode ? " · 演示说明文件" : ""}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setResult(null)}
                  className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-bold text-slate-600 transition hover:bg-slate-50"
                >
                  <RefreshCw size={14} />
                  继续调整
                </button>
                <a
                  href={result.download_url}
                  download={result.filename}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-950 px-4 py-2.5 text-xs font-bold text-white transition hover:bg-slate-800"
                >
                  <Download size={15} />
                  {demoMode ? "下载演示结果" : "下载结果"}
                </a>
              </div>
            </div>
          </section>
        ) : null}

        {files.length === 0 && !error ? (
          <div className="flex items-start gap-2 rounded-xl border border-slate-200 bg-white/60 px-4 py-3 text-xs leading-5 text-slate-500">
            <AlertCircle size={15} className="mt-0.5 shrink-0 text-slate-400" />
            Excel 输出只保留单元格值，不保留公式、图片、批注和原始样式。CSV 拆分结果保持 CSV 格式。
          </div>
        ) : null}
      </div>
    </div>
  );
}

