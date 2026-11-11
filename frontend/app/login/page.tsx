"use client";

import { ArrowRight, Loader2, LogIn } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { StatusBanner } from "@/components/status-banner";
import { getErrorMessage } from "@/lib/format";

function safeNextPath(value: string): string {
  const baseOrigin = "http://same-origin.invalid";
  if (
    !value.startsWith("/") ||
    value.startsWith("//") ||
    /[\u0000-\u001f\\]/u.test(value)
  ) {
    return "";
  }
  try {
    const resolved = new URL(value, baseOrigin);
    return resolved.origin === baseOrigin
      ? `${resolved.pathname}${resolved.search}${resolved.hash}`
      : "";
  } catch {
    return "";
  }
}

function LoginContent() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const requestedNext = searchParams.get("next") ?? "";
  const nextPath = safeNextPath(requestedNext);

  async function submit() {
    setError("");
    if (!/^[0-9]{8,18}$/.test(username)) {
      setError("用户名必须是 8–18 位数字");
      return;
    }
    if (password.length < 8 || password.length > 18) {
      setError("密码长度必须为 8–18 位");
      return;
    }
    setLoading(true);
    try {
      const user = await login(username, password);
      router.push(user.must_change_password ? "/change-password" : nextPath || "/");
      router.refresh();
    } catch (loginError) {
      setError(getErrorMessage(loginError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-12 sm:py-16">
      <section className="surface-card rounded-2xl p-6 sm:p-8">
        <div className="mb-6">
          <span className="grid size-11 place-items-center rounded-xl bg-blue-600 text-white">
            <LogIn size={20} />
          </span>
          <h1 className="mt-4 text-2xl font-black tracking-tight text-slate-950">登录账号</h1>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            登录后可保存处理结果到个人历史。匿名工具仍然可以直接使用。
          </p>
        </div>

        {nextPath && !error ? (
          <div className="mb-4">
            <StatusBanner tone="loading">此功能仅登录用户可用</StatusBanner>
          </div>
        ) : null}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
          className="space-y-4"
        >
          <label className="block">
            <span className="text-sm font-semibold text-slate-800">用户名</span>
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              inputMode="numeric"
              autoComplete="username"
              maxLength={18}
              className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-slate-800">密码</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              maxLength={18}
              className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
          <button
            type="submit"
            disabled={loading}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white transition hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
            {loading ? "正在登录…" : "登录"}
            {!loading ? <ArrowRight size={15} /> : null}
          </button>
        </form>

        <div className="mt-5 flex justify-between text-xs font-bold text-blue-700">
          <Link href="/register">注册账号</Link>
          <Link href="/recover">找回密码</Link>
        </div>
      </section>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-md px-4 py-16 text-sm text-slate-500">正在加载…</div>}>
      <LoginContent />
    </Suspense>
  );
}
