import { FileSpreadsheet, LayoutGrid } from "lucide-react";
import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="group flex items-center gap-3" aria-label="轻办公工具箱首页">
          <span className="grid size-9 place-items-center rounded-xl bg-blue-600 text-white shadow-sm shadow-blue-200 transition group-hover:-rotate-3">
            <FileSpreadsheet size={19} strokeWidth={2.2} />
          </span>
          <span>
            <span className="block text-[15px] font-bold tracking-tight text-slate-950">
              轻办公工具箱
            </span>
            <span className="block text-[10px] font-medium tracking-[0.14em] text-slate-400">
              SIMPLE OFFICE TOOLS
            </span>
          </span>
        </Link>

        <Link
          href="/"
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-blue-50 hover:text-blue-700"
        >
          <LayoutGrid size={16} />
          功能选择
        </Link>
      </div>
    </header>
  );
}

