"use client";

import { Download, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { StatusBanner } from "@/components/status-banner";
import { downloadRuntimeErrors, listRuntimeErrors } from "@/lib/auth-api";
import { getErrorMessage } from "@/lib/format";
import type { RuntimeErrorItem } from "@/lib/types";

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

function initialDate() {
  return new Date().toLocaleDateString("sv-SE");
}

export function RuntimeErrorTable() {
  const [date, setDate] = useState("");
  const [items, setItems] = useState<RuntimeErrorItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setDate(initialDate()), 0);
    return () => window.clearTimeout(timer);
  }, []);

  const load = useCallback(async (selectedDate: string, selectedPage: number) => {
    if (!selectedDate) return;
    setLoading(true);
    setError("");
    try {
      const data = await listRuntimeErrors(selectedDate, selectedPage);
      setItems(data.items);
      setTotal(data.total);
      setPage(data.page);
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(date, page), 0);
    return () => window.clearTimeout(timer);
  }, [date, load, page]);

  async function download() {
    setDownloading(true);
    setError("");
    try {
      saveBlob(await downloadRuntimeErrors(date), `runtime-errors-${date}.jsonl`);
    } catch (downloadError) {
      setError(getErrorMessage(downloadError));
    } finally {
      setDownloading(false);
    }
  }

  const pages = Math.max(1, Math.ceil(total / 50));

  return (
    <div className="space-y-4">
      <div className="surface-card flex flex-col gap-3 rounded-2xl p-4 sm:flex-row sm:items-end sm:justify-between">
        <label className="text-xs font-bold text-slate-600">
          日期
          <input
            type="date"
            value={date}
            max={initialDate()}
            onChange={(event) => {
              setDate(event.target.value);
              setPage(1);
            }}
            className="mt-1 block rounded-lg border border-slate-200 px-2 py-2 text-sm"
          />
        </label>
        <button
          type="button"
          disabled={!date || downloading}
          onClick={() => void download()}
          className="inline-flex items-center justify-center gap-1 rounded-lg bg-slate-950 px-3 py-2 text-xs font-bold text-white disabled:opacity-40"
        >
          {downloading ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
          下载错误文件
        </button>
      </div>

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

      {loading ? (
        <div className="flex min-h-52 items-center justify-center text-sm text-slate-500">
          <Loader2 size={17} className="mr-2 animate-spin" />
          正在读取运行错误…
        </div>
      ) : items.length === 0 ? (
        <p className="surface-card rounded-2xl px-5 py-12 text-center text-sm text-slate-500">
          该日期没有运行错误记录。
        </p>
      ) : (
        <div className="space-y-2">
          {items.map((item, index) => (
            <article key={`${date}-${index}`} className="surface-card rounded-xl p-4 text-xs">
              <div className="flex flex-wrap gap-2">
                <span className="rounded bg-red-50 px-2 py-0.5 font-bold text-red-700">
                  {item.level ?? "ERROR"}
                </span>
                <span className="font-mono text-slate-500">{item.logger ?? "unknown"}</span>
                <span className="text-slate-400">{item.timestamp ?? "—"}</span>
              </div>
              <p className="mt-2 break-words font-semibold text-slate-800">
                {item.message ?? item.event ?? "未命名错误"}
              </p>
            </article>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>共 {total} 条</span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
            className="rounded-lg border border-slate-200 px-3 py-1.5 font-bold disabled:opacity-40"
          >
            上一页
          </button>
          <span className="py-1.5">
            {page} / {pages}
          </span>
          <button
            type="button"
            disabled={page >= pages}
            onClick={() => setPage((current) => current + 1)}
            className="rounded-lg border border-slate-200 px-3 py-1.5 font-bold disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  );
}
