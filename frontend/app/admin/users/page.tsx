import type { Metadata } from "next";

import { AdminUserTable } from "@/components/admin-user-table";
import { AuthGuard } from "@/components/auth-guard";
import { BackToTools } from "@/components/back-to-tools";

export const metadata: Metadata = {
  title: "账号管理",
  description: "管理员查看、禁用、启用账号并管理角色。",
};

export default function AdminUsersPage() {
  return (
    <AuthGuard role="admin">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
        <div className="mb-5">
          <BackToTools />
        </div>
        <header className="mb-7">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-600">Administration</p>
          <h1 className="mt-2 text-3xl font-black tracking-[-0.035em] text-slate-950">账号管理</h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">
            管理账号状态和角色。密码与找回答案不可查看，只能重置为一次性临时密码。
          </p>
        </header>
        <AdminUserTable />
      </div>
    </AuthGuard>
  );
}
