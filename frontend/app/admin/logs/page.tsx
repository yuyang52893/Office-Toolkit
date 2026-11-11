"use client";

import { FileWarning, ScrollText } from "lucide-react";
import { useState } from "react";

import { AuditLogTable } from "@/components/audit-log-table";
import { AuthGuard } from "@/components/auth-guard";
import { BackToTools } from "@/components/back-to-tools";
import { RuntimeErrorTable } from "@/components/runtime-error-table";

type Tab = "audit" | "runtime";

export default function AdminLogsPage() {
  const [tab, setTab] = useState<Tab>("audit");

  return (
    <AuthGuard role="admin">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
        <div className="mb-5">
          <BackToTools />
        </div>
        <header className="mb-7">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-600">Log Center</p>
          <h1 className="mt-2 text-3xl font-black tracking-[-0.035em] text-slate-950">日志中心</h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">
            操作审计保留 30 天，运行错误文件保留 14 天。所有日志查看和下载都会记录审计事件。
          </p>
        </header>

        <div className="mb-5 flex gap-2">
          <button
            type="button"
            onClick={() => setTab("audit")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-bold ${
              tab === "audit" ? "bg-slate-950 text-white" : "border border-slate-200 text-slate-600"
            }`}
          >
            <ScrollText size={14} />
            操作审计
          </button>
          <button
            type="button"
            onClick={() => setTab("runtime")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-bold ${
              tab === "runtime" ? "bg-slate-950 text-white" : "border border-slate-200 text-slate-600"
            }`}
          >
            <FileWarning size={14} />
            运行错误
          </button>
        </div>

        {tab === "audit" ? <AuditLogTable /> : <RuntimeErrorTable />}
      </div>
    </AuthGuard>
  );
}
