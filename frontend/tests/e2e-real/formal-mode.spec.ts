import { readFile } from "node:fs/promises";

import { expect, test, type Page } from "@playwright/test";

async function inspectCsv(page: Page, files: { name: string; content: string }[]) {
  await page.locator('input[type="file"]').setInputFiles(
    files.map((file) => ({
      name: file.name,
      mimeType: "text/csv",
      buffer: Buffer.from(file.content, "utf8"),
    })),
  );
  await page.getByRole("button", { name: "读取工作表" }).click();
  await expect(page.getByRole("heading", { name: "选择工作表" })).toBeVisible();
}

async function expectZipDownload(page: Page) {
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载结果" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.zip$/);
  const path = await download.path();
  expect(path).not.toBeNull();
  const content = await readFile(path!);
  expect(content.subarray(0, 2).toString()).toBe("PK");
}

test("真实模式展示真实服务状态且不显示演示横幅", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("演示模式 · 数据为模拟")).toHaveCount(0);
  await expect(page.getByText("已连接真实处理服务")).toBeVisible();
});

test("真实模式下载过期结果时显示中文错误", async ({ page }) => {
  await page.goto("/excel");
  await inspectCsv(page, [
    { name: "真实模式.csv", content: "地区,金额\n华东,100\n华南,200\n" },
  ]);
  await page.getByRole("button", { name: /按行数/ }).click();
  await page.getByRole("spinbutton").fill("1");
  await page.getByRole("button", { name: "开始拆分" }).click();
  await expect(page.getByRole("heading", { name: "拆分完成" })).toBeVisible();

  await page.route("**/api/v1/results/*", async (route) => {
    await route.fulfill({
      status: 410,
      contentType: "application/json",
      body: JSON.stringify({
        success: false,
        data: null,
        error: {
          code: "RESULT_EXPIRED",
          message: "下载结果已过期，请重新处理",
        },
        request_id: "test-request",
      }),
    });
  });

  await page.getByRole("button", { name: "下载结果" }).click();
  await expect(page.getByText("下载结果已过期，请重新处理")).toBeVisible();
});

test("真实模式完成按工作表和按列拆分并下载 ZIP", async ({ page }) => {
  await page.goto("/excel");
  await inspectCsv(page, [
    { name: "销售明细.csv", content: "地区,金额\n华东,100\n华南,200\n华东,300\n" },
  ]);

  await page.getByRole("button", { name: "开始拆分" }).click();
  await expect(page.getByRole("heading", { name: "拆分完成" })).toBeVisible();
  await expectZipDownload(page);

  await page.getByRole("button", { name: "继续调整" }).click();
  await page.getByRole("button", { name: /按列值/ }).click();
  await page.getByRole("button", { name: "开始拆分" }).click();
  await expect(page.getByRole("heading", { name: "拆分完成" })).toBeVisible();
  await expectZipDownload(page);
});

test("真实模式合并多个 CSV 并下载 XLSX", async ({ page }) => {
  await page.goto("/excel?mode=merge");
  await inspectCsv(page, [
    { name: "一月.csv", content: "地区,金额\n华东,100\n" },
    { name: "二月.csv", content: "地区,金额\n华南,200\n" },
  ]);

  await page.getByRole("button", { name: "开始合并" }).click();
  await expect(page.getByRole("heading", { name: "合并完成" })).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载结果" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
  const path = await download.path();
  expect(path).not.toBeNull();
  const content = await readFile(path!);
  expect(content.subarray(0, 2).toString()).toBe("PK");
});

test("真实模式生成二维码后可下载并重新解析", async ({ page }) => {
  const text = "真实链路二维码 https://example.com/real";
  await page.goto("/qrcode");
  await page.getByRole("textbox").fill(text);
  await page.getByRole("button", { name: "立即生成" }).click();
  await expect(page.getByAltText("生成的二维码")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "下载 PNG" }).click();
  const download = await downloadPromise;
  const path = await download.path();
  expect(path).not.toBeNull();
  const qrImage = await readFile(path!);

  await page.getByRole("button", { name: "图片解析" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "real-qrcode.png",
    mimeType: "image/png",
    buffer: qrImage,
  });
  await page.getByRole("button", { name: "开始识别" }).click();
  await expect(page.getByText(text)).toBeVisible();
});

test("真实模式规范化 MAC 并生成二维码", async ({ page }) => {
  await page.goto("/qrcode?tab=mac");
  await page.getByLabel("已有 MAC 地址").fill("aa-bb-cc-dd-ee-ff");
  await expect(page.getByText("AA:BB:CC:DD:EE:FF").first()).toBeVisible();
  await page.getByRole("button", { name: "生成 MAC 二维码" }).click();
  await expect(page.getByAltText("MAC 地址二维码")).toBeVisible();
});
