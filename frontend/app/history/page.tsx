import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth-guard";
import { BackToTools } from "@/components/back-to-tools";
import { HistoryList } from "@/components/history-list";

export const metadata: Metadata = {
  title: "个人处理历史",
  description: "查看最近 30 分钟内保存的处理结果和已过期记录。",
};

export default function HistoryPage() {
  return (
    <AuthGuard>
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
        <div className="mb-5">
          <BackToTools />
        </div>
        <header className="mb-7">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-600">
            Personal History
          </p>
          <h1 className="mt-2 text-3xl font-black tracking-[-0.035em] text-slate-950">
            个人处理历史
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">
            文件完成后保留 30 分钟。过期或因存储配额清理后，记录会继续显示 3 小时。
          </p>
        </header>
        <HistoryList />
      </div>
    </AuthGuard>
  );
}
