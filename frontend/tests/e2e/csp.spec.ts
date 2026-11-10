import { expect, test } from "@playwright/test";

test("页面使用 nonce CSP 且没有安全策略报错", async ({ page }) => {
  const violations: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" && /content security policy/i.test(message.text())) {
      violations.push(message.text());
    }
  });

  const response = await page.goto("/");
  const policy = response?.headers()["content-security-policy"] ?? "";
  expect(policy).toContain("default-src 'self'");
  expect(policy).toContain("script-src 'self' 'nonce-");
  expect(policy).toMatch(/style-src 'self' (?:'nonce-|'unsafe-inline')/);
  expect(policy).toContain("frame-ancestors 'none'");

  await expect(page.getByRole("heading", { name: "今天想处理什么？" })).toBeVisible();
  await page.goto("/qrcode");
  await expect(page.getByRole("heading", { name: "二维码 / MAC 工具" })).toBeVisible();
  await page.getByRole("textbox").fill("CSP 生成测试");
  await page.getByRole("button", { name: "立即生成" }).click();
  await expect(page.getByAltText("生成的二维码")).toBeVisible();
  expect(violations).toEqual([]);
});
