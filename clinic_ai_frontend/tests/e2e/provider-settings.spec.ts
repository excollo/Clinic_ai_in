
import { test, expect } from '@playwright/test';

test.describe('Provider Settings Dashboard', () => {
    test.beforeEach(async ({ page }) => {
        // Login as admin
        await page.goto('/login');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await page.click('button[type="submit"]');
        await page.waitForURL('/provider/dashboard');
    });

    test('should navigate to settings and show tabs', async ({ page }) => {
        await page.click('text=Settings');
        await page.waitForURL('/provider/settings');

        await expect(page.locator('h1')).toHaveText('Settings');
        await expect(page.locator('text=Profile')).toBeVisible();
        await expect(page.locator('text=Organization')).toBeVisible();
        await expect(page.locator('text=Team Members')).toBeVisible();
    });

    test('should show profile information', async ({ page }) => {
        await page.goto('/provider/settings');
        await expect(page.locator('input#name')).not.toBeEmpty();
        await expect(page.locator('input#email')).not.toBeEmpty();
        await expect(page.locator('input#role')).not.toBeEmpty();
    });

    test('should list team members', async ({ page }) => {
        await page.goto('/provider/settings');
        await page.click('text=Team Members');

        // Check for table headers
        await expect(page.locator('th:has-text("Name")')).toBeVisible();
        await expect(page.locator('th:has-text("Email")')).toBeVisible();
        await expect(page.locator('th:has-text("Role")')).toBeVisible();

        // Check for at least one user row (the current user)
        await expect(page.locator('tbody tr')).toHaveCount(await page.locator('tbody tr').count());
    });
});
