"use client";

import { History, LogIn, LogOut, ShieldCheck, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";

export function AccountNav() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  if (loading) {
    return <span className="text-xs text-slate-400">读取账号…</span>;
  }

  if (!user) {
    return (
      <div className="flex items-center gap-1">
        <Link
          href="/login"
          className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs font-bold text-slate-600 transition hover:bg-blue-50 hover:text-blue-700"
        >
          <LogIn size={14} />
          登录
        </Link>
        <Link
          href="/register"
          className="hidden rounded-lg px-2.5 py-2 text-xs font-bold text-blue-700 transition hover:bg-blue-50 sm:inline-flex"
        >
          注册
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-1">
      <span className="inline-flex items-center gap-1.5 px-2 text-xs font-bold text-slate-700">
        <UserRound size={14} />
        {user.username}
      </span>
      {!user.must_change_password ? (
        <Link
          href="/history"
          className="inline-flex items-center gap-1 rounded-lg px-2 py-2 text-xs font-bold text-slate-600 transition hover:bg-blue-50 hover:text-blue-700"
        >
          <History size={14} />
          个人历史
        </Link>
      ) : null}
      {user.role === "admin" && !user.must_change_password ? (
        <>
          <Link
            href="/admin/users"
            className="hidden items-center gap-1 rounded-lg px-2 py-2 text-xs font-bold text-slate-600 transition hover:bg-blue-50 hover:text-blue-700 sm:inline-flex"
          >
            <ShieldCheck size={14} />
            账号管理
          </Link>
          <Link
            href="/admin/logs"
            className="hidden rounded-lg px-2 py-2 text-xs font-bold text-slate-600 transition hover:bg-blue-50 hover:text-blue-700 sm:inline-flex"
          >
            日志中心
          </Link>
        </>
      ) : null}
      <button
        type="button"
        onClick={async () => {
          await logout();
          router.push("/");
          router.refresh();
        }}
        className="inline-flex items-center gap-1 rounded-lg px-2 py-2 text-xs font-bold text-slate-500 transition hover:bg-red-50 hover:text-red-600"
      >
        <LogOut size={14} />
        退出登录
      </button>
    </div>
  );
}
