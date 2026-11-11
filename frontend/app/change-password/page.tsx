"use client";

import { KeyRound, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthGuard } from "@/components/auth-guard";
import { useAuth } from "@/components/auth-provider";
import { StatusBanner } from "@/components/status-banner";
import { changePassword } from "@/lib/auth-api";
import { setToken } from "@/lib/auth-storage";
import { getErrorMessage } from "@/lib/format";

function ChangePasswordContent() {
  const { refresh } = useAuth();
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setError("");
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
      const token = await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setToken(token);
      await refresh();
      router.push("/");
      router.refresh();
    } catch (changeError) {
      setError(getErrorMessage(changeError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-12 sm:py-16">
      <section className="surface-card rounded-2xl p-6 sm:p-8">
        <span className="grid size-11 place-items-center rounded-xl bg-blue-600 text-white">
          <KeyRound size={20} />
        </span>
        <h1 className="mt-4 text-2xl font-black tracking-tight text-slate-950">修改密码</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          修改后其他设备上的旧登录凭证会立即失效。
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
          className="mt-6 space-y-4"
        >
          <label className="block">
            <span className="text-sm font-semibold text-slate-800">当前密码</span>
            <input
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              autoComplete="current-password"
              maxLength={100}
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
            {loading ? "正在保存…" : "保存新密码"}
          </button>
        </form>
      </section>
    </div>
  );
}

export default function ChangePasswordPage() {
  return (
    <AuthGuard>
      <ChangePasswordContent />
    </AuthGuard>
  );
}
