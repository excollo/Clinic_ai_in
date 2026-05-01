import { test, expect } from "@playwright/test";

test("upload long-running transcription eventually completes without false failure", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("clinic_doctor_id", "doc-1");
    window.localStorage.setItem("clinic_api_key", "token-1");
  });

  let statusPollCount = 0;

  await page.route("**/doctor/doc-1/queue", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        patients: [
          {
            patient_id: "pat-1",
            visit_id: "v1",
            name: "Test Patient",
            age: 32,
            sex: "male",
            token_number: "OPD-1",
            visit_type: "walk_in",
            status: "in_consult",
            chief_complaint: "cough",
          },
        ],
      }),
    });
  });

  await page.route("**/api/visits/v1", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "v1",
        patient_id: "pat-1",
        status: "in_consult",
        visit_type: "walk_in",
        chief_complaint: "cough",
        patient: { first_name: "Test", last_name: "Patient", date_of_birth: "1992-01-01", gender: "male" },
      }),
    });
  });

  await page.route("**/patients/pat-1/visits/v1/vitals/required-fields", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ fixed_fields: [], dynamic_fields: [] }),
    });
  });

  await page.route("**/api/notes/transcribe", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ job_id: "job-1", status: "queued", message: "Queued" }),
    });
  });

  await page.route("**/api/notes/transcribe/status/pat-1/v1", async (route) => {
    statusPollCount += 1;
    if (statusPollCount === 2) {
      await route.abort("failed");
      return;
    }
    const status =
      statusPollCount < 3 ? "processing" : statusPollCount < 4 ? "timeout" : "completed";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        jobId: "job-1",
        status,
        message:
          status === "completed"
            ? "done"
            : status === "timeout"
              ? "Transcription is still processing in background. You can keep this page open or check again shortly."
              : "Transcription in progress",
      }),
    });
  });

  await page.route("**/api/notes/pat-1/visits/v1/dialogue/structure", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ dialogue: [{ Doctor: "How are you?" }, { Patient: "I am better." }] }),
    });
  });

  await page.route("**/api/notes/pat-1/visits/v1/dialogue", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        audio_file_path: "transcript-1",
        structured_dialogue: [{ Doctor: "How are you?" }, { Patient: "I am better." }],
      }),
    });
  });

  await page.goto("/visits/v1");
  await page.getByRole("button", { name: /Continue to vitals/i }).click();
  await page.getByRole("button", { name: /Skip vitals/i }).click();

  await page.setInputFiles('input[type="file"]', {
    name: "consultation.webm",
    mimeType: "audio/webm",
    buffer: Buffer.from("fake audio"),
  });
  await page.getByRole("button", { name: "Upload" }).click();

  await expect(page.locator("text=Transcript processing failed.")).toHaveCount(0);
  await expect(page.locator("text=How are you?")).toBeVisible({ timeout: 20000 });
  await expect(page.locator("text=I am better.")).toBeVisible();
});
