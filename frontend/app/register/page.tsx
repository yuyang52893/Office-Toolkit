"use client";

import { Loader2, UserPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { StatusBanner } from "@/components/status-banner";
import { loginAccount, registerAccount } from "@/lib/auth-api";
import { setToken } from "@/lib/auth-storage";
import { getErrorMessage } from "@/lib/format";

export default function RegisterPage() {
  const { refresh } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setError("");
    const validationErrors: string[] = [];
    if (!/^[0-9]{8,18}$/.test(username)) {
      validationErrors.push("用户名必须是 8–18 位数字");
    }
    if (password.length < 8 || password.length > 18) {
      validationErrors.push("密码长度必须为 8–18 位");
    }
    if (question.trim().length < 2 || !answer.trim()) {
      validationErrors.push("请填写自定义找回问题和答案");
    }
    if (validationErrors.length > 0) {
      setError(validationErrors.join("；"));
      return;
    }
    setLoading(true);
    try {
      await registerAccount({
        username,
        password,
        recovery_question: question,
        recovery_answer: answer,
      });
      const login = await loginAccount(username, password);
      setToken(login.access_token);
      await refresh();
      router.push("/");
      router.refresh();
    } catch (registerError) {
      setError(getErrorMessage(registerError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-12 sm:py-16">
      <section className="surface-card rounded-2xl p-6 sm:p-8">
        <span className="grid size-11 place-items-center rounded-xl bg-blue-600 text-white">
          <UserPlus size={20} />
        </span>
        <h1 className="mt-4 text-2xl font-black tracking-tight text-slate-950">注册账号</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          用户名只能是 8–18 位数字。自定义找回问题和答案用于重置密码。
        </p>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
          className="mt-6 space-y-4"
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
              autoComplete="new-password"
              maxLength={18}
              className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-slate-800">找回问题</span>
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              maxLength={200}
              className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-slate-800">找回答案</span>
            <input
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              maxLength={200}
              className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
          <button
            type="submit"
            disabled={loading}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white transition hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <UserPlus size={16} />}
            {loading ? "正在注册…" : "注册账号"}
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-slate-500">
          已有账号？<Link href="/login" className="font-bold text-blue-700">直接登录</Link>
        </p>
      </section>
    </div>
  );
}
