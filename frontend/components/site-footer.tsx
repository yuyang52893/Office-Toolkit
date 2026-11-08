import { LockKeyhole } from "lucide-react";

export function SiteFooter() {
  return (
    <footer className="border-t border-slate-200/80 px-4 py-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
        <p>轻办公工具箱 · 让重复工作少一步</p>
        <p className="flex items-center gap-1.5">
          <LockKeyhole size={13} />
          文件仅用于本次处理，30 分钟后自动删除
        </p>
      </div>
    </footer>
  );
}

