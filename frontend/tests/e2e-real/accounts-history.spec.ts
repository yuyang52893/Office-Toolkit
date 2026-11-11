import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

async function login(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page.getByText(username)).toBeVisible();
}

async function apiLogin(
  request: APIRequestContext,
  username: string,
  password: string,
) {
  const response = await request.post("/api/v1/auth/login", {
    data: { username, password },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).data.access_token as string;
}

test("真实账号处理文件后可以在个人历史中下载", async ({ page }) => {
  await login(page, "80000001", "UserPass1");
  await page.goto("/excel");
  await page.locator('input[type="file"]').setInputFiles({
    name: "账号历史.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("地区,金额\n华东,100\n华南,200\n", "utf8"),
  });
  await page.getByRole("button", { name: "读取工作表" }).click();
  await page.getByRole("button", { name: "开始拆分" }).click();
  await expect(page.getByRole("heading", { name: "拆分完成" })).toBeVisible();
  await expect(page.getByText(/已保存到个人历史/)).toBeVisible();

  await page.goto("/history");
  await expect(page.getByRole("heading", { name: "个人处理历史" })).toBeVisible();
  await expect(page.getByText("可下载").first()).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "下载结果" }).first().click();
  expect((await downloadPromise).suggestedFilename()).toMatch(/\.zip$/);
});

test("真实管理员可以管理账号并下载审计日志", async ({ page }) => {
  await login(page, "90000001", "AdminPass1");
  await page.goto("/admin/users");
  await expect(page.getByRole("heading", { name: "账号管理" })).toBeVisible();
  await expect(page.getByText("80000001")).toBeVisible();
  await expect(page.getByText(/password_hash|recovery_answer_hash/i)).toHaveCount(0);

  await page.goto("/admin/logs");
  await expect(page.getByRole("heading", { name: "日志中心" })).toBeVisible();
  await expect(page.getByText(/auth\.login\.success|admin\./).first()).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载 JSON" }).click();
  expect((await downloadPromise).suggestedFilename()).toMatch(/\.json$/);

  await page.getByRole("button", { name: "运行错误" }).click();
  await expect(page.getByText("该日期没有运行错误记录。")).toBeVisible();
});

test("用户不能下载他人历史，禁用后旧 Token 立即失效", async ({ request }) => {
  const secondUsername = "80000002";
  const registered = await request.post("/api/v1/auth/register", {
    data: {
      username: secondUsername,
      password: "SecondPass1",
      recovery_question: "第二用户找回问题",
      recovery_answer: "第二用户答案",
    },
  });
  expect(registered.status()).toBe(201);

  const secondToken = await apiLogin(request, secondUsername, "SecondPass1");
  const inspect = await request.post("/api/v1/excel/inspect", {
    headers: { Authorization: `Bearer ${secondToken}` },
    multipart: {
      files: {
        name: "other-user.csv",
        mimeType: "text/csv",
        buffer: Buffer.from("地区,金额\n华东,100\n", "utf8"),
      },
    },
  });
  expect(inspect.ok()).toBeTruthy();
  const upload = (await inspect.json()).data;
  const split = await request.post("/api/v1/excel/split", {
    headers: { Authorization: `Bearer ${secondToken}` },
    data: {
      upload_id: upload.upload_id,
      sheets: [{ file_id: upload.files[0].file_id, sheet_index: 0 }],
      mode: "by_sheet",
      has_header: true,
      remove_empty_rows: false,
      remove_duplicates: false,
    },
  });
  expect(split.ok()).toBeTruthy();
  const historyId = (await split.json()).data.history.history_id as string;

  const firstToken = await apiLogin(request, "80000001", "UserPass1");
  const forbiddenDownload = await request.get(
    `/api/v1/history/${historyId}/download`,
    { headers: { Authorization: `Bearer ${firstToken}` } },
  );
  expect(forbiddenDownload.status()).toBe(404);

  const adminToken = await apiLogin(request, "90000001", "AdminPass1");
  const usersResponse = await request.get("/api/v1/admin/users", {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  expect(usersResponse.ok()).toBeTruthy();
  const secondUser = (await usersResponse.json()).data.items.find(
    (item: { username: string }) => item.username === secondUsername,
  );
  expect(secondUser).toBeTruthy();

  try {
    const disabled = await request.patch(
      `/api/v1/admin/users/${secondUser.id}/status`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: { is_active: false },
      },
    );
    expect(disabled.ok()).toBeTruthy();

    const me = await request.get("/api/v1/auth/me", {
      headers: { Authorization: `Bearer ${secondToken}` },
    });
    expect(me.status()).toBe(401);
  } finally {
    await request.patch(`/api/v1/admin/users/${secondUser.id}/status`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { is_active: true },
    });
  }
});
