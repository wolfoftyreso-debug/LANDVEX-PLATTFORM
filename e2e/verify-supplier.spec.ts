import { expect, test } from "@playwright/test";

import { OPS_EMAIL, OPS_PASSWORD, signIn, uniqueName } from "./helpers";

/** Critical flow 1: ops onboards and verifies a supplier; badge appears.
 * 13 requirement items × 3 transitions = many server actions — allow time. */
test("ops verifies a supplier end-to-end", async ({ page }) => {
  test.setTimeout(420_000);
  await signIn(page, OPS_EMAIL, OPS_PASSWORD);

  // Create the company
  const name = uniqueName("E2E Weld UAB");
  await page.goto("/en/admin/companies");
  await page.getByLabel("Company name").fill(name);
  await page.getByLabel("Country").fill("LT");
  await page.getByLabel("Registration number").fill("309999999");
  await page.getByRole("button", { name: "Create" }).click();

  // Open the 360 view, add a worker, open the case
  await page.getByRole("link", { name }).click();
  await page.waitForURL(/\/admin\/companies\/[0-9a-f-]{36}/);
  // The contacts form reuses the same label — target the workers input by id
  await page.locator("#worker-name").fill("E2E Welder");
  await page.getByRole("button", { name: "Add worker" }).click();
  await page.getByRole("button", { name: /Open verification case/ }).click();
  await page.getByRole("link", { name: "→" }).click();
  await expect(page.getByRole("heading", { name: /Verification case/ })).toBeVisible();

  // Send to review, then walk every item to approved
  await page.getByRole("button", { name: "Send to review" }).click();

  async function clickAll(name: string, exact = false) {
    const locator = page.getByRole("button", { name, exact });
    for (;;) {
      const before = await locator.count();
      if (before === 0) break;
      await locator.first().click();
      // Each click is a server action + revalidate; wait for the row to flip
      await expect(locator).toHaveCount(before - 1, { timeout: 30_000 });
    }
  }
  await clickAll("Mark submitted");
  await clickAll("Start review");
  await clickAll("Approve", true);

  // Verify the case — the binary badge appears
  await page.getByRole("button", { name: "Mark verified" }).click();
  await expect(page.getByText("Verified for work in Sweden")).toBeVisible();
});
