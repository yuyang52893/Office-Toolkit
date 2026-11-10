import type { Metadata } from "next";
import type { ReactNode } from "react";
import { connection } from "next/server";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { DemoBanner } from "@/components/demo-banner";
import { AuthProvider } from "@/components/auth-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "轻办公工具箱 - Excel/CSV 与二维码工具",
    template: "%s | 轻办公工具箱",
  },
  description:
    "在线拆分合并 Excel、XLS、CSV，生成和解析二维码，转换 MAC 地址格式。免登录，文件自动清理。",
};

export default async function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  await connection();

  return (
    <html lang="zh-CN" data-scroll-behavior="smooth">
      <body>
        <AuthProvider>
          <div className="flex min-h-screen flex-col">
            <DemoBanner />
            <SiteHeader />
            <main className="flex-1">{children}</main>
            <SiteFooter />
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}

