import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { takeScreenshot } from './utils';

const BASE_URL = 'http://localhost:3000';
const USER_URL = 'http://localhost:8001';
const RESTAURANT_URL = 'http://localhost:8002';
const ORDER_URL = 'http://localhost:8003';
const AUTH_STORAGE_KEY = 'bhojango-auth';

async function loginCustomer(request: APIRequestContext) {
  const response = await request.post(`${USER_URL}/api/v1/auth/login`, {
    data: { email: 'customer1@test.com', password: 'Test1234!' },
  });
  expect(response.status(), 'customer login must succeed for SPR-03C order flow').toBe(200);
  const auth = await response.json();
  expect(auth.access_token).toBeTruthy();
  expect(auth.refresh_token).toBeTruthy();
  expect(auth.user).toBeTruthy();
  return auth;
}

async function getRestaurantAndMenuItem(request: APIRequestContext) {
  const restaurantsResponse = await request.get(`${RESTAURANT_URL}/api/v1/restaurants?limit=10`);
  expect(restaurantsResponse.status(), 'restaurant list must be available').toBe(200);
  const restaurants = (await restaurantsResponse.json()).items ?? [];
  expect(restaurants.length, 'at least one seeded restaurant is required').toBeGreaterThan(0);

  for (const restaurant of restaurants) {
    const menuResponse = await request.get(`${RESTAURANT_URL}/api/v1/restaurants/${restaurant.id}/menu`);
    if (menuResponse.status() !== 200) continue;
    const menu = await menuResponse.json();
    const fromCategories = (menu.categories ?? []).flatMap((category: any) => category.items ?? []);
    const items = [...fromCategories, ...(menu.uncategorized_items ?? [])].filter((item: any) => item.is_available !== false);
    if (items.length > 0) return { restaurant, item: items[0] };
  }

  throw new Error('No restaurant with at least one available menu item found for SPR-03C order flow');
}

async function createCodOrder(request: APIRequestContext, token: string, restaurant: any, item: any) {
  const response = await request.post(`${ORDER_URL}/api/v1/orders`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'X-Idempotency-Key': crypto.randomUUID(),
    },
    data: {
      restaurant_id: restaurant.id,
      items: [{ menu_item_id: item.id, quantity: 1, customizations: [] }],
      delivery_address: {
        street: '123 SPR-03C Order Street',
        city: 'Bangalore',
        state: 'KA',
        zip: '560001',
        country: 'IN',
      },
      payment_method: 'cash_on_delivery',
    },
  });
  expect(response.status(), 'SPR-03C setup order creation must succeed').toBe(201);
  const order = await response.json();
  expect(order.id).toBeTruthy();
  expect(order.status).toBe('pending');
  expect(Number(order.total)).toBeGreaterThan(0);
  return order;
}

async function seedAuthBeforeNavigation(page: Page, auth: any) {
  await page.addInitScript(
    ({ authData, authKey }) => {
      window.localStorage.setItem(
        authKey,
        JSON.stringify({
          state: {
            accessToken: authData.access_token,
            refreshToken: authData.refresh_token,
            user: authData.user,
            isAuthenticated: true,
          },
          version: 0,
        })
      );
    },
    { authData: auth, authKey: AUTH_STORAGE_KEY }
  );
}

test('SPR-03C order list detail timeline and customer cancellation flow', async ({ page, request }) => {
  const auth = await loginCustomer(request);
  const { restaurant, item } = await getRestaurantAndMenuItem(request);
  const order = await createCodOrder(request, auth.access_token, restaurant, item);
  const shortOrderId = order.id.slice(0, 8).toUpperCase();

  await seedAuthBeforeNavigation(page, auth);
  await page.goto(`${BASE_URL}/orders`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');

  await expect(page.getByTestId('orders-ready')).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(new RegExp(shortOrderId, 'i'))).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/Pending|Order placed/i).first()).toBeVisible();
  await takeScreenshot(page, 'spr03c-order-list-with-created-order.png');

  await page.getByRole('link', { name: new RegExp(shortOrderId, 'i') }).click();
  await expect(page).toHaveURL(new RegExp(`/orders/${order.id}`));
  await expect(page.getByTestId('order-detail-ready')).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(new RegExp(shortOrderId, 'i'))).toBeVisible();
  await expect(page.getByText(item.name)).toBeVisible();
  await expect(page.locator('ol').getByText('Order placed')).toBeVisible();
  await expect(page.getByRole('button', { name: /^Cancel Order$/i })).toBeVisible();
  await expect(page.getByText(/Objects are not valid as a React child/i)).toHaveCount(0);
  await expect(page.getByText(/Unhandled Runtime Error/i)).toHaveCount(0);
  await takeScreenshot(page, 'spr03c-order-detail-before-cancel.png');

  const cancelResponsePromise = page.waitForResponse((response) =>
    response.url().includes(`/api/order/orders/${order.id}/cancel`) && response.request().method() === 'PATCH'
  );
  await page.getByRole('button', { name: /^Cancel Order$/i }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByPlaceholder(/Changed my mind/i).fill('SPR-03C customer cancellation proof');
  await page.getByRole('dialog').getByRole('button', { name: /^Cancel Order$/i }).click();
  const cancelResponse = await cancelResponsePromise;
  expect(cancelResponse.status(), 'customer cancellation PATCH must succeed').toBe(200);

  await expect(page.getByText('Order Cancelled', { exact: true })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/customer_cancelled/i)).toBeVisible();
  await expect(page.getByRole('button', { name: /^Cancel Order$/i })).toHaveCount(0);
  await expect(page.getByText(/Objects are not valid as a React child/i)).toHaveCount(0);
  await expect(page.getByText(/Unhandled Runtime Error/i)).toHaveCount(0);
  await takeScreenshot(page, 'spr03c-order-detail-cancelled.png');
});
