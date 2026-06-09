import { chromium, expect, test as base } from "@playwright/test";


const test = base.extend({
  browser: async ({}, use) => {
    if (!process.env.PLAYWRIGHT_CDP_URL) {
      throw new Error("PLAYWRIGHT_CDP_URL is required for the containerized browser");
    }
    const browser = await chromium.connectOverCDP(process.env.PLAYWRIGHT_CDP_URL);
    await use(browser);
  }
});


const pages = [
  ["/", "仪表盘", "dashboard"],
  ["/sources", "订阅源", "sources"],
  ["/nodes", "节点", "nodes"],
  ["/users", "用户", "users"],
  ["/settings", "模板设置", "settings"]
];

test("main workflows fit the viewport", async ({ page }, testInfo) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto("/login");
  await page.getByLabel("用户名").fill(process.env.ADMIN_USERNAME || "admin");
  await page.getByLabel("密码").fill(process.env.ADMIN_PASSWORD || "smoke-admin-secret");
  await page.getByRole("button", { name: /登\s*录/ }).click();
  await expect(page).toHaveURL(/\/$/);

  for (const [path, title, slug] of pages) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
    await expect.poll(async () => page.evaluate(
      () => document.body.scrollWidth <= document.documentElement.clientWidth
    )).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`${slug}.png`),
      fullPage: true
    });
  }

  const username = `portal-${testInfo.project.name}`;
  await page.evaluate(async ({ username }) => {
    const response = await fetch("/api/users/", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password: "portal-secret", node_ids: [] })
    });
    if (!response.ok && response.status !== 400) {
      throw new Error(`Unable to create portal user: ${response.status}`);
    }
  }, { username });

  await page.goto("/user/login");
  await expect(page.getByRole("heading", { name: "登录订阅门户" })).toBeVisible();
  await expect.poll(async () => page.evaluate(
    () => document.body.scrollWidth <= document.documentElement.clientWidth
  )).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("user-login.png"), fullPage: true });
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("密码").fill("portal-secret");
  await page.getByRole("button", { name: "进入订阅门户" }).click();
  await expect(page).toHaveURL(/\/user$/);
  await expect(page.getByRole("heading", { name: "我的订阅" })).toBeVisible();
  await expect(page.locator("input[readonly]")).toHaveValue(/\/sub\//);
  await expect(page.getByRole("button", { name: /复制地址/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /打开订阅/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /下载 YAML/ })).toBeVisible();
  await expect.poll(async () => page.evaluate(
    () => document.body.scrollWidth <= document.documentElement.clientWidth
  )).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("user-portal.png"), fullPage: true });
  await page.getByRole("button", { name: /退出登录/ }).click();
  await expect(page).toHaveURL(/\/user\/login$/);

  await page.goto("/missing-page");
  await expect(page.getByText("页面不存在")).toBeVisible();
  expect(errors).toEqual([]);
});
