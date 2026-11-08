import {
  ArrowRight,
  Check,
  Columns3,
  FileSpreadsheet,
  Files,
  Layers3,
  QrCode,
  Rows3,
  ScanLine,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

const excelFeatures = [
  { icon: Layers3, label: "按工作表拆分" },
  { icon: Rows3, label: "按行数拆分" },
  { icon: Columns3, label: "按列值拆分" },
  { icon: Files, label: "多表合并" },
];

export default function HomePage() {
  return (
    <>
      <section className="relative overflow-hidden">
        <div className="subtle-grid absolute inset-0 opacity-70 [mask-image:linear-gradient(to_bottom,black,transparent_82%)]" />
        <div className="relative mx-auto grid max-w-6xl gap-12 px-4 pb-20 pt-16 sm:px-6 sm:pt-24 lg:grid-cols-[1.08fr_0.92fr] lg:items-center lg:pb-28">
          <div className="fade-up">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50/80 px-3 py-1.5 text-xs font-semibold text-blue-700">
              <Sparkles size={14} />
              免登录 · 文件自动清理
            </div>
            <h1 className="max-w-2xl text-4xl font-black leading-[1.13] tracking-[-0.045em] text-slate-950 sm:text-6xl">
              把繁琐的表格，
              <span className="relative mx-2 inline-block text-blue-600">
                变成几步操作
                <span className="absolute -bottom-1 left-0 h-2 w-full rounded-full bg-blue-100/90" />
              </span>
            </h1>
            <p className="mt-6 max-w-xl text-base leading-8 text-slate-600 sm:text-lg">
              在线拆分、合并 Excel / XLS / CSV，生成和解析二维码。
              常用办公小工具集中在一个清爽页面里。
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/excel"
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-blue-600/20 transition hover:-translate-y-0.5 hover:bg-blue-700"
              >
                <FileSpreadsheet size={18} />
                处理表格
                <ArrowRight size={16} />
              </Link>
              <Link
                href="/qrcode"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-bold text-slate-700 shadow-sm transition hover:-translate-y-0.5 hover:border-blue-200 hover:text-blue-700"
              >
                <QrCode size={18} />
                二维码与 MAC
              </Link>
            </div>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <Check size={14} className="text-emerald-600" />
                支持 xlsx / xls / csv
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Check size={14} className="text-emerald-600" />
                批量处理
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Check size={14} className="text-emerald-600" />
                30 分钟自动删除
              </span>
            </div>
          </div>

          <div className="fade-up relative mx-auto w-full max-w-lg lg:mx-0" style={{ animationDelay: "80ms" }}>
            <div className="absolute -left-5 top-16 size-24 rounded-full bg-blue-300/25 blur-2xl" />
            <div className="absolute -right-3 bottom-4 size-32 rounded-full bg-cyan-300/20 blur-3xl" />
            <div className="surface-card relative rotate-[1.4deg] rounded-[28px] p-5 sm:p-7">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-600">
                    Excel Split
                  </p>
                  <p className="mt-1 text-lg font-bold text-slate-900">销售数据.xlsx</p>
                </div>
                <span className="rounded-lg bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700">
                  处理完成
                </span>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-11 place-items-center rounded-xl bg-emerald-100 text-emerald-700">
                    <FileSpreadsheet size={22} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-4 text-xs font-semibold text-slate-700">
                      <span>销售数据_拆分结果.zip</span>
                      <span className="text-slate-400">6 个文件</span>
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
                      <div className="h-full w-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-400" />
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3">
                {["华东区.xlsx", "华南区.xlsx", "华北区.xlsx", "西南区.xlsx"].map(
                  (name, index) => (
                    <div
                      key={name}
                      className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 text-xs font-semibold text-slate-600"
                      style={{ transform: `translateY(${index % 2 ? 5 : 0}px)` }}
                    >
                      <span className="grid size-7 place-items-center rounded-lg bg-blue-50 text-blue-600">
                        <FileSpreadsheet size={14} />
                      </span>
                      {name}
                    </div>
                  ),
                )}
              </div>
              <div className="mt-4 flex items-center justify-between rounded-xl bg-slate-950 px-4 py-3 text-xs text-slate-300">
                <span className="inline-flex items-center gap-2">
                  <ShieldCheck size={15} className="text-emerald-400" />
                  临时文件将在 29:42 后清理
                </span>
                <span className="font-bold text-white">下载 ZIP</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-20 sm:px-6 sm:pb-28">
        <div className="mb-8 flex items-end justify-between gap-5">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-600">
              Tools
            </p>
            <h2 className="mt-2 text-2xl font-black tracking-tight text-slate-950 sm:text-3xl">
              选择你要处理的内容
            </h2>
          </div>
          <p className="hidden max-w-sm text-right text-sm leading-6 text-slate-500 sm:block">
            一次上传，批量处理。结果保留 30 分钟，方便重复下载。
          </p>
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          <Link
            href="/excel"
            className="surface-card group relative overflow-hidden rounded-[26px] p-6 transition hover:-translate-y-1 hover:border-blue-200 sm:p-8"
          >
            <div className="absolute -right-14 -top-14 size-44 rounded-full bg-blue-100/60 transition group-hover:scale-110" />
            <div className="relative">
              <div className="flex items-start justify-between">
                <span className="grid size-14 place-items-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-600/20">
                  <FileSpreadsheet size={28} />
                </span>
                <span className="inline-flex items-center gap-1 text-sm font-bold text-blue-600">
                  进入工作台
                  <ArrowRight size={16} className="transition group-hover:translate-x-1" />
                </span>
              </div>
              <h3 className="mt-7 text-2xl font-black tracking-tight text-slate-950">
                Excel / CSV 工作台
              </h3>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                多 Sheet 拆分、按行数、按列值拆分，以及多文件数据合并。
                支持去除空行和重复行。
              </p>
              <div className="mt-6 grid grid-cols-2 gap-2">
                {excelFeatures.map(({ icon: Icon, label }) => (
                  <span
                    key={label}
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200/80 bg-slate-50/80 px-3 py-2.5 text-xs font-semibold text-slate-600"
                  >
                    <Icon size={15} className="text-blue-600" />
                    {label}
                  </span>
                ))}
              </div>
            </div>
          </Link>

          <Link
            href="/qrcode"
            className="surface-card group relative overflow-hidden rounded-[26px] p-6 transition hover:-translate-y-1 hover:border-blue-200 sm:p-8"
          >
            <div className="absolute -right-14 -top-14 size-44 rounded-full bg-cyan-100/60 transition group-hover:scale-110" />
            <div className="relative">
              <div className="flex items-start justify-between">
                <span className="grid size-14 place-items-center rounded-2xl bg-slate-950 text-white shadow-lg shadow-slate-900/15">
                  <QrCode size={29} />
                </span>
                <span className="inline-flex items-center gap-1 text-sm font-bold text-blue-600">
                  开始使用
                  <ArrowRight size={16} className="transition group-hover:translate-x-1" />
                </span>
              </div>
              <h3 className="mt-7 text-2xl font-black tracking-tight text-slate-950">
                二维码 / MAC 工具
              </h3>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                文本转二维码、自定义尺寸、上传图片解析内容。
                MAC 地址支持常见格式识别与规范化。
              </p>
              <div className="mt-6 grid grid-cols-2 gap-2">
                <span className="inline-flex items-center gap-2 rounded-xl border border-slate-200/80 bg-slate-50/80 px-3 py-2.5 text-xs font-semibold text-slate-600">
                  <QrCode size={15} className="text-blue-600" />
                  生成 PNG
                </span>
                <span className="inline-flex items-center gap-2 rounded-xl border border-slate-200/80 bg-slate-50/80 px-3 py-2.5 text-xs font-semibold text-slate-600">
                  <ScanLine size={15} className="text-blue-600" />
                  图片识别
                </span>
                <span className="inline-flex items-center gap-2 rounded-xl border border-slate-200/80 bg-slate-50/80 px-3 py-2.5 text-xs font-semibold text-slate-600">
                  <Sparkles size={15} className="text-blue-600" />
                  MAC 规范化
                </span>
                <span className="inline-flex items-center gap-2 rounded-xl border border-slate-200/80 bg-slate-50/80 px-3 py-2.5 text-xs font-semibold text-slate-600">
                  <ShieldCheck size={15} className="text-blue-600" />
                  多码识别
                </span>
              </div>
            </div>
          </Link>
        </div>
      </section>
    </>
  );
}

