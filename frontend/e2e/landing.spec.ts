import { test, expect } from "@playwright/test";

test.describe("Landing page", () => {
  test("shows MIHARIKUN heading", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "MIHARIKUN" })).toBeVisible();
  });

  test("has '最新規制を見る' link pointing to /news", async ({ page }) => {
    await page.goto("/");
    const link = page.getByRole("link", { name: /最新規制を見る/ });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", "/news");
  });

  test("has '無料で始める' link pointing to /login", async ({ page }) => {
    await page.goto("/");
    const link = page.getByRole("link", { name: "無料で始める" });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", "/login");
  });
});
