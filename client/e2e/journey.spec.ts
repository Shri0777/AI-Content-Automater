/*
 * A new user's whole journey in demo mode: sign up, add keys and a demo
 * account, save a developer app, make a plan and a post, edit it, approve
 * it and see it posted. One test, so it signs up and logs in only once
 * (the API allows 10 logins a minute).
 */

import { expect, test } from "@playwright/test";

import { expectNoSidewaysScroll, makeInviteCode, openFully, PASSWORD, watchConsole } from "./helpers";

const APP_PAGES = ["/app", "/app/posts", "/app/plans", "/app/plans/new", "/app/accounts", "/app/keys", "/app/notifications", "/app/settings"];

test("a new user goes from sign-up to a published post", async ({ page }) => {
  const expectQuietConsole = watchConsole(page);
  const email = `e2e-${Date.now()}@example.com`;

  await test.step("sign up with an invite code and save the recovery codes", async () => {
    await page.goto("/register");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByLabel("Invite code").fill(makeInviteCode());
    await page.getByRole("button", { name: "Create account" }).click();
    const done = page.getByRole("button", { name: /continue/i });
    await expect(done).toBeDisabled();
    await page.getByRole("checkbox").check();
    await done.click();
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  });

  await test.step("save demo text and image keys and test them", async () => {
    await page.getByRole("link", { name: "AI keys" }).click();
    const text = page.locator('section[aria-labelledby="text-title"]');
    await text.getByLabel("Provider").selectOption("anthropic");
    await expect(text.getByText("with dashes: claude-sonnet-5-5")).toBeVisible();
    await expect(page.locator("#text-model-options option")).toHaveCount(3);
    // Browsers must not fill a saved login (email, password) into key forms.
    await expect(text.locator('input[name="api_key"]')).toHaveAttribute("autocomplete", "new-password");
    await expect(text.locator('input[name="model_name"]')).toHaveAttribute("autocomplete", "off");
    for (const kind of ["text", "image"]) {
      const section = page.locator(`section[aria-labelledby="${kind}-title"]`);
      await section.getByLabel("Provider").selectOption("demo");
      await section.getByRole("button", { name: "Save key" }).click();
      await section.getByRole("button", { name: "Test connection" }).click();
      await expect(section.getByText(/^Working/)).toBeVisible();
    }
  });

  await test.step("connect a demo account and save an X developer app", async () => {
    await page.getByRole("link", { name: "Social accounts" }).click();
    await page.getByRole("button", { name: "Add a demo account" }).click();
    await expect(page.locator('section[aria-labelledby="connected"]').getByText("Demo account 1")).toBeVisible();

    const x = page.locator('section[aria-labelledby="direct"] li').filter({ hasText: /^X/ });
    await expect(x.getByText("Needs your developer app")).toBeVisible();
    await x.getByRole("button", { name: "Set up" }).click();
    await expect(x.getByText("/api/v1/social/link/x/callback/")).toBeVisible();
    await x.getByLabel("OAuth 2.0 Client ID").fill("my-x-client-id");
    await x.getByLabel("Client Secret").fill("my-x-client-secret");
    await x.getByRole("button", { name: "Save app" }).click();
    await expect(x.getByText("Using your developer app")).toBeVisible();
    await expect(x.getByRole("button", { name: "Connect" })).toBeVisible();
  });

  await test.step("keyboard users can skip the menu to the form", async () => {
    await page.goto("/app/plans/new");
    await expect(page.getByRole("heading", { name: "New plan" })).toBeVisible();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
    await page.keyboard.press("Enter");
    await page.keyboard.press("Tab");
    await expect(page.getByLabel("Plan name")).toBeFocused();
  });

  await test.step("pick topics by searching, and add one of your own", async () => {
    const search = page.getByRole("combobox", { name: /Find a topic/ });
    await search.fill("ai news");
    await expect(page.getByRole("option", { name: /AI news/ })).toBeVisible();
    await search.press("Enter");
    await expect(page.getByRole("button", { name: "Remove AI news" })).toBeVisible();
    await search.fill("security");
    await expect(page.getByRole("option", { name: /Cybersecurity/ })).toBeVisible();
    await search.press("Escape");
    await expect(page.getByRole("listbox")).toHaveCount(0);

    await page.getByRole("button", { name: "Add your own topic" }).click();
    await page.getByLabel("Topic name").fill("Indian EV market");
    await page.getByLabel(/Words to look for/).fill("electric vehicle, EV, India");
    await page.getByLabel(/Your instructions for the AI/).fill("Focus on prices in rupees.");
    await page.getByRole("button", { name: "Add topic" }).click();
    await expect(page.getByRole("button", { name: "Remove Indian EV market" })).toBeVisible();
  });

  await test.step("create a plan with posting times", async () => {
    await page.getByLabel("Plan name").fill("Weekday tech news");
    await page.getByRole("button", { name: "Add posting times" }).click();
    const saturday = page.getByRole("button", { name: "Sat" });
    await saturday.focus();
    await page.keyboard.press("Space");
    await expect(saturday).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Create plan" }).click();
    await expect(page.getByRole("heading", { name: "Weekday tech news" })).toBeVisible();
    await expect(page.locator('section[aria-labelledby="next"] li').first()).toBeVisible();
  });

  await test.step("make a post, edit its wording and approve it", async () => {
    await page.getByRole("button", { name: "Make a post now" }).click();
    await expect(page).toHaveURL(/\/app\/posts\/[0-9a-f-]{36}$/);
    const approve = page.getByRole("button", { name: /^Approve/ });
    await expect(approve).toBeVisible({ timeout: 90_000 });
    await expect(page.locator('section[aria-labelledby="check"]')).toContainText("Passed the check");
    // The post carries key points, not just a headline (post_creation.md).
    await expect(page.locator('section[aria-label="Caption"] ol li').first()).toBeVisible();
    // The post is a set of slides; the arrow keys move between them.
    const slides = page.getByRole("region", { name: "Slides" });
    await expect(slides.getByRole("img")).toBeVisible();
    await expect(slides.getByText(/^Slide 1 of \d+$/)).toBeVisible();
    await slides.locator('[tabindex="0"]').focus();
    await page.keyboard.press("ArrowRight");
    await expect(slides.getByText(/^Slide 2 of \d+$/)).toBeVisible();

    await page.getByRole("button", { name: "Edit the wording" }).click();
    await page.locator('textarea[name="caption"]').fill("My own caption, written by a person.");
    await page.getByRole("button", { name: "Save my version" }).click();
    await expect(page.getByText("My own caption, written by a person.")).toBeVisible();
    await expect(page.locator('section[aria-labelledby="check"]')).toContainText("your own words");

    await approve.click();
    await expect(page.locator('section[aria-labelledby="where"]')).toContainText("Posted", { timeout: 30_000 });
  });

  await test.step("a reload keeps you signed in", async () => {
    await page.reload();
    await expect(page.getByText("My own caption, written by a person.")).toBeVisible();
  });

  await test.step("every app page fits a phone screen", async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    for (const path of APP_PAGES) {
      await openFully(page, path);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toHaveCount(0);
      await expectNoSidewaysScroll(page);
    }
    const menu = page.getByRole("button", { name: "Menu" });
    await menu.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Close" })).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("link", { name: "AI keys" })).toBeVisible();
  });

  await test.step("sign out", async () => {
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/(login)?$/);
    await page.goto("/app");
    await expect(page).toHaveURL(/\/login$/);
  });

  expectQuietConsole();
});
