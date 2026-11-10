import { expect, test, type Page } from "@playwright/test";

type MockRole = "user" | "admin";

type MockUser = {
  id: number;
  username: string;
  role: MockRole;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  last_login_at: string | null;
};

function jsonBody(data: unknown, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify({
      success: true,
      data,
      error: null,
      request_id: "e2e-request",
    }),
  };
}

async function mockAuthApi(page: Page, options?: { mustChangePassword?: boolean }) {
  let password = "Password1";
  const user: MockUser = {
    id: 1,
    username: "00123456",
    role: "user",
    is_active: true,
    must_change_password: options?.mustChangePassword ?? false,
    created_at: "2026-11-10T00:00:00Z",
    last_login_at: null,
  };
  let sessionVersion = 1;

  await page.route("**/api/v1/auth/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const body = request.postDataJSON?.() as Record<string, string> | null;
    const authorization = request.headers().authorization;

    if (path.endsWith("/auth/register") && request.method() === "POST") {
      expect(body?.username).toBe("00123456");
      expect(body?.password).toBe(password);
      await route.fulfill(jsonBody(user, 201));
      return;
    }

    if (path.endsWith("/auth/login") && request.method() === "POST") {
      if (body?.username !== user.username || body?.password !== password) {
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({
            success: false,
            data: null,
            error: { code: "INVALID_CREDENTIALS", message: "用户名或密码错误" },
            request_id: "e2e-request",
          }),
        });
        return;
      }
      await route.fulfill(
        jsonBody({
          access_token: `token-${sessionVersion}`,
          user: { ...user, must_change_password: options?.mustChangePassword ?? false },
        }),
      );
      return;
    }

    if (path.endsWith("/auth/me") && request.method() === "GET") {
      expect(authorization).toMatch(/^Bearer token-/);
      await route.fulfill(jsonBody(user));
      return;
    }

    if (path.endsWith("/auth/logout") && request.method() === "POST") {
      expect(authorization).toMatch(/^Bearer token-/);
      sessionVersion += 1;
      await route.fulfill(jsonBody(null));
      return;
    }

    if (path.endsWith("/auth/recovery-question") && request.method() === "POST") {
      await route.fulfill(jsonBody({ recovery_question: "请输入注册时设置的找回问题和答案" }));
      return;
    }

    if (path.endsWith("/auth/reset-password") && request.method() === "POST") {
      expect(body?.recovery_question).toBe("我的问题");
      expect(body?.recovery_answer).toBe("我的答案");
      password = body?.new_password ?? password;
      await route.fulfill(jsonBody(null));
      return;
    }

    if (path.endsWith("/auth/change-password") && request.method() === "POST") {
      expect(authorization).toMatch(/^Bearer token-/);
      password = body?.new_password ?? password;
      sessionVersion += 1;
      user.must_change_password = false;
      await route.fulfill(jsonBody({ access_token: `token-${sessionVersion}` }));
      return;
    }

    await route.fulfill({ status: 404, body: "not mocked" });
  });

  return user;
}

test("用户可以注册、自动登录、刷新保持会话并退出", async ({ page }) => {
  await mockAuthApi(page);
  await page.goto("/register");

  await page.getByLabel("用户名").fill("00123456");
  await page.getByLabel("密码", { exact: true }).fill("Password1");
  await page.getByLabel("找回问题").fill("我的问题");
  await page.getByLabel("找回答案").fill("我的答案");
  await page.getByRole("button", { name: "注册账号" }).click();

  await expect(page.getByRole("link", { name: "个人历史" })).toBeVisible();
  await page.reload();
  await expect(page.getByText("00123456")).toBeVisible();

  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page.getByRole("link", { name: "登录", exact: true })).toBeVisible();
});

test("注册页校验数字用户名和密码长度", async ({ page }) => {
  await page.goto("/register");

  await page.getByLabel("用户名").fill("abc");
  await page.getByLabel("密码", { exact: true }).fill("123");
  await page.getByLabel("找回问题").fill("问题");
  await page.getByLabel("找回答案").fill("答案");
  await page.getByRole("button", { name: "注册账号" }).click();

  await expect(page.getByText("用户名必须是 8–18 位数字")).toBeVisible();
  await expect(page.getByText("密码长度必须为 8–18 位")).toBeVisible();
});

test("找回密码需要用户名、自定义问题和答案", async ({ page }) => {
  await mockAuthApi(page);
  await page.goto("/recover");

  await page.getByLabel("用户名").fill("00123456");
  await page.getByLabel("找回问题", { exact: true }).fill("我的问题");
  await page.getByLabel("找回答案").fill("我的答案");
  await page.getByLabel("新密码", { exact: true }).fill("NewPass1");
  await page.getByLabel("确认新密码").fill("NewPass1");
  await page.getByRole("button", { name: "重置密码" }).click();

  await expect(page.getByText("密码已重置，请使用新密码登录")).toBeVisible();
});

test("临时密码用户登录后被要求修改密码", async ({ page }) => {
  await mockAuthApi(page, { mustChangePassword: true });
  await page.goto("/login");

  await page.getByLabel("用户名").fill("00123456");
  await page.getByLabel("密码", { exact: true }).fill("Password1");
  await page.getByRole("button", { name: "登录" }).click();

  await expect(page).toHaveURL(/\/change-password/);
  await expect(page.getByRole("heading", { name: "修改密码" })).toBeVisible();

  await page.getByLabel("当前密码").fill("Password1");
  await page.getByLabel("新密码", { exact: true }).fill("NewPass1");
  await page.getByLabel("确认新密码").fill("NewPass1");
  await page.getByRole("button", { name: "保存新密码" }).click();

  await expect(page.getByRole("link", { name: "个人历史" })).toBeVisible();
});

test("无 Token 访问登录专属页面会跳转登录", async ({ page }) => {
  await page.goto("/change-password");

  await expect(page).toHaveURL(/\/login\?next=%2Fchange-password$/);
  await expect(page.getByText("此功能仅登录用户可用")).toBeVisible();
});
