import { test, expect } from "@playwright/test";

test.describe("News page", () => {
  test("shows '最新規制ニュース' heading", async ({ page }) => {
    await page.goto("/news");
    await expect(
      page.getByRole("heading", { name: "最新規制ニュース" })
    ).toBeVisible();
  });

  test("has source filter buttons (全て, NK, 国交省)", async ({ page }) => {
    await page.goto("/news");
    await expect(page.getByRole("link", { name: /全て/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /NK/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /国交省/ })).toBeVisible();
  });

  test("clicking NK filter changes URL to ?source=nk", async ({ page }) => {
    await page.goto("/news");
    const nkLink = page.getByRole("link", { name: /NK/ });
    await nkLink.click();
    await expect(page).toHaveURL(/[?&]source=nk/);
  });
});
