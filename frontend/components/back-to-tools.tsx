import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export function BackToTools() {
  return (
    <Link
      href="/"
      className="inline-flex items-center gap-1.5 rounded-lg text-xs font-bold text-slate-500 transition hover:text-blue-700"
    >
      <ArrowLeft size={14} />
      返回功能选择
    </Link>
  );
}

