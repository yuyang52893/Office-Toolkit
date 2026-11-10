"use client";

import { Loader2 } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/components/auth-provider";
import { StatusBanner } from "@/components/status-banner";

export function AuthGuard({
  children,
  role,
}: {
  children: ReactNode;
  role?: "user" | "admin";
}) {
  const { user, loading, refreshError, refresh } = useAuth();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !refreshError && !user) {
      window.location.replace(`/login?next=${encodeURIComponent(pathname)}`);
    } else if (
      !loading &&
      user?.must_change_password &&
      pathname !== "/change-password"
    ) {
      window.location.replace("/change-password");
    }
  }, [loading, pathname, refreshError, user]);

  if (refreshError) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16">
        <StatusBanner tone="error">{refreshError}</StatusBanner>
        <button
          type="button"
          onClick={() => void refresh()}
          className="mt-4 rounded-lg bg-slate-950 px-4 py-2 text-sm font-bold text-white"
        >
          重新验证
        </button>
      </div>
    );
  }

  if (loading || !user || (user.must_change_password && pathname !== "/change-password")) {
    return (
      <div className="grid min-h-[50vh] place-items-center">
        <span className="inline-flex items-center gap-2 text-sm font-semibold text-slate-500">
          <Loader2 size={17} className="animate-spin" />
          {loading ? "正在验证登录状态…" : "此功能仅登录用户可用"}
        </span>
      </div>
    );
  }

  if (role === "admin" && user.role !== "admin") {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center text-sm text-slate-600">
        当前账号没有管理员权限。
      </div>
    );
  }

  return children;
}
