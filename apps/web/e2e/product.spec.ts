import { expect, type Page, test } from "@playwright/test";

const NOTE =
  "Graphs are everywhere in interviews. Breadth first search finds shortest paths when " +
  "every edge costs the same. Depth first search is useful for detecting cycles. Try VisuAlgo.";

async function signUp(page: Page, name: string) {
  const email = `${name.toLowerCase()}-${Date.now()}@example.com`;
  await page.goto("/");
  await page.getByRole("link", { name: "Get started free" }).first().click();
  await page.getByLabel("Name").fill(name);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("local-rig-test-only");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/home/);
  await expect(page.getByRole("heading", { name: `Welcome, ${name}` })).toBeVisible();
  return email;
}

async function saveNote(page: Page) {
  await page.goto("/inbox");
  await page.getByLabel(/Paste a link/).fill(NOTE);
  await page.getByRole("button", { name: "learn" }).click();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page).toHaveURL(/\/saves\//);
  await expect(page.getByRole("heading", { name: "Graphs explained" })).toBeVisible();
  await expect(page.getByText("A short tour of graph algorithms.")).toBeVisible();
}

test("signed-out visitors can't reach the app", async ({ page }) => {
  await page.goto("/library?mode=study");
  await expect(page).toHaveURL(/\/login\?next=%2Flibrary/);
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});

test("the full loop: save, understand, act, measure", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await signUp(page, "Priya");
  await expect(page.getByText("Nothing saved yet")).toBeVisible();

  // Capture and ingestion, on the real worker and database.
  await saveNote(page);

  // Nothing joins Tasks until it's approved.
  await page.getByRole("tab", { name: "Actions" }).click();
  await expect(page.getByText("Smallest next step")).toBeVisible();
  await page.getByRole("button", { name: "Add to tasks" }).first().click();
  await expect(page.getByText("Accepted", { exact: false }).first()).toBeVisible();

  // The task is done from the board.
  await page.goto("/tasks");
  // The box ticks once the server confirms, so this clicks rather than asserting instantly.
  await page.getByRole("checkbox", { name: /Read one problem statement/ }).click();
  await expect(page.getByRole("region", { name: "Done" })).toContainText("Read one problem");

  // The score moved.
  await page.goto("/insights");
  await expect(page.getByText("100%", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("1 of 1 acted on")).toBeVisible();
  await expect(page.getByText("Things your saves changed")).toBeVisible();

  // Home reflects it too.
  await page.goto("/home");
  await expect(page.getByText("1 day streak")).toBeVisible();

  // Ask Your Brain streams a cited answer from the save.
  await page.goto("/ask");
  await page.getByLabel("Ask anything you've saved").fill("How do I find shortest paths?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/BFS finds shortest paths/)).toBeVisible();
  await page.getByRole("button", { name: /Source 1/ }).click();
  await expect(page.getByRole("complementary", { name: "Source" })).toBeVisible();

  // Learn: make flashcards from the card, then review one.
  await page.goto("/library");
  await page.getByRole("link", { name: /Graphs explained/ }).click();
  await page.getByRole("button", { name: "Make flashcards" }).click();
  await expect(page.getByText(/Made 1 flashcards/)).toBeVisible();
  await page.goto("/learn");
  await expect(page.getByText("What is BFS?")).toBeVisible();
  await page.getByRole("button", { name: "Show answer" }).click();
  await page.getByRole("button", { name: "Good" }).click();
  await expect(page.getByText("Nothing due right now")).toBeVisible();

  // The knowledge graph drew the save's topic, and links back to the Library.
  await page.goto("/graph");
  await expect(page.getByText("Algorithms (1)")).toBeVisible();

  // The Library finds it by content.
  await page.goto("/library");
  await page.getByLabel("Search your library").fill("cycles");
  await expect(page).toHaveURL(/q=cycles/);
  await expect(page.getByRole("link", { name: /Graphs explained/ })).toBeVisible();
  await page.getByLabel("Search your library").fill("zzzznothing");
  await expect(page.getByText("Nothing matches that")).toBeVisible();

  // An API key shows once, and works.
  await page.goto("/settings");
  await page.getByLabel("Key name").fill("Laptop");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page.getByText("You won't see it again")).toBeVisible();

  // Signing out really ends the session.
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL("http://localhost:3100/");
  await page.goto("/home");
  await expect(page).toHaveURL(/\/login/);

  expect(errors).toEqual([]);
});

test("a teammate joins through an invite and shares the workspace", async ({ browser }) => {
  const owner = await (await browser.newContext({
    permissions: ["clipboard-read", "clipboard-write"],
  })).newPage();
  await signUp(owner, "Maya");
  await owner.goto("/settings/workspace");
  await owner.getByLabel("Team name").fill("Startup Squad");
  await owner.getByRole("button", { name: "Create", exact: true }).click();
  await owner.getByRole("button", { name: /Switch workspace/ }).click();
  await owner.getByRole("menuitem", { name: "Startup Squad" }).click();
  await expect(owner.getByRole("heading", { name: "Invite someone" })).toBeVisible();

  const teammate = await (await browser.newContext()).newPage();
  const teammateEmail = await signUp(teammate, "Dev");

  await owner.getByLabel("Email").fill(teammateEmail);
  await owner.getByRole("button", { name: "Create invite" }).click();
  await owner.getByRole("button", { name: "Copy link" }).click();
  const link = await owner.evaluate(() => navigator.clipboard.readText());
  expect(link).toContain("/invites/");

  await teammate.goto(link);
  await teammate.getByRole("button", { name: "Accept invite" }).click();
  await expect(teammate).toHaveURL(/\/home/);
  await expect(teammate.getByText("You're in Startup Squad.")).toBeVisible();

  await owner.reload();
  await expect(owner.getByText("Dev", { exact: true })).toBeVisible();
});

test("the demo account signs in without exposing its password", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Try the live demo" }).first().click();
  expect(await page.content()).not.toContain("e2e-demo-password");
  await page.getByRole("button", { name: "Continue with demo account" }).click();
  await expect(page).toHaveURL(/\/home/);
  await expect(page.getByRole("heading", { name: "Welcome, Demo" })).toBeVisible();
});
