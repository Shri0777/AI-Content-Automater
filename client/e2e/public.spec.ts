/* The pages anyone can open: they render, fit phones, and respect reduced motion. */

import { expect, test } from "@playwright/test";

import { expectNoSidewaysScroll, openFully, watchConsole } from "./helpers";

const PUBLIC_PAGES = [
  { path: "/", heading: /News in\./ },
  { path: "/login", heading: "Sign in" },
  { path: "/register", heading: "Create your account" },
  { path: "/recover", heading: "Reset your password" },
  { path: "/social/link-result?platform=x&result=error&reason=link_failed", heading: "Could not connect x" },
];

for (const width of [390, 1280]) {
  test(`public pages render cleanly at ${width}px`, async ({ page }) => {
    const expectQuietConsole = watchConsole(page);
    await page.setViewportSize({ width, height: 860 });
    for (const { path, heading } of PUBLIC_PAGES) {
      await openFully(page, path);
      await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
      await expectNoSidewaysScroll(page);
    }
    // Long enough for Firefox to report an unused font preload.
    await page.waitForTimeout(4000);
    expectQuietConsole();
  });
}

test("the signed-in app sends visitors to sign in", async ({ page }) => {
  await page.goto("/app/posts");
  await expect(page).toHaveURL(/\/login$/);
});

test("with reduced motion nothing animates", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.waitForTimeout(800);
  const running = await page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running").length);
  const first = await page.locator("canvas").evaluate((canvas: HTMLCanvasElement) => canvas.toDataURL());
  await page.waitForTimeout(600);
  const second = await page.locator("canvas").evaluate((canvas: HTMLCanvasElement) => canvas.toDataURL());
  expect(running).toBe(0);
  expect(second).toBe(first);
});

test("the dither animates when motion is allowed", async ({ page }) => {
  await page.goto("/");
  const first = await page.locator("canvas").evaluate((canvas: HTMLCanvasElement) => canvas.toDataURL());
  await page.waitForTimeout(600);
  const second = await page.locator("canvas").evaluate((canvas: HTMLCanvasElement) => canvas.toDataURL());
  expect(second).not.toBe(first);
});
