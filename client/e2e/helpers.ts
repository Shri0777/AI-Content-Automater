/* Shared helpers for the browser tests. */

import { execSync } from "node:child_process";
import path from "node:path";

import { expect, type Page } from "@playwright/test";

export const PASSWORD = "a-long-test-passphrase-42";

/** Make one single-use invite code with manage.py (see playwright.config.ts). */
export function makeInviteCode(): string {
  const manage = process.env.E2E_MANAGE;
  if (!manage) throw new Error("Set E2E_MANAGE to the manage.py command (see playwright.config.ts).");
  const output = execSync(`${manage} create_invite_codes 1`, { cwd: path.resolve(__dirname, "../.."), encoding: "utf8" });
  const lines = output.trim().split("\n");
  return lines[lines.length - 1].trim();
}

/** Collect console errors and warnings; call the result to assert there were none. */
export function watchConsole(page: Page): () => void {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") problems.push(`${message.type()}: ${message.text()}`);
  });
  page.on("pageerror", (error) => problems.push(`page error: ${error.message}`));
  return () => expect(problems, "console errors or warnings").toEqual([]);
}

/**
 * Open a page and wait until it has finished loading, including Next.js
 * prefetching the pages it links to. Leaving earlier cancels those scripts,
 * which Firefox reports as console warnings that no real visitor causes.
 */
export async function openFully(page: Page, path: string) {
  await page.goto(path);
  await page.waitForLoadState("networkidle");
}

/** Assert the page does not scroll sideways (nothing wider than the screen). */
export async function expectNoSidewaysScroll(page: Page) {
  const tooWide = await page.evaluate(() => {
    if (document.documentElement.scrollWidth <= window.innerWidth) return [];
    return [...document.querySelectorAll("body *")]
      .filter((element) => element.getBoundingClientRect().right > window.innerWidth + 1)
      .slice(-3)
      .map((element) => `<${element.tagName.toLowerCase()} class="${element.getAttribute("class") ?? ""}">`);
  });
  expect(tooWide, `wider than the screen on ${page.url()}`).toEqual([]);
}
