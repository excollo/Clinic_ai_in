import fs from "fs/promises";
import { chromium } from "@playwright/test";

const base = "http://localhost:5174";
const outFile = "artifacts/week4/badge-retest.log";

async function run() {
  await fs.mkdir("artifacts/week4", { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const lines = [];

  page.on("console", (msg) => {
    lines.push(msg.text());
  });

  await page.goto(`${base}/login`);
  await page.evaluate(() => {
    localStorage.setItem("clinic_api_key", "demo-api-key");
    localStorage.setItem("clinic_doctor_id", "doctor-opaque-001");
    localStorage.setItem("clinic_doctor_name", "Priya Sharma");
    localStorage.setItem("clinic_mobile", "9876543210");
    localStorage.removeItem("consent_sync_mock_attempt");
  });

  await page.goto(`${base}/consent/vis_badge_001`);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: /Capture consent/i }).click();
  await page.waitForTimeout(10000);
  await page.goto(`${base}/patients`);
  await page.waitForTimeout(22000);

  await fs.writeFile(outFile, lines.join("\n"), "utf8");
  await browser.close();
  console.log("BADGE_RETEST_DONE");
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
