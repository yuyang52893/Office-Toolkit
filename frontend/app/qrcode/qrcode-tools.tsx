"use client";

import {
  ArrowRight,
  Check,
  Copy,
  Download,
  Image as ImageIcon,
  Loader2,
  LockKeyhole,
  Network,
  QrCode,
  ScanLine,
  Sparkles,
  UploadCloud,
  X,
} from "lucide-react";
import Image from "next/image";
import type { ChangeEvent, DragEvent, KeyboardEvent } from "react";
import { useEffect, useRef, useState } from "react";

import { StatusBanner } from "@/components/status-banner";
import { BackToTools } from "@/components/back-to-tools";
import { decodeQrCode, generateQrCode } from "@/lib/api";
import { formatBytes, getErrorMessage } from "@/lib/format";
import type { QrDecodedItem } from "@/lib/types";
import { MacAddressTool } from "./mac-address-tool";

type Tab = "generate" | "decode" | "mac";

export function QrCodeTools({ initialTab = "generate" }: { initialTab?: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [content, setContent] = useState("https://example.com");
  const [size, setSize] = useState(512);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const previewUrlRef = useRef("");

  const [decodeFile, setDecodeFile] = useState<File | null>(null);
  const [decodePreviewUrl, setDecodePreviewUrl] = useState("");
  const [decoding, setDecoding] = useState(false);
  const [decodeError, setDecodeError] = useState("");
  const [decodedItems, setDecodedItems] = useState<QrDecodedItem[]>([]);
  const [copied, setCopied] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const decodeInputRef = useRef<HTMLInputElement>(null);
  const decodePreviewRef = useRef("");
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
      if (decodePreviewRef.current) {
        URL.revokeObjectURL(decodePreviewRef.current);
      }
      if (copyTimerRef.current) {
        clearTimeout(copyTimerRef.current);
      }
    };
  }, []);

  function replacePreview(blob: Blob | null) {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
    }
    const next = blob ? URL.createObjectURL(blob) : "";
    previewUrlRef.current = next;
    setPreviewUrl(next);
  }

  function markGenerateDirty() {
    setGenerateError("");
    replacePreview(null);
  }

  async function handleGenerate() {
    if (!content.trim()) {
      setGenerateError("请输入二维码内容");
      return;
    }
    setGenerating(true);
    setGenerateError("");
    try {
      const { blob } = await generateQrCode(content, size, "text");
      replacePreview(blob);
    } catch (error) {
      replacePreview(null);
      setGenerateError(getErrorMessage(error));
    } finally {
      setGenerating(false);
    }
  }

  function acceptDecodeFile(file: File) {
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      setDecodeError("仅支持 PNG、JPEG 和 WebP 图片");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setDecodeError("图片不能超过 10MB");
      return;
    }
    if (decodePreviewRef.current) {
      URL.revokeObjectURL(decodePreviewRef.current);
    }
    const nextUrl = URL.createObjectURL(file);
    decodePreviewRef.current = nextUrl;
    setDecodePreviewUrl(nextUrl);
    setDecodeFile(file);
    setDecodedItems([]);
    setDecodeError("");
  }

  function handleDecodeInput(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      acceptDecodeFile(file);
    }
    event.target.value = "";
  }

  function handleDecodeDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) {
      acceptDecodeFile(file);
    }
  }

  function handleDecodeKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      decodeInputRef.current?.click();
    }
  }

  async function handleDecode() {
    if (!decodeFile) {
      setDecodeError("请先选择包含二维码的图片");
      return;
    }
    setDecoding(true);
    setDecodeError("");
    try {
      const data = await decodeQrCode(decodeFile);
      setDecodedItems(data.items);
    } catch (error) {
      setDecodedItems([]);
      setDecodeError(getErrorMessage(error));
    } finally {
      setDecoding(false);
    }
  }

  function clearDecode() {
    if (decodePreviewRef.current) {
      URL.revokeObjectURL(decodePreviewRef.current);
    }
    decodePreviewRef.current = "";
    setDecodePreviewUrl("");
    setDecodeFile(null);
    setDecodedItems([]);
    setDecodeError("");
  }

  async function copyText(key: string, value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(key);
      if (copyTimerRef.current) {
        clearTimeout(copyTimerRef.current);
      }
      copyTimerRef.current = setTimeout(() => setCopied(""), 1600);
    } catch {
      setDecodeError("复制失败，请手动选择内容");
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="mb-5">
        <BackToTools />
      </div>
      <section className="fade-up mb-8">
        <div className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-blue-600">
          <QrCode size={15} />
          QR & MAC Studio
        </div>
        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
          <div>
            <h1 className="text-3xl font-black tracking-[-0.035em] text-slate-950 sm:text-4xl">
              二维码 / MAC 工具
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">
              输入文本生成自定义尺寸二维码，也可以上传截图识别内容。
              MAC 地址会自动校验并返回常见格式。
            </p>
          </div>
          <div className="flex gap-2 text-xs">
            <span className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 font-bold text-slate-500">
              PNG
            </span>
            <span className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 font-bold text-slate-500">
              JPG / WEBP
            </span>
            <span className="rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1.5 font-bold text-emerald-700">
              多码识别
            </span>
          </div>
        </div>
      </section>

      <div className="mb-5 inline-flex w-full rounded-xl border border-slate-200 bg-white p-1 shadow-sm sm:w-auto">
        <button
          type="button"
          onClick={() => setTab("generate")}
          className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-bold transition sm:flex-none ${
            tab === "generate" ? "bg-slate-950 text-white shadow-sm" : "text-slate-600 hover:bg-slate-50"
          }`}
        >
          <QrCode size={16} />
          生成二维码
        </button>
        <button
          type="button"
          onClick={() => setTab("decode")}
          className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-bold transition sm:flex-none ${
            tab === "decode" ? "bg-slate-950 text-white shadow-sm" : "text-slate-600 hover:bg-slate-50"
          }`}
        >
          <ScanLine size={16} />
          图片解析
        </button>
        <button
          type="button"
          onClick={() => setTab("mac")}
          className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-bold transition sm:flex-none ${
            tab === "mac" ? "bg-slate-950 text-white shadow-sm" : "text-slate-600 hover:bg-slate-50"
          }`}
        >
          <Network size={16} />
          MAC 地址
        </button>
      </div>

      {tab === "generate" ? (
        <div className="grid gap-5 lg:grid-cols-[1.08fr_0.92fr]">
          <section className="surface-card fade-up rounded-2xl p-5 sm:p-7">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-black tracking-tight text-slate-950">二维码内容</h2>
                <p className="mt-1 text-xs text-slate-500">普通文本、网址或任意短文本</p>
              </div>
              <Sparkles size={19} className="text-blue-500" />
            </div>

            <label className="block">
              <span className="text-sm font-semibold text-slate-800">内容</span>
              <textarea
                value={content}
                onChange={(event) => {
                  setContent(event.target.value);
                  markGenerateDirty();
                }}
                placeholder="输入网址、文本或其他二维码内容"
                rows={6}
                maxLength={2000}
                className="mt-2 w-full resize-y rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
              <span className="mt-1.5 block text-right text-[10px] text-slate-400">
                {content.length} / 2000
              </span>
            </label>

            <div className="mt-5">
              <div className="flex items-center justify-between">
                <label htmlFor="qr-size" className="text-sm font-semibold text-slate-800">
                  图片尺寸
                </label>
                <span className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">
                  {size} × {size} px
                </span>
              </div>
              <div className="mt-3 grid grid-cols-[1fr_92px] items-center gap-4">
                <input
                  id="qr-size"
                  type="range"
                  min={128}
                  max={2048}
                  step={32}
                  value={size}
                  onChange={(event) => {
                    setSize(Number(event.target.value));
                    markGenerateDirty();
                  }}
                  className="accent-blue-600"
                />
                <input
                  type="number"
                  min={128}
                  max={2048}
                  value={size}
                  onChange={(event) => {
                    const next = Number(event.target.value);
                    setSize(Number.isFinite(next) ? Math.min(2048, Math.max(128, next)) : 512);
                    markGenerateDirty();
                  }}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-center text-sm font-bold text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  aria-label="二维码尺寸像素"
                />
              </div>
            </div>

            <button
              type="button"
              onClick={handleGenerate}
              disabled={generating}
              className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-blue-600/15 transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {generating ? <Loader2 size={17} className="animate-spin" /> : <QrCode size={17} />}
              {generating ? "正在生成…" : "立即生成"}
              {!generating ? <ArrowRight size={16} /> : null}
            </button>

            {generateError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{generateError}</StatusBanner>
              </div>
            ) : null}
          </section>

          <section className="surface-card fade-up rounded-2xl p-5 sm:p-7" style={{ animationDelay: "70ms" }}>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-black tracking-tight text-slate-950">预览与下载</h2>
                <p className="mt-1 text-xs text-slate-500">PNG · 黑白 · 中等容错</p>
              </div>
              <span className="grid size-9 place-items-center rounded-xl bg-blue-50 text-blue-600">
                <ImageIcon size={17} />
              </span>
            </div>

            <div className="mt-6 grid min-h-72 place-items-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-6">
              {previewUrl ? (
                <div className="rounded-2xl bg-white p-4 shadow-lg shadow-slate-900/8 ring-1 ring-slate-200">
                  <Image
                    src={previewUrl}
                    alt="生成的二维码"
                    width={512}
                    height={512}
                    unoptimized
                    className="size-56 rounded-lg object-contain sm:size-64"
                  />
                </div>
              ) : (
                <div className="text-center">
                  <span className="mx-auto grid size-20 place-items-center rounded-2xl bg-white text-slate-300 shadow-sm ring-1 ring-slate-200">
                    <QrCode size={44} strokeWidth={1.5} />
                  </span>
                  <p className="mt-4 text-sm font-semibold text-slate-500">生成后在这里预览</p>
                  <p className="mt-1 text-xs text-slate-400">尺寸会按输入像素精确输出</p>
                </div>
              )}
            </div>

            <a
              href={previewUrl || undefined}
              download={`qrcode-${size}.png`}
              aria-disabled={!previewUrl}
              className={`mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-bold transition ${
                previewUrl
                  ? "bg-slate-950 text-white hover:bg-slate-800"
                  : "pointer-events-none bg-slate-100 text-slate-400"
              }`}
            >
              <Download size={16} />
              下载 PNG
            </a>
          </section>
        </div>
      ) : tab === "decode" ? (
        <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
          <section className="surface-card fade-up rounded-2xl p-5 sm:p-7">
            <div className="mb-5">
              <h2 className="text-lg font-black tracking-tight text-slate-950">上传二维码图片</h2>
              <p className="mt-1 text-xs text-slate-500">支持 PNG、JPEG、WebP，最大 10MB</p>
            </div>
            <input
              ref={decodeInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="sr-only"
              onChange={handleDecodeInput}
            />
            <div
              role="button"
              tabIndex={0}
              aria-label="选择二维码图片"
              onClick={() => decodeInputRef.current?.click()}
              onKeyDown={handleDecodeKeyDown}
              onDragOver={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDecodeDrop}
              className={`relative grid min-h-64 place-items-center overflow-hidden rounded-2xl border-2 border-dashed p-5 text-center transition ${
                isDragging
                  ? "border-blue-500 bg-blue-50"
                  : "border-slate-200 bg-slate-50/70 hover:border-blue-300 hover:bg-blue-50/40"
              }`}
            >
              {decodePreviewUrl ? (
                <>
                  <Image
                    src={decodePreviewUrl}
                    alt="待解析的二维码图片"
                    width={640}
                    height={420}
                    unoptimized
                    className="max-h-64 w-auto rounded-xl object-contain shadow-sm"
                  />
                  <button
                    type="button"
                    aria-label="移除图片"
                    onClick={(event) => {
                      event.stopPropagation();
                      clearDecode();
                    }}
                    className="absolute right-3 top-3 grid size-8 place-items-center rounded-lg bg-white text-slate-500 shadow-md transition hover:text-red-600"
                  >
                    <X size={16} />
                  </button>
                </>
              ) : (
                <div>
                  <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-white text-blue-600 shadow-sm ring-1 ring-slate-200">
                    <UploadCloud size={25} />
                  </span>
                  <p className="mt-4 text-sm font-bold text-slate-800">拖拽二维码图片到这里</p>
                  <p className="mt-1 text-xs text-slate-500">或点击选择文件</p>
                </div>
              )}
            </div>

            {decodeFile ? (
              <div className="mt-3 flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3.5 py-3">
                <span className="grid size-9 place-items-center rounded-lg bg-blue-50 text-blue-600">
                  <ImageIcon size={16} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-800">{decodeFile.name}</p>
                  <p className="text-[11px] text-slate-400">{formatBytes(decodeFile.size)}</p>
                </div>
              </div>
            ) : null}

            <button
              type="button"
              onClick={handleDecode}
              disabled={decoding || !decodeFile}
              className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-blue-600/15 transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-45"
            >
              {decoding ? <Loader2 size={17} className="animate-spin" /> : <ScanLine size={17} />}
              {decoding ? "正在识别…" : "开始识别"}
            </button>

            {decodeError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{decodeError}</StatusBanner>
              </div>
            ) : null}
          </section>

          <section className="surface-card fade-up rounded-2xl p-5 sm:p-7" style={{ animationDelay: "70ms" }}>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-black tracking-tight text-slate-950">识别结果</h2>
                <p className="mt-1 text-xs text-slate-500">
                  {decodedItems.length > 0
                    ? `找到 ${decodedItems.length} 个不同二维码`
                    : "识别后会展示图片中的全部二维码"}
                </p>
              </div>
              <span className="grid size-9 place-items-center rounded-xl bg-blue-50 text-blue-600">
                <ScanLine size={17} />
              </span>
            </div>

            {decodedItems.length === 0 ? (
              <div className="mt-6 grid min-h-72 place-items-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-6 text-center">
                <div>
                  <span className="mx-auto grid size-16 place-items-center rounded-2xl bg-white text-slate-300 shadow-sm ring-1 ring-slate-200">
                    <ScanLine size={32} strokeWidth={1.5} />
                  </span>
                  <p className="mt-4 text-sm font-semibold text-slate-500">等待识别</p>
                  <p className="mt-1 text-xs text-slate-400">多码图片会按内容去重后全部展示</p>
                </div>
              </div>
            ) : (
              <div className="mt-5 space-y-3">
                {decodedItems.map((item, index) => (
                  <article
                    key={`${item.text}-${index}`}
                    className="rounded-xl border border-slate-200 bg-white p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <span
                          className={`inline-flex rounded-md px-2 py-1 text-[10px] font-black uppercase tracking-wide ${
                            item.kind === "mac"
                              ? "bg-blue-50 text-blue-700"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {item.kind === "mac" ? "MAC 地址" : "二维码文本"}
                        </span>
                        <p className="mt-2 break-all text-sm font-semibold leading-6 text-slate-800">
                          {item.text}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => copyText(`main-${index}`, item.text)}
                        className="grid size-8 shrink-0 place-items-center rounded-lg border border-slate-200 text-slate-400 transition hover:border-blue-200 hover:text-blue-600"
                        aria-label="复制内容"
                      >
                        {copied === `main-${index}` ? <Check size={15} /> : <Copy size={15} />}
                      </button>
                    </div>

                    {item.mac ? (
                      <div className="mt-4 grid gap-2 sm:grid-cols-2">
                        {[
                          ["冒号格式", item.mac.canonical],
                          ["连字符格式", item.mac.hyphenated],
                          ["纯十六进制", item.mac.plain],
                          ["Cisco 格式", item.mac.cisco],
                        ].map(([label, value]) => (
                          <button
                            key={label}
                            type="button"
                            onClick={() => copyText(`${index}-${label}`, value)}
                            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-left transition hover:border-blue-200 hover:bg-blue-50"
                          >
                            <span className="block text-[10px] font-semibold text-slate-500">
                              {label}
                            </span>
                            <span className="mt-0.5 block truncate font-mono text-xs font-bold text-slate-700">
                              {value}
                            </span>
                          </button>
                        ))}
                        <div className="sm:col-span-2 flex flex-wrap gap-2 text-[10px] font-semibold text-slate-500">
                          <span className="rounded-md bg-slate-100 px-2 py-1">
                            {item.mac.multicast ? "组播地址" : "单播地址"}
                          </span>
                          <span className="rounded-md bg-slate-100 px-2 py-1">
                            {item.mac.locally_administered ? "本地管理" : "全局管理"}
                          </span>
                        </div>
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            )}

            <div className="mt-5 flex items-start gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-[11px] leading-5 text-slate-500">
              <LockKeyhole size={14} className="mt-0.5 shrink-0" />
              图片仅用于本次识别，不会长期保存。
            </div>
          </section>
        </div>
      ) : (
        <MacAddressTool />
      )}
    </div>
  );
}

