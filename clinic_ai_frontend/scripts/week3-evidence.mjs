import { chromium } from "@playwright/test";
import fs from "fs/promises";

const base = "http://localhost:5174";
const shotDir = "artifacts/week3";

async function ensureDir() {
  await fs.mkdir(shotDir, { recursive: true });
}

async function shot(page, name) {
  const path = `${shotDir}/${name}.png`;
  await page.screenshot({ path, fullPage: true });
  return path;
}

async function run() {
  await ensureDir();
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const consoleLogs = [];
  page.on("console", (msg) => consoleLogs.push(msg.text()));

  await page.goto(`${base}/login`);
  await page.evaluate(() => {
    localStorage.setItem("clinic_api_key", "demo-api-key");
    localStorage.setItem("clinic_doctor_id", "doctor-opaque-001");
    localStorage.setItem("clinic_doctor_name", "Priya Sharma");
    localStorage.setItem("clinic_mobile", "9876543210");
    localStorage.removeItem("consent_sync_mock_attempt");
  });
  await page.goto(`${base}/patients`);

  await shot(page, "screen10_patients_loaded_pre");
  await page.goto(`${base}/patients`);
  console.log("URL_AFTER_PATIENTS", page.url());
  await shot(page, "debug_patients_page");
  await page.waitForTimeout(1000);
  await shot(page, "screen10_patients_loaded");
  await page.fill('input[placeholder="Search by name or mobile"]', "zzzzzzzz");
  await page.waitForTimeout(500);
  await shot(page, "screen10_patients_empty_state");
  await page.fill('input[placeholder="Search by name or mobile"]', "");
  await page.waitForTimeout(500);
  await page.getByRole("button", { name: /Register/i }).first().click();
  await page.waitForTimeout(500);
  await shot(page, "screen11_register_walkin");
  await page.click('button:has-text("Schedule")');
  await page.waitForTimeout(300);
  await shot(page, "screen11_register_schedule");
  await page.click('button:has-text("Walk-in")');
  await page.fill('input[placeholder="Patient full name"]', "Test Patient");
  await page.fill('input[placeholder="+91 Mobile number"]', "9876543210");
  await page.fill('textarea[placeholder="Chief complaint"]', "Chest pain");
  await page.fill('input[placeholder="Age"]', "35");
  await page.click('button:has-text("Continue to consent")');
  await page.waitForTimeout(1200);
  await shot(page, "screen12_consent");
  await page.check('input[type="checkbox"]');
  await page.click('button:has-text("Capture consent")');
  await page.waitForTimeout(1000);
  const urlAfterCapture = page.url();
  const unsyncedAfterCapture = await page.getByText(/unsynced/i).count();
  await shot(page, "screen13_walkin_confirmation");
  await page.waitForTimeout(9000);
  const unsyncedAfterWait = await page.getByText(/unsynced/i).count();
  await shot(page, "screen13_walkin_confirmation_after_retries");
  await page.goto(`${base}/schedule-confirmation`);
  await page.waitForTimeout(400);
  await shot(page, "screen14_schedule_confirmation");
  await page.goto(`${base}/patients/pat_rs`);
  await page.waitForTimeout(700);
  await shot(page, "screen15_overview");
  await page.click('button:has-text("Continuity Summary")');
  await page.waitForTimeout(700);
  await shot(page, "screen15_continuity");
  await page.goto(`${base}/scan-share`);
  await page.waitForTimeout(1200);
  await shot(page, "screen16_scan_share");
  await page.fill('input[placeholder="14-digit ABHA ID"]', "12345678901234");
  await shot(page, "screen16_manual_entry");
  await browser.close();

  await fs.writeFile(`${shotDir}/console.log`, consoleLogs.join("\n"), "utf8");
  await fs.writeFile(
    `${shotDir}/test-results.json`,
    JSON.stringify(
      {
        urlAfterCapture,
        unsyncedAfterCapture,
        unsyncedAfterWait,
      },
      null,
      2,
    ),
    "utf8",
  );
  console.log("EVIDENCE_DONE");
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
