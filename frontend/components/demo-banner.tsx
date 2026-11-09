import { FlaskConical } from "lucide-react";

import { demoMode } from "@/lib/config";

export function DemoBanner() {
  if (!demoMode) {
    return null;
  }

  return (
    <div className="border-b border-amber-200/80 bg-amber-50 px-4 py-2 text-center text-xs font-semibold text-amber-800">
      <span className="inline-flex items-center justify-center gap-2">
        <FlaskConical size={14} />
        演示模式 · 数据为模拟
        <span className="hidden font-normal text-amber-700 sm:inline">
          用于评审页面和操作流程，不会调用真实后端
        </span>
      </span>
    </div>
  );
}

