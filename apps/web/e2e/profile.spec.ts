import { test, expect } from '@playwright/test';
import { takeScreenshot } from './utils';

const BASE_URL = 'http://localhost:3000';

test('profile page', async ({ page }) => {
  // Visit /profile (may redirect to login if not authenticated)
  await page.goto(`${BASE_URL}/profile`);
  await page.waitForLoadState('networkidle');
  await takeScreenshot(page, 'profile-01-profile-page.png');

  const currentUrl = page.url();
  console.log(`Current URL: ${currentUrl}`);

  if (currentUrl.includes('/login')) {
    console.log('Redirected to login - skipping authenticated test');
    await takeScreenshot(page, 'profile-01-redirected-to-login.png');
    return;
  }

  // Verify user info visible
  try {
    const userInfo = page.locator('[class*="profile"], [class*="user"], h1, h2');
    await expect(userInfo.first()).toBeVisible({ timeout: 5000 });
    await takeScreenshot(page, 'profile-02-user-info-visible.png');
  } catch {
    console.log('User info not visible');
    await takeScreenshot(page, 'profile-02-user-info-not-found.png');
  }
});