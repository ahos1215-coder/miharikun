import { test, expect } from "@playwright/test";

test.describe("Auth flow", () => {
  test("/dashboard redirects to /login when not authenticated", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });

  test("/login page shows email and password fields", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByLabel("メールアドレス")).toBeVisible();
    await expect(page.getByLabel("パスワード")).toBeVisible();
  });

  test("/login page has ログイン and 新規登録 options", async ({ page }) => {
    await page.goto("/login");
    // Default state shows ログイン submit button
    await expect(
      page.getByRole("button", { name: "ログイン" })
    ).toBeVisible();
    // Toggle to sign-up mode
    await expect(
      page.getByRole("button", { name: "新規登録" })
    ).toBeVisible();
  });
});
