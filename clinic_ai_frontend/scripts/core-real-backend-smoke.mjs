import { chromium } from "@playwright/test";

const baseUrl = "http://127.0.0.1:5173";
const mobile = "9876543290";
const password = "StrongPass123";
const newPassword = "StrongPass456";

async function fillOtp(page, code = "123456") {
  for (let i = 0; i < 6; i += 1) {
    await page.locator(`#otp-${i}`).fill(code[i]);
  }
}

async function clickByText(page, text) {
  await page.getByRole("button", { name: text, exact: false }).first().click();
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  let visitUrl = "";

  await page.goto(`${baseUrl}/signup`);
  await page.locator('input[name="fullName"]').fill("Dr Core Flow");
  await page.getByLabel(/mobile/i).fill(mobile);
  await page.locator('input[name="email"]').fill("coreflow@example.com");
  await page.locator('input[name="regNo"]').fill("MCI12345");
  await page.locator('select[name="specialty"]').selectOption({ index: 1 });
  await page.locator('input[name="password"]').fill(password);
  await clickByText(page, "Continue");
  await fillOtp(page);
  await clickByText(page, "Verify");
  await page.locator('input[name="clinicName"]').fill("Core Clinic");
  await page.locator('input[name="city"]').fill("Delhi");
  await page.locator('input[name="pincode"]').fill("110001");
  await page.locator('input[name="opdStart"]').fill("09:00");
  await page.locator('input[name="opdEnd"]').fill("18:00");
  await page.locator('input[name="tokenPrefix"]').fill("OPD-");
  await clickByText(page, "Continue");
  await clickByText(page, "Skip");
  await clickByText(page, "Finish");
  await clickByText(page, "Skip");

  await page.goto(`${baseUrl}/login`);
  await page.getByLabel(/mobile/i).fill(mobile);
  await page.locator('input[type="password"]').fill(password);
  await clickByText(page, "Sign in");

  await page.goto(`${baseUrl}/forgot-password`);
  await page.getByLabel(/mobile/i).fill(mobile);
  await clickByText(page, "Send OTP");
  await fillOtp(page);
  await clickByText(page, "Verify");
  await page.locator('input[type="password"]').first().fill(newPassword);
  await page.locator('input[type="password"]').nth(1).fill(newPassword);
  await clickByText(page, "Continue");

  await page.goto(`${baseUrl}/login`);
  await page.getByLabel(/mobile/i).fill(mobile);
  await page.locator('input[type="password"]').fill(newPassword);
  await clickByText(page, "Sign in");

  await page.goto(`${baseUrl}/patients`);
  await clickByText(page, "Register");
  await page.locator('input[placeholder*="name" i]').fill("Ramesh Kumar");
  await page.locator('input[type="number"]').fill("45");
  await page.locator("select").first().selectOption("male");
  await page.locator('input[placeholder*="mobile" i]').fill("9876543288");
  await page.locator("select").nth(1).selectOption("hindi");
  await page.locator("textarea").fill("chest pain");
  await clickByText(page, "Continue");

  await page.waitForURL(/\/consent\//);
  visitUrl = page.url();
  await page.locator('input[type="checkbox"]').check();
  await clickByText(page, "Capture");
  await page.waitForURL(/\/walk-in-confirmation/);

  const visitId = visitUrl.split("/consent/")[1] ?? "";
  await page.goto(`${baseUrl}/visits/${visitId}`);
  await clickByText(page, "Continue");
  await page.waitForTimeout(2000);
  await page.locator('input[name="systolic"]').fill("120");
  await page.locator('input[name="diastolic"]').fill("80");
  await page.locator('input[name="weight"]').fill("70");
  await clickByText(page, "Save");
  await page.waitForTimeout(500);

  await browser.close();
  console.log("core smoke finished");
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
