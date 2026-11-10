import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page.getByText(username)).toBeVisible();
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
