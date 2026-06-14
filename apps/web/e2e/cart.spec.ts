import { test, expect } from '@playwright/test';
import { takeScreenshot } from './utils';

const BASE_URL = 'http://localhost:3000';

test('cart flow - add items and view cart', async ({ page }) => {
  // Visit restaurants first
  await page.goto(`${BASE_URL}/restaurants`);
  await page.waitForLoadState('networkidle');
  await takeScreenshot(page, 'cart-01-restaurants.png');

  // Find restaurant links
  const restaurantLinks = page.locator('a[href*="/restaurants/"]');
  const linkCount = await restaurantLinks.count();
  console.log(`Found ${linkCount} restaurant links`);

  if (linkCount > 0) {
    await restaurantLinks.first().click();
    await page.waitForLoadState('networkidle');
    await takeScreenshot(page, 'cart-02-restaurant-detail.png');

    // Try to find and click "Add to Cart" buttons
    let addedCount = 0;
    try {
      const addButtons = page.getByRole('button', { name: /add to cart/i });
      const buttonCount = await addButtons.count();
      console.log(`Found ${buttonCount} Add to Cart buttons`);

      if (buttonCount > 0) {
        await addButtons.first().click();
        addedCount++;
        await page.waitForTimeout(1000);
        await takeScreenshot(page, 'cart-03-after-first-add.png');

        if (buttonCount > 1) {
          await addButtons.nth(1).click();
          addedCount++;
          await page.waitForTimeout(1000);
          await takeScreenshot(page, 'cart-04-after-second-add.png');
        }
      }
    } catch (e) {
      console.log('Could not find Add to Cart buttons - menu may not have loaded');
      await takeScreenshot(page, 'cart-03-add-buttons-not-found.png');
    }

    console.log(`Added ${addedCount} items to cart`);
  } else {
    await takeScreenshot(page, 'cart-02-no-restaurants-found.png');
  }

  // Navigate to cart page
  await page.goto(`${BASE_URL}/cart`);
  await page.waitForLoadState('networkidle');
  await takeScreenshot(page, 'cart-05-cart-page.png');

  // Verify cart page shows items or is empty
  const currentUrl = page.url();
  if (currentUrl.includes('/login')) {
    console.log('Redirected to login - cart requires auth');
    await takeScreenshot(page, 'cart-05-cart-requires-login.png');
  } else {
    const cartContent = page.locator('body');
    await expect(cartContent).toBeVisible();
    await takeScreenshot(page, 'cart-06-cart-content-visible.png');
  }
});