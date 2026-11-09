import { expect, test } from "@playwright/test";

test("真实模式展示真实服务状态且不显示演示横幅", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("演示模式 · 数据为模拟")).toHaveCount(0);
  await expect(page.getByText("已连接真实处理服务")).toBeVisible();
});

test("真实模式下载过期结果时显示中文错误", async ({ page }) => {
  await page.goto("/excel");
  await page.locator('input[type="file"]').setInputFiles({
    name: "真实模式.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("地区,金额\n华东,100\n华南,200\n", "utf8"),
  });
  await page.getByRole("button", { name: "读取工作表" }).click();
  await expect(page.getByRole("heading", { name: "选择工作表" })).toBeVisible();
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
