"use client";

import { KeyRound, Loader2, RefreshCw, Search, ShieldCheck, UserX } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { StatusBanner } from "@/components/status-banner";
import { useAuth } from "@/components/auth-provider";
import {
  forceAdminUserLogout,
  listAdminUsers,
  resetAdminUserPassword,
  setAdminUserRole,
  setAdminUserStatus,
} from "@/lib/auth-api";
import { getErrorMessage } from "@/lib/format";
import type { AuthUser } from "@/lib/types";

type TemporaryPassword = {
  username: string;
  value: string;
};

function formatDate(value: string | null) {
  if (!value) {
    return "从未登录";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("zh-CN");
}

export function AdminUserTable() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [temporary, setTemporary] = useState<TemporaryPassword | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setUsers(await listAdminUsers());
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const filtered = useMemo(
    () => users.filter((user) => user.username.includes(query.trim())),
    [query, users],
  );

  function replaceUser(next: AuthUser) {
    setUsers((current) => current.map((user) => (user.id === next.id ? next : user)));
  }

  async function run(
    userId: number,
    action: () => Promise<AuthUser>,
    successMessage: string,
  ) {
    setPendingId(userId);
    setError("");
    setNotice("");
    try {
      replaceUser(await action());
      setNotice(successMessage);
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setPendingId(null);
    }
  }

  async function resetPassword(target: AuthUser) {
    setPendingId(target.id);
    setError("");
    setNotice("");
    setTemporary(null);
    try {
      const data = await resetAdminUserPassword(target.id);
      replaceUser(data.user);
      setTemporary({ username: target.username, value: data.temporary_password });
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setPendingId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-72 items-center justify-center text-sm font-semibold text-slate-500">
        <Loader2 size={18} className="mr-2 animate-spin" />
        正在读取账号…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="surface-card flex flex-col gap-3 rounded-2xl p-4 sm:flex-row sm:items-center sm:justify-between">
        <label className="relative block max-w-sm flex-1">
          <span className="sr-only">搜索用户名</span>
          <Search
            size={15}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            inputMode="numeric"
            placeholder="搜索 8–18 位用户名"
            className="w-full rounded-xl border border-slate-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          />
        </label>
        <button
          type="button"
          onClick={() => void load()}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600"
        >
          <RefreshCw size={14} />
          刷新
        </button>
      </div>

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {notice ? <StatusBanner tone="success">{notice}</StatusBanner> : null}

      {temporary ? (
        <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
          <p className="text-sm font-bold text-amber-900">临时密码只显示这一次</p>
          <p className="mt-1 text-xs text-amber-700">
            用户 {temporary.username} 登录后必须先修改密码。
          </p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
            <code className="min-w-0 flex-1 rounded-lg bg-white px-3 py-2 font-mono text-sm font-bold text-slate-900">
              {temporary.value}
            </code>
            <button
              type="button"
              onClick={() => setTemporary(null)}
              className="rounded-lg bg-amber-900 px-3 py-2 text-xs font-bold text-white"
            >
              我已保存
            </button>
          </div>
        </section>
      ) : null}

      <div className="space-y-3">
        {filtered.map((target) => {
          const isSelf = currentUser?.id === target.id;
          const pending = pendingId === target.id;
          return (
            <article key={target.id} className="surface-card rounded-2xl p-4 sm:p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-mono text-sm font-black text-slate-900">{target.username}</h2>
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">
                      {target.role === "admin" ? "管理员" : "普通用户"}
                    </span>
                    <span
                      className={`rounded-md px-2 py-0.5 text-[10px] font-bold ${
                        target.is_active
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-red-50 text-red-700"
                      }`}
                    >
                      {target.is_active ? "启用" : "已禁用"}
                    </span>
                    {isSelf ? (
                      <span className="text-[10px] font-bold text-blue-600">当前账号</span>
                    ) : null}
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    创建于 {formatDate(target.created_at)} · 最近登录 {formatDate(target.last_login_at)}
                  </p>
                </div>

                {!isSelf ? (
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={pending}
                      onClick={() =>
                        void run(
                          target.id,
                          () => setAdminUserStatus(target.id, !target.is_active),
                          target.is_active ? "账号已禁用" : "账号已启用",
                        )
                      }
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 disabled:opacity-50"
                    >
                      <UserX size={14} />
                      {target.is_active ? "禁用账号" : "启用账号"}
                    </button>
                    <button
                      type="button"
                      disabled={pending}
                      onClick={() =>
                        void run(
                          target.id,
                          () =>
                            setAdminUserRole(
                              target.id,
                              target.role === "admin" ? "user" : "admin",
                            ),
                          target.role === "admin" ? "已降为普通用户" : "已设为管理员",
                        )
                      }
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 disabled:opacity-50"
                    >
                      <ShieldCheck size={14} />
                      {target.role === "admin" ? "设为普通用户" : "设为管理员"}
                    </button>
                    <button
                      type="button"
                      disabled={pending}
                      onClick={() =>
                        void run(target.id, () => forceAdminUserLogout(target.id), "已强制退出登录")
                      }
                      className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 disabled:opacity-50"
                    >
                      强制退出
                    </button>
                    <button
                      type="button"
                      disabled={pending}
                      onClick={() => void resetPassword(target)}
                      className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50"
                    >
                      <KeyRound size={14} />
                      重置密码
                    </button>
                  </div>
                ) : null}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
