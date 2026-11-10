"use client";

import { Loader2 } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/components/auth-provider";

export function AuthGuard({
  children,
  role,
}: {
  children: ReactNode;
  role?: "user" | "admin";
}) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      window.location.replace(`/login?next=${encodeURIComponent(pathname)}`);
    } else if (
      !loading &&
      user?.must_change_password &&
      pathname !== "/change-password"
    ) {
      window.location.replace("/change-password");
    }
  }, [loading, pathname, user]);

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
