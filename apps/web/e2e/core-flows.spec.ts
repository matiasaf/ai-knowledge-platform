import { expect, test } from "@playwright/test";
import { buildTextPdf } from "./pdf";

// The core flows of the app, driven through a real browser against a real API.
// Read top to bottom, each test documents what a user does and what the app promises.

test("a PDF is uploaded, extracted, indexed and then found with page provenance", async ({
  page,
}) => {
  await page.goto("/");

  // 1. Ingestion: one form, three API calls (upload → extract → index).
  await page.getByLabel("PDF document").setInputFiles({
    name: "handbook.pdf",
    mimeType: "application/pdf",
    buffer: buildTextPdf([
      "Leave requests are submitted through the HR portal.",
      "Security incidents are reported to the on-call engineer.",
    ]),
  });
  await page.getByRole("button", { name: "Upload document" }).click();

  const indexed = page.getByRole("region", { name: "Indexed for retrieval" });
  await expect(indexed).toBeVisible();
  await expect(indexed.getByText("handbook.pdf")).toBeVisible();
  await expect(indexed.locator("dt:has-text('Pages') + dd").first()).toHaveText("2");

  // 2. Retrieval: ranked excerpts, each tied to its document and page. No AI involved.
  await page.getByLabel("Question or keywords").fill("leave requests");
  await page.getByRole("button", { name: "Find evidence" }).click();

  const evidence = page.getByRole("region", { name: "Evidence for “leave requests”" });
  const firstMatch = evidence.getByRole("listitem").first();
  await expect(firstMatch).toContainText("handbook.pdf");
  await expect(firstMatch).toContainText("Page 1");
  await expect(firstMatch).toContainText("Leave requests are submitted through the HR portal.");

  // 3. A miss is reported as a miss, never filled in with a guess.
  await page.getByLabel("Question or keywords").fill("quarterly revenue");
  await page.getByRole("button", { name: "Find evidence" }).click();
  await expect(page.getByText("No indexed passage matched.")).toBeVisible();
});

test("a file that is not a PDF is rejected at upload", async ({ page }) => {
  await page.goto("/");

  await page.getByLabel("PDF document").setInputFiles({
    name: "fake.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("this is not a pdf"),
  });
  await page.getByRole("button", { name: "Upload document" }).click();

  // The API checks the file signature, not the extension or the declared type.
  const upload = page.getByRole("region", { name: "Add a source document" });
  await expect(upload.getByRole("alert")).toContainText("Upload failed");
});

test("without a configured provider, asking a question fails explicitly", async ({ page }) => {
  await page.goto("/");

  await page.getByLabel("Question", { exact: true }).fill("How are leave requests submitted?");
  await page.getByRole("button", { name: "Get grounded answer" }).click();

  // The API returns 503 generation_not_configured; the UI shows it instead of an answer.
  const answerPanel = page.getByRole("region", { name: "Ask the indexed knowledge base" });
  await expect(answerPanel.getByRole("alert")).toContainText(
    "Answer generation is not configured for this API.",
  );
  await expect(page.getByRole("heading", { name: /^Answer to/ })).toHaveCount(0);
});
