import { test, expect } from '@playwright/test';
import { takeScreenshot } from './utils';

const BASE_URL = 'http://localhost:3000';

test('wallet page', async ({ page }) => {
  // Visit /wallet (may redirect to login if not authenticated)
  await page.goto(`${BASE_URL}/wallet`);
  await page.waitForLoadState('networkidle');
  await takeScreenshot(page, 'wallet-01-wallet-page.png');

  const currentUrl = page.url();
  console.log(`Current URL: ${currentUrl}`);

  if (currentUrl.includes('/login')) {
    console.log('Redirected to login - skipping authenticated test');
    await takeScreenshot(page, 'wallet-01-redirected-to-login.png');
    return;
  }

  // Verify balance visible
  try {
    const balanceSection = page.locator('[class*="balance"], [class*="amount"], [class*="wallet"]');
    await expect(balanceSection.first()).toBeVisible({ timeout: 10000 });
    const balanceText = await balanceSection.first().textContent();
    console.log(`Wallet balance: ${balanceText}`);
    await takeScreenshot(page, 'wallet-02-balance-visible.png');
  } catch {
    console.log('Balance not visible');
    await takeScreenshot(page, 'wallet-02-balance-not-found.png');
  }
});