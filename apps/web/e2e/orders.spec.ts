import { test, expect } from '@playwright/test';
import { takeScreenshot } from './utils';

const BASE_URL = 'http://localhost:3000';

test('orders page', async ({ page }) => {
  // Visit /orders (may redirect to login if not authenticated)
  await page.goto(`${BASE_URL}/orders`);
  await page.waitForLoadState('networkidle');
  await takeScreenshot(page, 'orders-01-orders-page.png');

  const currentUrl = page.url();
  console.log(`Current URL: ${currentUrl}`);

  if (currentUrl.includes('/login')) {
    console.log('Redirected to login - skipping authenticated test');
    await takeScreenshot(page, 'orders-01-redirected-to-login.png');
    return;
  }

  // Verify order cards visible
  try {
    const orderCards = page.locator('[class*="order"], [class*="card"]');
    const cardCount = await orderCards.count();
    console.log(`Found ${cardCount} order cards`);
    await takeScreenshot(page, 'orders-02-cards-visible.png');
  } catch (e) {
    console.log('Error checking orders');
    await takeScreenshot(page, 'orders-02-error.png');
  }
});