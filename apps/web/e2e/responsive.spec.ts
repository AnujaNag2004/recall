import { expect, test } from "@playwright/test";

const PAGES = ["/home", "/inbox", "/ask", "/library", "/graph", "/learn", "/tasks", "/insights", "/settings", "/settings/workspace", "/settings/agent-runs"];

test("every page fits a 360px phone, in both themes", async ({ page }) => {
  test.setTimeout(240_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(`${page.url()}: ${error.message.slice(0, 200)}`));

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/signup");
  await page.getByLabel("Name").fill("Priya Sharma");
  await page.getByLabel("Email").fill(`tour-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("local-rig-test-only");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/home/);

  await page.goto("/inbox");
  await page.getByLabel(/Paste a link/).fill(
    "Graphs are everywhere in interviews. Breadth first search finds shortest paths. Depth first search detects cycles.",
  );
  await page.getByRole("button", { name: "learn" }).click();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Graphs explained" })).toBeVisible();
  const card = new URL(page.url()).pathname;

  for (const theme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: theme });
    await page.evaluate((value) => localStorage.setItem("theme", value), theme);
    for (const width of [1280, 360]) {
      await page.setViewportSize({ width, height: width === 360 ? 740 : 800 });
      for (const path of [...PAGES, card]) {
        await page.goto(path);
        await page.waitForLoadState("networkidle");
        const name = path === card ? "card" : path.replaceAll("/", "-").slice(1);
        await page.screenshot({ path: `test-results/tour/${theme}-${width}-${name}.png` });
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - window.innerWidth,
        );
        expect(overflow, `${path} at ${width}px overflows`).toBeLessThanOrEqual(0);
      }
    }
  }
  expect(errors).toEqual([]);
});
