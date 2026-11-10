"use client";

import { KeyRound, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { StatusBanner } from "@/components/status-banner";
import { getRecoveryQuestion, resetPassword } from "@/lib/auth-api";
import { getErrorMessage } from "@/lib/format";

export default function RecoverPage() {
  const [username, setUsername] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit() {
    setError("");
    if (!/^[0-9]{8,18}$/.test(username)) {
      setError("用户名必须是 8–18 位数字");
      return;
    }
    if (!question.trim() || !answer.trim()) {
      setError("请填写注册时设置的找回问题和答案");
      return;
    }
    if (newPassword.length < 8 || newPassword.length > 18) {
      setError("新密码长度必须为 8–18 位");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("两次输入的新密码不一致");
      return;
    }
    setLoading(true);
    try {
      setPrompt(await getRecoveryQuestion(username));
      await resetPassword({
        username,
        recovery_question: question,
        recovery_answer: answer,
        new_password: newPassword,
      });
      setSuccess(true);
    } catch (resetError) {
      setError(getErrorMessage(resetError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-12 sm:py-16">
      <section className="surface-card rounded-2xl p-6 sm:p-8">
        <span className="grid size-11 place-items-center rounded-xl bg-indigo-600 text-white">
          <KeyRound size={20} />
        </span>
        <h1 className="mt-4 text-2xl font-black tracking-tight text-slate-950">找回密码</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          输入注册时设置的找回问题和答案，验证成功后设置新密码。
        </p>

        {success ? (
          <div className="mt-6 space-y-4">
            <StatusBanner tone="success">密码已重置，请使用新密码登录</StatusBanner>
            <Link
              href="/login"
              className="inline-flex w-full justify-center rounded-xl bg-slate-950 px-5 py-3 text-sm font-bold text-white"
            >
              返回登录
            </Link>
          </div>
        ) : (
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
              <span className="text-sm font-semibold text-slate-800">找回问题</span>
              <input
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                maxLength={200}
                placeholder={prompt || "请输入注册时设置的问题"}
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
            <label className="block">
              <span className="text-sm font-semibold text-slate-800">新密码</span>
              <input
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                autoComplete="new-password"
                maxLength={18}
                className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
            </label>
            <label className="block">
              <span className="text-sm font-semibold text-slate-800">确认新密码</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
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
              {loading ? <Loader2 size={16} className="animate-spin" /> : <KeyRound size={16} />}
              {loading ? "正在验证…" : "重置密码"}
            </button>
          </form>
        )}

        <p className="mt-5 text-center text-xs text-slate-500">
          想起密码了？<Link href="/login" className="font-bold text-blue-700">返回登录</Link>
        </p>
      </section>
    </div>
  );
}
