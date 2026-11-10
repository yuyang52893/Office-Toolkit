"use client";

import {
  Clock3,
  Download,
  FileArchive,
  History,
  Loader2,
  LockKeyhole,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { StatusBanner } from "@/components/status-banner";
import { downloadHistoryFile, listHistory } from "@/lib/auth-api";
import { ApiError } from "@/lib/errors";
import { formatBytes, getErrorMessage } from "@/lib/format";
import type { HistoryItem } from "@/lib/types";

const toolLabels: Record<string, string> = {
  excel: "Excel / CSV",
  qrcode: "二维码",
  mac: "MAC 地址",
};

const reasonLabels: Record<NonNullable<HistoryItem["expire_reason"]>, string> = {
  timeout: "30 分钟已到期",
  quota_count: "超过 10 个文件上限，已自动清理",
  quota_size: "超过 200MB 存储上限，已自动清理",
};

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function summaryLabel(item: HistoryItem): string {
  if (typeof item.summary.output_count === "number") {
    return `${item.summary.output_count} 个输出文件`;
  }
  if (typeof item.summary.row_count === "number") {
    return `${item.summary.row_count.toLocaleString("zh-CN")} 行`;
  }
  if (typeof item.summary.count === "number") {
    return `${item.summary.count} 个二维码`;
  }
  return item.operation;
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function HistoryList() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState("");
  const [error, setError] = useState("");
  const [downloadError, setDownloadError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setItems(await listHistory());
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.status === 401) {
        window.location.replace("/login?next=%2Fhistory");
        return;
      }
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function download(item: HistoryItem) {
    setDownloading(item.id);
    setDownloadError("");
    try {
      saveBlob(await downloadHistoryFile(item.id), item.result_filename);
    } catch (downloadFailure) {
      if (downloadFailure instanceof ApiError && downloadFailure.status === 401) {
        window.location.replace("/login?next=%2Fhistory");
      } else if (downloadFailure instanceof ApiError && downloadFailure.status === 410) {
        setDownloadError("文件已过期，请重新处理");
      } else if (downloadFailure instanceof ApiError && downloadFailure.status === 403) {
        setDownloadError("没有权限下载该文件");
      } else {
        setDownloadError(getErrorMessage(downloadFailure));
      }
    } finally {
      setDownloading("");
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-72 items-center justify-center text-sm font-semibold text-slate-500">
        <Loader2 size={18} className="mr-2 animate-spin" />
        正在读取历史记录…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error ? (
        <StatusBanner tone="error">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => void load()}
            className="ml-2 font-bold underline underline-offset-2"
          >
            重新加载
          </button>
        </StatusBanner>
      ) : null}

      {downloadError ? <StatusBanner tone="error">{downloadError}</StatusBanner> : null}

      {!error && items.length === 0 ? (
        <div className="surface-card rounded-2xl px-6 py-16 text-center">
          <History size={36} className="mx-auto text-slate-300" />
          <p className="mt-4 text-sm font-bold text-slate-700">还没有处理历史</p>
          <p className="mt-1 text-xs text-slate-500">登录后成功处理文件，结果会显示在这里。</p>
        </div>
      ) : null}

      {items.map((item) => {
        const active = item.status === "active";
        return (
          <article key={item.id} className="surface-card rounded-2xl p-5 sm:p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex min-w-0 items-start gap-3">
                <span
                  className={`grid size-11 shrink-0 place-items-center rounded-xl ${
                    active ? "bg-blue-50 text-blue-600" : "bg-slate-100 text-slate-400"
                  }`}
                >
                  {active ? <FileArchive size={20} /> : <ShieldAlert size={20} />}
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-sm font-bold text-slate-900">
                      {item.result_filename}
                    </h2>
                    <span
                      className={`rounded-md px-2 py-0.5 text-[10px] font-bold ${
                        active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"
                      }`}
                    >
                      {active ? "可下载" : "已过期"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {toolLabels[item.tool] ?? item.tool} · {summaryLabel(item)} ·{" "}
                    {formatBytes(item.size_bytes)}
                  </p>
                  <p className="mt-2 flex items-center gap-1.5 text-[11px] text-slate-400">
                    <Clock3 size={12} />
                    完成于 {formatDate(item.completed_at)}
                    {active
                      ? `，有效至 ${formatDate(item.expires_at)}`
                      : `，${item.expire_reason ? reasonLabels[item.expire_reason] : "文件已失效"}`}
                  </p>
                  {!active && item.purge_after ? (
                    <p className="mt-1 text-[11px] text-slate-400">
                      记录将在 {formatDate(item.purge_after)} 自动移除
                    </p>
                  ) : null}
                </div>
              </div>

              {active ? (
                <a
                  href={`/api/v1/history/${encodeURIComponent(item.id)}/download`}
                  onClick={(event) => {
                    event.preventDefault();
                    void download(item);
                  }}
                  className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-slate-950 px-4 py-2.5 text-xs font-bold text-white transition hover:bg-slate-800"
                >
                  {downloading === item.id ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <Download size={15} />
                  )}
                  下载结果
                </a>
              ) : (
                <span className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-slate-100 px-4 py-2.5 text-xs font-bold text-slate-400">
                  <LockKeyhole size={15} />
                  无法下载
                </span>
              )}
            </div>
          </article>
        );
      })}

      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={() => void load()}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 transition hover:text-blue-700"
        >
          <RefreshCw size={13} />
          刷新列表
        </button>
      </div>
    </div>
  );
}
