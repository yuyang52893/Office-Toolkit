import { expect, test, type Page } from "@playwright/test";

const admin = {
  id: 1,
  username: "90000001",
  role: "admin" as const,
  is_active: true,
  must_change_password: false,
  created_at: "2026-11-10T00:00:00Z",
  last_login_at: "2026-11-10T01:00:00Z",
};

const user = {
  id: 2,
  username: "80000001",
  role: "user" as const,
  is_active: true,
  must_change_password: false,
  created_at: "2026-11-10T00:30:00Z",
  last_login_at: null,
};

function success(data: unknown, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify({
      success: true,
      data,
      error: null,
      request_id: "admin-e2e",
    }),
  };
}

async function mockAdminApi(page: Page, role: "admin" | "user" = "admin") {
  await page.addInitScript(() => {
    window.sessionStorage.setItem("office_tools_access_token", "admin-token");
  });
  let currentUser = structuredClone(role === "admin" ? admin : { ...user, role });

  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill(success(currentUser));
  });
  await page.route("**/api/v1/admin/users**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "GET" && path.endsWith("/admin/users")) {
      await route.fulfill(success({ items: [admin, user] }));
      return;
    }
    if (path.endsWith("/status")) {
      currentUser = { ...currentUser, ...user, is_active: false };
      await route.fulfill(success(currentUser));
      return;
    }
    if (path.endsWith("/role")) {
      await route.fulfill(success({ ...user, role: "admin" }));
      return;
    }
    if (path.endsWith("/logout")) {
      await route.fulfill(success(user));
      return;
    }
    if (path.endsWith("/reset-password")) {
      await route.fulfill(
        success({ temporary_password: "TempPass123", user: { ...user, must_change_password: true } }),
      );
      return;
    }
    await route.fulfill({ status: 404, body: "not mocked" });
  });
  await page.route("**/api/v1/admin/audit-logs/download*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/csv; charset=utf-8",
      headers: { "Content-Disposition": 'attachment; filename="audit-2026-11-10.csv"' },
      body: "\ufeffid,event\n1,admin.user.status.success\n",
    });
  });
  await page.route("**/api/v1/admin/audit-logs**", async (route) => {
    await route.fulfill(
      success({
        items: [
          {
            id: 1,
            request_id: "audit-request",
            event: "admin.user.status.success",
            outcome: "success",
            actor_user_id: 1,
            target_user_id: 2,
            actor_username: admin.username,
            target_username: user.username,
            ip: "127.0.0.1",
            details: { is_active: false },
            created_at: "2026-11-10T01:10:00",
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
      }),
    );
  });
  await page.route("**/api/v1/admin/runtime-errors/download*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/x-ndjson",
      headers: {
        "Content-Disposition": 'attachment; filename="runtime-errors-2026-11-10.jsonl"',
      },
      body: '{"level":"ERROR","message":"示例错误"}\n',
    });
  });
  await page.route("**/api/v1/admin/runtime-errors**", async (route) => {
    await route.fulfill(
      success({
        items: [{ level: "ERROR", logger: "app.test", message: "示例错误" }],
        total: 1,
        page: 1,
        page_size: 50,
        date: "2026-11-10",
      }),
    );
  });
}

test("管理员可以禁用用户并只显示一次临时密码", async ({ page }) => {
  await mockAdminApi(page);
  await page.goto("/admin/users");
  await expect(page.getByText(user.username)).toBeVisible();
  await expect(page.getByText(/password_hash|recovery_answer_hash/i)).toHaveCount(0);

  await page.getByRole("button", { name: "禁用账号" }).click();
  await expect(page.getByText("账号已禁用")).toBeVisible();
  await page.getByRole("button", { name: "重置密码" }).click();
  await expect(page.getByText("TempPass123")).toBeVisible();
  await page.getByRole("button", { name: "我已保存" }).click();
  await expect(page.getByText("TempPass123")).toHaveCount(0);
});

test("普通用户无法进入管理员页面", async ({ page }) => {
  await mockAdminApi(page, "user");
  await page.goto("/admin/users");
  await expect(page.getByText("当前账号没有管理员权限")).toBeVisible();
});

test("管理员可以查看并下载审计和运行错误日志", async ({ page }) => {
  await mockAdminApi(page);
  await page.goto("/admin/logs");
  await expect(page.getByText("admin.user.status.success")).toBeVisible();

  const auditDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载 CSV" }).click();
  expect((await auditDownload).suggestedFilename()).toMatch(/\.csv$/);

  await page.getByRole("button", { name: "运行错误" }).click();
  await expect(page.getByText("示例错误")).toBeVisible();
  const errorDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载错误文件" }).click();
  expect((await errorDownload).suggestedFilename()).toMatch(/\.jsonl$/);
});
