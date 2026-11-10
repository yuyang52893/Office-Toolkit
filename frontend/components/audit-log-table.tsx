"use client";

import { Download, Loader2, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { StatusBanner } from "@/components/status-banner";
import { downloadAuditLogs, listAuditLogs, type AuditLogFilters } from "@/lib/auth-api";
import { getErrorMessage } from "@/lib/format";
import type { AuditLogItem } from "@/lib/types";

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

export function AuditLogTable() {
  const [filters, setFilters] = useState<AuditLogFilters>({
    date: "",
    event: "",
    outcome: "",
    request_id: "",
    username: "",
    page: 1,
    page_size: 50,
  });
  const [items, setItems] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(
      () => setFilters((current) => ({ ...current, date: initialDate() })),
      0,
    );
    return () => window.clearTimeout(timer);
  }, []);

  const load = useCallback(async (next: AuditLogFilters) => {
    setLoading(true);
    setError("");
    try {
      const data = await listAuditLogs(next);
      setItems(data.items);
      setTotal(data.total);
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (filters.date) {
      const timer = window.setTimeout(() => void load(filters), 0);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [filters, load]);

  async function download(format: "csv" | "json") {
    setDownloading(format);
    setError("");
    try {
      saveBlob(await downloadAuditLogs(filters, format), `audit-${filters.date}.${format}`);
    } catch (downloadError) {
      setError(getErrorMessage(downloadError));
    } finally {
      setDownloading("");
    }
  }

  const pages = Math.max(1, Math.ceil(total / (filters.page_size ?? 50)));

  return (
    <div className="space-y-4">
      <div className="surface-card grid gap-3 rounded-2xl p-4 md:grid-cols-3 lg:grid-cols-6">
        <label className="text-xs font-bold text-slate-600">
          日期
          <input
            type="date"
            value={filters.date}
            max={initialDate()}
            onChange={(event) => setFilters({ ...filters, date: event.target.value, page: 1 })}
            className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2 text-sm"
          />
        </label>
        <label className="text-xs font-bold text-slate-600">
          用户名
          <input
            inputMode="numeric"
            value={filters.username}
            onChange={(event) => setFilters({ ...filters, username: event.target.value, page: 1 })}
            className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2 text-sm"
          />
        </label>
        <label className="text-xs font-bold text-slate-600">
          事件
          <input
            value={filters.event}
            onChange={(event) => setFilters({ ...filters, event: event.target.value, page: 1 })}
            className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2 text-sm"
          />
        </label>
        <label className="text-xs font-bold text-slate-600">
          结果
          <select
            value={filters.outcome}
            onChange={(event) =>
              setFilters({
                ...filters,
                outcome: event.target.value as AuditLogFilters["outcome"],
                page: 1,
              })
            }
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm"
          >
            <option value="">全部</option>
            <option value="success">成功</option>
            <option value="failure">失败</option>
          </select>
        </label>
        <label className="text-xs font-bold text-slate-600">
          请求编号
          <input
            value={filters.request_id}
            onChange={(event) => setFilters({ ...filters, request_id: event.target.value, page: 1 })}
            className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2 text-sm"
          />
        </label>
        <button
          type="button"
          onClick={() => void load(filters)}
          className="mt-auto inline-flex items-center justify-center gap-1 rounded-lg bg-slate-950 px-3 py-2.5 text-xs font-bold text-white"
        >
          <Search size={14} />
          查询
        </button>
      </div>

      <div className="flex flex-wrap justify-end gap-2">
        <button
          type="button"
          onClick={() => void download("csv")}
          disabled={Boolean(downloading)}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600"
        >
          {downloading === "csv" ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
          下载 CSV
        </button>
        <button
          type="button"
          onClick={() => void download("json")}
          disabled={Boolean(downloading)}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600"
        >
          {downloading === "json" ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
          下载 JSON
        </button>
      </div>

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

      {loading ? (
        <div className="flex min-h-52 items-center justify-center text-sm text-slate-500">
          <Loader2 size={17} className="mr-2 animate-spin" />
          正在读取审计日志…
        </div>
      ) : (
        <div className="space-y-2">
          {items.length === 0 ? (
            <p className="surface-card rounded-2xl px-5 py-12 text-center text-sm text-slate-500">
              当前筛选条件下没有日志。
            </p>
          ) : (
            items.map((item) => (
              <article key={item.id} className="surface-card rounded-xl p-4 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono font-bold text-slate-800">{item.event}</span>
                  <span
                    className={`rounded px-2 py-0.5 font-bold ${
                      item.outcome === "success"
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-red-50 text-red-700"
                    }`}
                  >
                    {item.outcome === "success" ? "成功" : "失败"}
                  </span>
                  <span className="text-slate-400">{item.created_at}</span>
                </div>
                <p className="mt-2 text-slate-500">
                  操作人 {item.actor_username ?? "—"} · 目标 {item.target_username ?? "—"} · IP {item.ip}
                </p>
                <p className="mt-1 break-all font-mono text-[10px] text-slate-400">
                  {item.request_id}
                </p>
                <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-50 p-2 text-[10px] text-slate-600">
                  {JSON.stringify(item.details, null, 2)}
                </pre>
              </article>
            ))
          )}
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>共 {total} 条</span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={(filters.page ?? 1) <= 1}
            onClick={() => {
              const next = { ...filters, page: Math.max(1, (filters.page ?? 1) - 1) };
              setFilters(next);
            }}
            className="rounded-lg border border-slate-200 px-3 py-1.5 font-bold disabled:opacity-40"
          >
            上一页
          </button>
          <span className="py-1.5">
            {filters.page ?? 1} / {pages}
          </span>
          <button
            type="button"
            disabled={(filters.page ?? 1) >= pages}
            onClick={() => {
              const next = { ...filters, page: (filters.page ?? 1) + 1 };
              setFilters(next);
            }}
            className="rounded-lg border border-slate-200 px-3 py-1.5 font-bold disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  );
}
