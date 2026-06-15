import { test, expect, type Page } from '@playwright/test';
import { takeScreenshot } from './utils';

const BASE_URL = 'http://localhost:3000';
const CART_STORAGE_KEY = 'bhojango-cart-guest';

async function clearGuestCart(page: Page) {
  await page.goto(BASE_URL);
  await page.evaluate((key) => localStorage.removeItem(key), CART_STORAGE_KEY);
}

async function openRestaurantByIndex(page: Page, index: number) {
  await page.goto(`${BASE_URL}/restaurants`);
  await page.waitForLoadState('networkidle');

  const hrefs = await page.locator('a[href*="/restaurants/"]').evaluateAll((links) =>
    Array.from(
      new Set(
        links
          .map((link) => (link as HTMLAnchorElement).getAttribute('href'))
          .filter((href): href is string => Boolean(href))
      )
    )
  );

  expect(hrefs.length, 'expected enough restaurant links').toBeGreaterThan(index);
  const href = hrefs[index];
  expect(href, `expected restaurant link at index ${index}`).toBeTruthy();
  if (!href) {
    throw new Error(`Restaurant link at index ${index} was not found`);
  }

  await page.goto(new URL(href, BASE_URL).toString());
  await page.waitForLoadState('networkidle');
}

async function addFirstVisibleMenuItem(page: Page) {
  const addButton = page.getByRole('button', { name: /add to cart|add/i }).first();
  await expect(addButton, 'expected at least one add-to-cart button').toBeVisible({ timeout: 15000 });
  await addButton.click();
}

async function readCartStorage(page: Page) {
  return page.evaluate((key) => {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  }, CART_STORAGE_KEY);
}

async function seedGuestCart(page: Page, price = 150, quantity = 1) {
  await page.goto(BASE_URL);
  await page.evaluate(
    ({ key, seededPrice, seededQuantity }) => {
      localStorage.setItem(
        key,
        JSON.stringify({
          state: {
            schemaVersion: 1,
            updatedAt: new Date().toISOString(),
            restaurantId: 'spr03a-seeded-restaurant',
            restaurantName: 'SPR-03A Seeded Restaurant',
            restaurantSlug: 'spr03a-seeded-restaurant',
            currency: 'INR',
            items: [
              {
                menuItemId: 'spr03a-seeded-item',
                name: 'SPR-03A Seeded Item',
                price: seededPrice,
                quantity: seededQuantity,
                customizations: [],
                isVeg: true,
              },
            ],
            deliveryFee: 30,
            discountAmount: 0,
          },
          version: 1,
        })
      );
    },
    { key: CART_STORAGE_KEY, seededPrice: price, seededQuantity: quantity }
  );
}

// SPR-03A-FIX2B hydration overlay assertion: the clean evidence screenshot must not hide a real Next.js hydration error.
async function expectNoHydrationDevOverlay(page: Page) {
  await expect(page.getByText(/Hydration failed/i)).toHaveCount(0);
  await expect(page.getByText(/^1 error$/i)).toHaveCount(0);
  await expect(page.locator('nextjs-portal')).toHaveCount(0);
}

test.beforeEach(async ({ page }) => {
  await clearGuestCart(page);
});

test('SPR-03A empty cart state renders browse CTA', async ({ page }) => {
  await page.goto(`${BASE_URL}/cart`);
  await page.waitForLoadState('networkidle');

  await expect(page.getByRole('link', { name: /browse restaurants/i })).toBeVisible();
  await takeScreenshot(page, 'spr03a-cart-empty.png');
});

test('SPR-03A guest cart persists after refresh and shows full fee breakdown', async ({ page }) => {
  await openRestaurantByIndex(page, 0);
  await addFirstVisibleMenuItem(page);

  await expect
    .poll(async () => {
      const stored = await readCartStorage(page);
      return stored?.state?.items?.length ?? 0;
    })
    .toBeGreaterThan(0);

  await page.goto(`${BASE_URL}/cart`);
  await page.waitForLoadState('networkidle');

  await expect(page.getByText(/Bill Summary/i)).toBeVisible();
  await expect(page.getByText(/Items Total/i)).toBeVisible();
  await expect(page.getByText(/Delivery Fee/i)).toBeVisible();
  await expect(page.getByText(/Platform Fee/i)).toBeVisible();
  await expect(page.getByText(/Tax \/ GST \(5%\)/i)).toBeVisible();
  await expect(page.getByText(/Discount/i)).toBeVisible();
  await expect(page.getByText(/Grand Total/i)).toBeVisible();
  await takeScreenshot(page, 'spr03a-cart-populated.png');

  await page.reload();
  await page.waitForLoadState('networkidle');

  const storedAfterRefresh = await readCartStorage(page);
  expect(storedAfterRefresh?.state?.items?.length).toBeGreaterThan(0);
  await expect(page.getByText(/Grand Total/i)).toBeVisible();
});


test('SPR-03A checkout entry redirects unauthenticated users while preserving cart and INR fee slab', async ({ page }) => {
  await seedGuestCart(page, 150, 1);

  await page.goto(`${BASE_URL}/cart`);
  await page.waitForLoadState('networkidle');

  await expect(page.getByText(/Bill Summary/i)).toBeVisible();
  await expect(page.getByText(/Delivery Fee/i)).toBeVisible();
  await expect(page.getByText('₹50.00')).toBeVisible();

  await page.getByRole('button', { name: /increase quantity/i }).first().click();

  await expect
    .poll(async () => {
      const stored = await readCartStorage(page);
      return stored?.state?.items?.[0]?.quantity ?? 0;
    })
    .toBe(2);

  await expect(page.getByText('₹30.00')).toBeVisible();
  await expectNoHydrationDevOverlay(page);
  await takeScreenshot(page, 'spr03a-checkout-entry-summary.png');

  await page.getByRole('button', { name: /proceed to checkout|checkout/i }).click();
  await expect(page).toHaveURL(/\/login\?redirect=(%2F|\/)checkout/);

  const storedAfterRedirect = await readCartStorage(page);
  expect(storedAfterRedirect?.state?.items?.length).toBe(1);
  expect(storedAfterRedirect?.state?.items?.[0]?.quantity).toBe(2);
  expect(storedAfterRedirect?.state?.restaurantId).toBe('spr03a-seeded-restaurant');

  const emailInput = page.locator('input[name="email"], input[type="email"], input[placeholder*="email" i]').first();
  await expect(emailInput).toBeVisible({ timeout: 15000 });
});

test('SPR-03A quantity stepper updates persisted quantity and totals', async ({ page }) => {
  await openRestaurantByIndex(page, 0);
  await addFirstVisibleMenuItem(page);
  await page.goto(`${BASE_URL}/cart`);
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: /increase quantity/i }).first().click();

  await expect
    .poll(async () => {
      const stored = await readCartStorage(page);
      return stored?.state?.items?.[0]?.quantity ?? 0;
    })
    .toBeGreaterThanOrEqual(2);

  await expect(page.getByText(/Grand Total/i)).toBeVisible();
  await takeScreenshot(page, 'spr03a-cart-quantity-update.png');

  await page.getByRole('button', { name: /decrease quantity/i }).first().click();
  await page.getByRole('button', { name: /decrease quantity/i }).first().click();

  await expect
    .poll(async () => {
      const stored = await readCartStorage(page);
      return stored?.state?.items?.length ?? 0;
    })
    .toBe(0);
});

test('SPR-03A cross-restaurant guard supports cancel and start-new-cart', async ({ page }) => {
  await openRestaurantByIndex(page, 0);
  await addFirstVisibleMenuItem(page);

  const firstCart = await readCartStorage(page);
  const firstRestaurantId = firstCart?.state?.restaurantId;
  expect(firstRestaurantId).toBeTruthy();

  await openRestaurantByIndex(page, 1);
  await addFirstVisibleMenuItem(page);

  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByText(/Your cart has items from/i)).toBeVisible();
  await takeScreenshot(page, 'spr03a-cross-restaurant-guard.png');

  await page.getByRole('button', { name: /^cancel$/i }).click();
  await expect(page.getByRole('dialog')).toBeHidden();

  const afterCancel = await readCartStorage(page);
  expect(afterCancel?.state?.restaurantId).toBe(firstRestaurantId);

  await addFirstVisibleMenuItem(page);
  await page.getByRole('button', { name: /start new cart/i }).click();

  await expect
    .poll(async () => {
      const stored = await readCartStorage(page);
      return stored?.state?.restaurantId;
    })
    .not.toBe(firstRestaurantId);

  const afterReplace = await readCartStorage(page);
  expect(afterReplace?.state?.items?.length).toBe(1);
});
