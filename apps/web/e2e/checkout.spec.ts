import { test, expect } from '@playwright/test';
import { takeScreenshot } from './utils';

const BASE_URL = 'http://localhost:3000';

test('checkout flow', async ({ page }) => {
  // Pre-populate cart by visiting a restaurant and adding items
  await page.goto(`${BASE_URL}/restaurants`);
  await takeScreenshot(page, 'checkout-01-restaurants.png');

  // Find any clickable card/link to a restaurant
  const restaurantLinks = page.locator('a[href*="/restaurants/"]');
  const linkCount = await restaurantLinks.count();
  console.log(`Found ${linkCount} restaurant links`);

  if (linkCount > 0) {
    await restaurantLinks.first().click();
    await page.waitForLoadState('networkidle');
    await takeScreenshot(page, 'checkout-02-restaurant-detail.png');

    // Add items to cart
    try {
      const addButtons = page.getByRole('button', { name: /add to cart/i });
      const buttonCount = await addButtons.count();
      if (buttonCount > 0) {
        await addButtons.first().click();
        await page.waitForTimeout(1000);
        await takeScreenshot(page, 'checkout-03-item-added.png');
      }
    } catch {
      console.log('Could not add item to cart');
      await takeScreenshot(page, 'checkout-03-add-failed.png');
    }
  }

  // Navigate to /checkout
  await page.goto(`${BASE_URL}/checkout`);
  await page.waitForLoadState('networkidle');
  await takeScreenshot(page, 'checkout-04-checkout-page.png');

  // Fill delivery address form
  try {
    const addressInputs = page.locator('input').first();
    await addressInputs.fill('123 Test Street');
    await takeScreenshot(page, 'checkout-05-address-filled.png');
  } catch {
    console.log('Could not fill address fields');
    await takeScreenshot(page, 'checkout-05-address-failed.png');
  }

  // Click "Place Order"
  try {
    const placeOrderBtn = page.getByRole('button', { name: /place order/i });
    await expect(placeOrderBtn).toBeVisible({ timeout: 5000 });
    await placeOrderBtn.click();
    await page.waitForTimeout(2000);
    await takeScreenshot(page, 'checkout-06-after-place-order.png');
  } catch (e) {
    console.log('Place order button not found or failed');
    await takeScreenshot(page, 'checkout-06-place-order-failed.png');
  }
});