import type { Metadata } from "next";

import { QrCodeTools } from "./qrcode-tools";

export const metadata: Metadata = {
  title: "二维码 / MAC 工具",
  description: "在线生成自定义尺寸二维码、解析图片二维码，并识别和规范化 MAC 地址。",
};

export default function QrCodePage() {
  return <QrCodeTools />;
}

