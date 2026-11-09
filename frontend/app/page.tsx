import {
  ArrowRight,
  Files,
  Layers3,
  Network,
  QrCode,
  ScanLine,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

import { demoMode } from "@/lib/config";

type ToolAction = {
  title: string;
  description: string;
  href: string;
  icon: typeof Layers3;
  label: string;
  tags: string[];
  iconClass: string;
  accentClass: string;
};

const spreadsheetActions: ToolAction[] = [
  {
    title: "拆分 Excel / CSV",
    description: "把一个文件按工作表、固定行数或指定列拆成多个文件。",
    href: "/excel?mode=by_sheet",
    icon: Layers3,
    label: "SPLIT",
    tags: ["按工作表", "按行数", "按列值"],
    iconClass: "bg-blue-600 text-white shadow-blue-600/20",
    accentClass: "bg-blue-100/70",
  },
  {
    title: "合并多个表格",
    description: "把多个 Excel、XLS 或 CSV 的数据按行追加到一个结果文件。",
    href: "/excel?mode=merge",
    icon: Files,
    label: "MERGE",
    tags: ["批量上传", "表头对齐", "清理数据"],
    iconClass: "bg-slate-950 text-white shadow-slate-900/15",
    accentClass: "bg-sky-100/70",
  },
];

const qrActions: ToolAction[] = [
  {
    title: "生成二维码",
    description: "把文本或链接生成自定义尺寸的 PNG 二维码。",
    href: "/qrcode?tab=generate",
    icon: QrCode,
    label: "CREATE",
    tags: ["自定义尺寸", "PNG"],
    iconClass: "bg-indigo-600 text-white shadow-indigo-600/20",
    accentClass: "bg-indigo-100/70",
  },
  {
    title: "解析二维码图片",
    description: "上传截图或照片，识别图片中的所有二维码内容。",
    href: "/qrcode?tab=decode",
    icon: ScanLine,
    label: "SCAN",
    tags: ["多码识别", "PNG / JPG"],
    iconClass: "bg-cyan-600 text-white shadow-cyan-600/20",
    accentClass: "bg-cyan-100/70",
  },
  {
    title: "制作 MAC 地址二维码",
    description: "规范化已有 MAC 地址，并生成可直接下载的二维码。",
    href: "/qrcode?tab=mac",
    icon: Network,
    label: "MAC",
    tags: ["格式转换", "地址校验"],
    iconClass: "bg-emerald-600 text-white shadow-emerald-600/20",
    accentClass: "bg-emerald-100/70",
  },
];

function ToolCard({ action, compact = false }: { action: ToolAction; compact?: boolean }) {
  const Icon = action.icon;
  return (
    <Link
      href={action.href}
      className={`surface-card group relative overflow-hidden rounded-[24px] p-5 transition duration-200 hover:-translate-y-1 hover:border-blue-200 hover:shadow-xl hover:shadow-slate-900/8 sm:p-6 ${
        compact ? "min-h-56" : "min-h-64"
      }`}
    >
      <span
        className={`absolute -right-14 -top-14 size-40 rounded-full transition duration-300 group-hover:scale-125 ${action.accentClass}`}
      />
      <div className="relative flex h-full flex-col">
        <div className="flex items-start justify-between">
          <span
            className={`grid place-items-center rounded-2xl shadow-lg ${action.iconClass} ${
              compact ? "size-12" : "size-14"
            }`}
          >
            <Icon size={compact ? 23 : 27} />
          </span>
          <span className="text-[10px] font-black tracking-[0.18em] text-slate-400">
            {action.label}
          </span>
        </div>
        <h3 className="mt-5 text-xl font-black tracking-tight text-slate-950 sm:text-2xl">
          {action.title}
        </h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">{action.description}</p>
        <div className="mt-auto flex items-end justify-between gap-3 pt-5">
          <div className="flex flex-wrap gap-1.5">
            {action.tags.map((tag) => (
              <span
                key={tag}
                className="rounded-md border border-slate-200/80 bg-white/80 px-2 py-1 text-[10px] font-semibold text-slate-500"
              >
                {tag}
              </span>
            ))}
          </div>
          <span className="inline-flex shrink-0 items-center gap-1 text-xs font-bold text-blue-600">
            开始使用
            <ArrowRight size={14} className="transition group-hover:translate-x-1" />
          </span>
        </div>
      </div>
    </Link>
  );
}

export default function HomePage() {
  return (
    <div className="relative overflow-hidden">
      <div className="subtle-grid absolute inset-x-0 top-0 h-[34rem] opacity-65 [mask-image:linear-gradient(to_bottom,black,transparent)]" />
      <section className="relative mx-auto max-w-6xl px-4 pb-10 pt-12 sm:px-6 sm:pt-16">
        <div className="fade-up text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-white/80 px-3.5 py-1.5 text-xs font-bold text-blue-700 shadow-sm">
            <Sparkles size={14} />
            欢迎使用轻办公工具箱
          </span>
          <h1 className="mx-auto mt-5 max-w-3xl text-4xl font-black tracking-[-0.045em] text-slate-950 sm:text-5xl">
            今天想处理什么？
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-sm leading-7 text-slate-600 sm:text-base">
            先选择一个具体功能，再进入对应工作台。
            参数已经为你简化，按页面提示操作即可。
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-[11px] text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck size={13} className="text-emerald-600" />
              免登录
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Sparkles size={13} className="text-blue-600" />
              {demoMode ? "数据仅作演示" : "文件仅临时保存"}
            </span>
            <span>支持 xlsx / xls / csv</span>
          </div>
        </div>
      </section>

      <section className="relative mx-auto max-w-6xl px-4 pb-16 sm:px-6 sm:pb-24">
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <p className="text-[10px] font-black tracking-[0.2em] text-blue-600">SPREADSHEET</p>
            <h2 className="mt-1 text-xl font-black tracking-tight text-slate-950">表格处理</h2>
          </div>
          <p className="hidden text-xs text-slate-500 sm:block">拆分与合并，进入后先上传文件</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {spreadsheetActions.map((action) => (
            <ToolCard key={action.title} action={action} />
          ))}
        </div>

        <div className="mb-4 mt-9 flex items-end justify-between gap-4">
          <div>
            <p className="text-[10px] font-black tracking-[0.2em] text-blue-600">QR & MAC</p>
            <h2 className="mt-1 text-xl font-black tracking-tight text-slate-950">
              二维码与 MAC
            </h2>
          </div>
          <p className="hidden text-xs text-slate-500 sm:block">生成、识别或转换地址格式</p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {qrActions.map((action) => (
            <ToolCard key={action.title} action={action} compact />
          ))}
        </div>

        <div className="mt-8 flex flex-col gap-3 rounded-2xl border border-slate-200/80 bg-white/60 px-4 py-4 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <span className="inline-flex items-center gap-2">
            <ShieldCheck size={15} className="text-emerald-600" />
            {demoMode
              ? "当前为演示模式，不会上传或保存真实文件"
              : "已连接真实处理服务，文件将在 30 分钟后自动删除"}
          </span>
          <span>
            {demoMode ? "界面与流程用于评审，后续可切换真实后端" : "不建立处理历史，也不长期保存文件"}
          </span>
        </div>
      </section>
    </div>
  );
}

