import type { Metadata } from "next";

import { QrCodeTools } from "./qrcode-tools";

export const metadata: Metadata = {
  title: "二维码 / MAC 工具",
  description: "在线生成自定义尺寸二维码、解析图片二维码，并识别和规范化 MAC 地址。",
};

const validTabs = ["generate", "decode", "mac"] as const;
type QrTab = (typeof validTabs)[number];

export default async function QrCodePage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string | string[] }>;
}) {
  const requestedTab = (await searchParams).tab;
  const tab = Array.isArray(requestedTab) ? requestedTab[0] : requestedTab;
  const initialTab = validTabs.includes(tab as QrTab) ? (tab as QrTab) : "generate";
  return <QrCodeTools initialTab={initialTab} />;
}

