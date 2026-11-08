"use client";

import { Check, Copy, Download, Loader2, Network, ShieldCheck } from "lucide-react";
import Image from "next/image";
import { useEffect, useMemo, useRef, useState } from "react";

import { StatusBanner } from "@/components/status-banner";
import { generateQrCode } from "@/lib/api";
import { getErrorMessage } from "@/lib/format";
import { normalizeMac } from "@/lib/mac";

export function MacAddressTool() {
  const [value, setValue] = useState("AA:BB:CC:DD:EE:FF");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const [copied, setCopied] = useState("");
  const previewRef = useRef("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const normalized = useMemo(() => normalizeMac(value), [value]);

  useEffect(() => {
    return () => {
      if (previewRef.current) {
        URL.revokeObjectURL(previewRef.current);
      }
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  function updatePreview(blob: Blob | null) {
    if (previewRef.current) {
      URL.revokeObjectURL(previewRef.current);
    }
    const next = blob ? URL.createObjectURL(blob) : "";
    previewRef.current = next;
    setPreviewUrl(next);
  }

  async function generate() {
    if (!normalized) {
      setError("请输入合法的 12 位十六进制 MAC 地址");
      return;
    }
    setGenerating(true);
    setError("");
    try {
      const { blob } = await generateQrCode(value, 512, "mac");
      updatePreview(blob);
    } catch (generateError) {
      updatePreview(null);
      setError(getErrorMessage(generateError));
    } finally {
      setGenerating(false);
    }
  }

  async function copy(label: string, text: string) {
    await navigator.clipboard.writeText(text);
    setCopied(label);
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    timerRef.current = setTimeout(() => setCopied(""), 1500);
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
      <section className="surface-card fade-up rounded-2xl p-5 sm:p-7">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-black tracking-tight text-slate-950">MAC 地址工具</h2>
            <p className="mt-1 text-xs text-slate-500">把已有 MAC 地址规范化并制作成二维码</p>
          </div>
          <span className="grid size-10 place-items-center rounded-xl bg-blue-50 text-blue-600">
            <Network size={19} />
          </span>
        </div>

        <label className="block">
          <span className="text-sm font-semibold text-slate-800">已有 MAC 地址</span>
          <input
            value={value}
            onChange={(event) => {
              setValue(event.target.value);
              setError("");
            }}
            placeholder="例如 AA:BB:CC:DD:EE:FF"
            className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 font-mono text-base font-bold uppercase tracking-wide text-slate-800 outline-none transition placeholder:font-sans placeholder:font-normal placeholder:normal-case placeholder:tracking-normal focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          />
        </label>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          支持冒号、连字符、Cisco 点分和纯十六进制格式，不会随机生成 MAC 地址。
        </p>

        <div
          className={`mt-5 rounded-xl border p-4 transition ${
            normalized ? "border-emerald-200 bg-emerald-50/70" : "border-slate-200 bg-slate-50"
          }`}
        >
          <div className="flex items-center gap-2">
            <ShieldCheck
              size={16}
              className={normalized ? "text-emerald-600" : "text-slate-400"}
            />
            <span className="text-xs font-bold text-slate-700">
              {normalized ? "格式有效，已规范化" : "等待输入有效地址"}
            </span>
          </div>
          {normalized ? (
            <p className="mt-2 font-mono text-lg font-black tracking-wide text-slate-900">
              {normalized.canonical}
            </p>
          ) : (
            <p className="mt-2 text-xs text-slate-500">需要 12 位十六进制字符</p>
          )}
        </div>

        {normalized ? (
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {[
              ["冒号格式", normalized.canonical],
              ["连字符格式", normalized.hyphenated],
              ["纯十六进制", normalized.plain],
              ["Cisco 格式", normalized.cisco],
            ].map(([label, text]) => (
              <button
                key={label}
                type="button"
                onClick={() => copy(label, text)}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-left transition hover:border-blue-200 hover:bg-blue-50"
              >
                <span className="block text-[10px] font-semibold text-slate-500">{label}</span>
                <span className="mt-0.5 flex items-center justify-between gap-2 font-mono text-xs font-bold text-slate-700">
                  {text}
                  {copied === label ? <Check size={13} /> : <Copy size={13} className="text-slate-400" />}
                </span>
              </button>
            ))}
          </div>
        ) : null}

        <button
          type="button"
          onClick={generate}
          disabled={generating || !normalized}
          className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-blue-600/15 transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-45"
        >
          {generating ? <Loader2 size={17} className="animate-spin" /> : <Network size={17} />}
          {generating ? "正在生成…" : "生成 MAC 二维码"}
        </button>

        {error ? (
          <div className="mt-4">
            <StatusBanner tone="error">{error}</StatusBanner>
          </div>
        ) : null}
      </section>

      <section className="surface-card fade-up rounded-2xl p-5 sm:p-7">
        <h2 className="text-lg font-black tracking-tight text-slate-950">MAC 二维码预览</h2>
        <p className="mt-1 text-xs text-slate-500">生成内容统一使用冒号格式</p>
        <div className="mt-6 grid min-h-80 place-items-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-6">
          {previewUrl ? (
            <div className="rounded-2xl bg-white p-4 shadow-lg shadow-slate-900/10 ring-1 ring-slate-200">
              <Image
                src={previewUrl}
                alt="MAC 地址二维码"
                width={512}
                height={512}
                unoptimized
                className="size-56 rounded-lg object-contain sm:size-64"
              />
            </div>
          ) : (
            <div className="text-center">
              <span className="mx-auto grid size-20 place-items-center rounded-2xl bg-white text-slate-300 shadow-sm ring-1 ring-slate-200">
                <Network size={40} strokeWidth={1.5} />
              </span>
              <p className="mt-4 text-sm font-semibold text-slate-500">有效地址生成后在这里预览</p>
            </div>
          )}
        </div>
        <a
          href={previewUrl || undefined}
          download="mac-qrcode.png"
          aria-disabled={!previewUrl}
          className={`mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-bold transition ${
            previewUrl
              ? "bg-slate-950 text-white hover:bg-slate-800"
              : "pointer-events-none bg-slate-100 text-slate-400"
          }`}
        >
          <Download size={16} />
          下载 MAC 二维码
        </a>
      </section>
    </div>
  );
}

