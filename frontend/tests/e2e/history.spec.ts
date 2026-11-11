import { expect, test, type Page } from "@playwright/test";

const user = {
  id: 1,
  username: "00123456",
  role: "user",
  is_active: true,
  must_change_password: false,
  created_at: "2026-11-10T00:00:00Z",
  last_login_at: null,
};

const historyItems = [
  {
    id: "active-1",
    tool: "excel_split",
    operation: "by_rows",
    result_filename: "拆分结果.zip",
    size_bytes: 1024,
    summary: { output_count: 2 },
    status: "active",
    completed_at: "2026-11-10T01:00:00Z",
    expires_at: "2026-11-10T01:30:00Z",
    expired_at: null,
    expire_reason: null,
    purge_after: null,
  },
  {
    id: "expired-1",
    tool: "qrcode",
    operation: "generate",
    result_filename: "旧二维码.png",
    size_bytes: 2048,
    summary: { size: 512 },
    status: "expired",
    completed_at: "2026-11-10T00:00:00Z",
    expires_at: "2026-11-10T00:30:00Z",
    expired_at: "2026-11-10T00:35:00Z",
    expire_reason: "timeout",
    purge_after: "2026-11-10T03:35:00Z",
  },
];

async function mockAuthenticatedHistory(page: Page) {
  await page.addInitScript(() => {
    sessionStorage.setItem("office_tools_access_token", "history-token");
  });
  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        data: user,
        error: null,
        request_id: "auth-request",
      }),
    });
  });
  await page.route("**/api/v1/history", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        data: { items: historyItems },
        error: null,
        request_id: "history-request",
      }),
    });
  });
}

test("历史列表区分可下载和已过期文件", async ({ page }) => {
  await mockAuthenticatedHistory(page);
  await page.goto("/history");

  await expect(page.getByRole("heading", { name: "个人处理历史" })).toBeVisible();
  await expect(page.getByText("拆分结果.zip")).toBeVisible();
  await expect(page.getByRole("link", { name: "下载结果" })).toBeVisible();
  await expect(page.getByText("旧二维码.png")).toBeVisible();
  await expect(page.getByText("已过期", { exact: true })).toBeVisible();
  await expect(page.getByText("30 分钟已到期")).toBeVisible();
  await expect(page.getByRole("link", { name: "下载结果" })).toHaveCount(1);
});

test("无 Token 访问个人历史会跳转登录", async ({ page }) => {
  await page.goto("/history");

  await expect(page).toHaveURL(/\/login\?next=%2Fhistory$/);
  await expect(page.getByText("此功能仅登录用户可用")).toBeVisible();
});

test("下载已过期文件时显示明确提示", async ({ page }) => {
  await mockAuthenticatedHistory(page);
  await page.route("**/api/v1/history/active-1/download", async (route) => {
    await route.fulfill({
      status: 410,
      contentType: "application/json",
      body: JSON.stringify({
        success: false,
        data: null,
        error: { code: "HISTORY_EXPIRED", message: "文件已过期" },
        request_id: "expired-request",
      }),
    });
  });
  await page.goto("/history");
  await page.getByRole("link", { name: "下载结果" }).click();

  await expect(page.getByText("文件已过期，请重新处理")).toBeVisible();
});

test("下载无权限文件时显示无权限提示", async ({ page }) => {
  await mockAuthenticatedHistory(page);
  await page.route("**/api/v1/history/active-1/download", async (route) => {
    await route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({
        success: false,
        data: null,
        error: { code: "FORBIDDEN", message: "没有权限" },
        request_id: "forbidden-request",
      }),
    });
  });
  await page.goto("/history");
  await page.getByRole("link", { name: "下载结果" }).click();

  await expect(page.getByText("没有权限下载该文件")).toBeVisible();
});
