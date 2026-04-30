import { test, expect } from '@playwright/test';

test('homepage loads successfully', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/AI Healthcare Platform/);
    // Check for main heading or key element
    await expect(page.locator('h1')).toBeVisible();
});
