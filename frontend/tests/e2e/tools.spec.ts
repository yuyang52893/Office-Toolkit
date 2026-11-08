import { expect, test } from "@playwright/test";

const demoPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z4wAAAABJRU5ErkJggg==",
  "base64",
);

test.beforeEach(({ page }) => {
  page.on("pageerror", (error) => {
    console.error("[browser page error]", error);
  });
});

test("首页明确展示欢迎语和五个功能入口", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("演示模式 · 数据为模拟")).toBeVisible();
  await expect(page.getByRole("heading", { name: "今天想处理什么？" })).toBeVisible();
  await expect(page.getByRole("link", { name: /拆分 Excel \/ CSV/ })).toHaveAttribute(
    "href",
    "/excel?mode=by_sheet",
  );
  await expect(page.getByRole("link", { name: /合并多个表格/ })).toHaveAttribute(
    "href",
    "/excel?mode=merge",
  );
  await expect(page.getByRole("link", { name: /生成二维码/ })).toHaveAttribute(
    "href",
    "/qrcode?tab=generate",
  );
  await expect(page.getByRole("link", { name: /解析二维码图片/ })).toHaveAttribute(
    "href",
    "/qrcode?tab=decode",
  );
  await expect(page.getByRole("link", { name: /制作 MAC 地址二维码/ })).toHaveAttribute(
    "href",
    "/qrcode?tab=mac",
  );
  await expect(page.getByRole("link", { name: "功能选择" })).toBeVisible();
});

test("首页入口会预选对应处理模式", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: /合并多个表格/ }).click();
  await expect(page).toHaveURL(/\/excel\?mode=merge$/);
  await expect(page.getByRole("link", { name: "返回功能选择" })).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles({
    name: "合并数据.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("地区,金额\n华东,100\n华南,200\n", "utf8"),
  });
  await page.getByRole("button", { name: "读取工作表" }).click();
  await expect(page.getByRole("button", { name: /^合并数据/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  await page.goto("/");
  await page.getByRole("link", { name: /制作 MAC 地址二维码/ }).click();
  await expect(page).toHaveURL(/\/qrcode\?tab=mac$/);
  await expect(page.getByRole("heading", { name: "MAC 地址工具" })).toBeVisible();
});

test("Excel/CSV 按行数拆分并下载 ZIP", async ({ page }) => {
  await page.goto("/excel");
  const csv = Buffer.from(
    "地区,金额,备注\n华东,100,A\n华南,200,B\n华东,300,C\n西南,400,D\n",
    "utf8",
  );
  await page.locator('input[type="file"]').setInputFiles({
    name: "销售数据.csv",
    mimeType: "text/csv",
    buffer: csv,
  });
  await page.getByRole("button", { name: "读取工作表" }).click();
  await expect(page.getByRole("heading", { name: "选择工作表" })).toBeVisible();
  await expect(page.getByText("销售数据.csv").last()).toBeVisible();

  await page.getByRole("button", { name: /按行数/ }).click();
  await page.getByRole("spinbutton").fill("2");
  await page.getByRole("button", { name: "开始拆分" }).click();
  await expect(page.getByRole("heading", { name: "拆分完成" })).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "下载演示结果" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^演示结果说明_.*\.txt$/);
});

test("二维码生成并下载 PNG", async ({ page }) => {
  await page.goto("/qrcode");
  await page.getByRole("textbox").fill("轻办公工具箱 https://example.com");
  await page.getByRole("button", { name: "立即生成" }).click();
  await expect(page.getByAltText("生成的二维码")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "下载 PNG" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("qrcode-512.png");
});

test("上传二维码图片并解析 MAC 地址", async ({ page }) => {
  await page.goto("/qrcode");
  await page.getByRole("button", { name: "图片解析" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "demo-code.png",
    mimeType: "image/png",
    buffer: demoPng,
  });
  await page.getByRole("button", { name: "开始识别" }).click();
  await expect(page.getByText("轻办公工具箱演示内容").first()).toBeVisible();
});

test("MAC 页签规范化已有地址并生成二维码", async ({ page }) => {
  await page.goto("/qrcode");
  await page.getByRole("button", { name: "MAC 地址", exact: true }).click();
  await page.getByLabel("已有 MAC 地址").fill("aa-bb-cc-dd-ee-ff");
  await expect(page.getByText("AA:BB:CC:DD:EE:FF").first()).toBeVisible();
  await page.getByRole("button", { name: "生成 MAC 二维码" }).click();
  await expect(page.getByAltText("MAC 地址二维码")).toBeVisible();
});

