import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { takeScreenshot } from './utils';

const BASE_URL = 'http://localhost:3000';
const USER_URL = 'http://localhost:8001';
const RESTAURANT_URL = 'http://localhost:8002';
const PAYMENT_URL = 'http://localhost:8005';
const CART_STORAGE_KEY = 'bhojango-cart-guest';
const AUTH_STORAGE_KEY = 'bhojango-auth';

async function loginCustomer(request: APIRequestContext) {
  const response = await request.post(`${USER_URL}/api/v1/auth/login`, {
    data: { email: 'customer1@test.com', password: 'Test1234!' },
  });
  expect(response.status(), 'customer login must succeed for SPR-03B checkout contract').toBe(200);
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
    if (items.length > 0) {
      return { restaurant, item: items[0] };
    }
  }

  throw new Error('No restaurant with at least one available menu item found for SPR-03B checkout contract');
}

async function seedAuthAndCartBeforeNavigation(page: Page, auth: any, restaurant: any, item: any) {
  await page.addInitScript(
    ({ authData, restaurantData, itemData, authKey, cartKey }) => {
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

      window.localStorage.setItem(
        cartKey,
        JSON.stringify({
          state: {
            schemaVersion: 1,
            updatedAt: new Date().toISOString(),
            restaurantId: restaurantData.id,
            restaurantName: restaurantData.name,
            restaurantSlug: restaurantData.slug,
            currency: restaurantData.currency ?? 'INR',
            items: [
              {
                menuItemId: itemData.id,
                name: itemData.name,
                price: Number(itemData.price),
                quantity: 1,
                customizations: [],
                isVeg: Boolean(itemData.is_veg),
              },
            ],
            deliveryFee: Number(restaurantData.delivery_fee ?? 0),
            discountAmount: 0,
          },
          version: 1,
        })
      );
    },
    {
      authData: auth,
      restaurantData: restaurant,
      itemData: item,
      authKey: AUTH_STORAGE_KEY,
      cartKey: CART_STORAGE_KEY,
    }
  );
}

async function ensureAddress(page: Page) {
  await expect(page.getByRole('heading', { name: /^Delivery Address$/i })).toBeVisible({ timeout: 15000 });
  const existingAddressRadio = page.locator('input[name="address"]').first();
  if ((await existingAddressRadio.count()) > 0) {
    await existingAddressRadio.check();
    return;
  }

  await page.getByRole('button', { name: /add delivery address/i }).click();
  await page.locator('input[placeholder*="Label" i]').fill('SPR-03B Home');
  await page.locator('input[placeholder*="Street" i]').fill('123 SPR-03B Contract Street');
  await page.locator('input[placeholder*="City" i]').fill('Bangalore');
  await page.locator('input[placeholder*="State" i]').fill('KA');
  await page.locator('input[placeholder*="Postal" i]').fill('560001');
  await page.getByRole('button', { name: /save address/i }).click();
  await expect(page.locator('input[name="address"]').first()).toBeChecked({ timeout: 15000 });
}

test('SPR-03B authenticated checkout creates order and reaches simulated payment contract', async ({ page, request }) => {
  const auth = await loginCustomer(request);
  const { restaurant, item } = await getRestaurantAndMenuItem(request);

  await seedAuthAndCartBeforeNavigation(page, auth, restaurant, item);
  await page.goto(`${BASE_URL}/checkout`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');

  const seededStorage = await page.evaluate(
    ({ authKey, cartKey }) => ({
      auth: window.localStorage.getItem(authKey),
      cart: window.localStorage.getItem(cartKey),
    }),
    { authKey: AUTH_STORAGE_KEY, cartKey: CART_STORAGE_KEY }
  );
  expect(seededStorage.auth, 'auth localStorage must be seeded before checkout hydration').toBeTruthy();
  expect(seededStorage.cart, 'cart localStorage must be seeded before checkout hydration').toBeTruthy();

  await expect(page).toHaveURL(/\/checkout$/);
  await expect(page.getByTestId('checkout-ready')).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/Order Summary/i)).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/Grand Total/i)).toBeVisible();

  await ensureAddress(page);

  const cardOption = page.locator('input[name="payment"][value="card"]').first();
  await expect(cardOption).toBeVisible();
  await cardOption.check();

  const orderResponsePromise = page.waitForResponse((response) =>
    response.url().includes('/api/order/orders') && response.request().method() === 'POST'
  );
  const paymentResponsePromise = page.waitForResponse((response) =>
    response.url().includes('/api/payment/payments/initiate') && response.request().method() === 'POST'
  );

  await page.getByRole('button', { name: /place order/i }).click();

  const orderResponse = await orderResponsePromise;
  expect(orderResponse.status(), 'order creation must succeed').toBe(201);
  const order = await orderResponse.json();
  expect(order.id).toBeTruthy();
  expect(order.status).toBe('pending');
  expect(Number(order.total)).toBeGreaterThan(0);

  const paymentResponse = await paymentResponsePromise;
  expect(paymentResponse.status(), 'simulated payment initiation must succeed').toBe(201);
  const payment = await paymentResponse.json();
  expect(payment.provider).toBe('mock');
  expect(payment.payment_intent_id).toBeTruthy();

  await expect(page).toHaveURL(/\/checkout\/payment\?/);
  await expect(page.getByText(/Payment simulated/i)).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/SPR-03B order\/payment contract/i)).toBeVisible();
  await expect(page.getByText(/Objects are not valid as a React child/i)).toHaveCount(0);
  await expect(page.getByText(/Unhandled Runtime Error/i)).toHaveCount(0);
  await takeScreenshot(page, 'spr03b-simulated-payment-contract.png');
});

test('SPR-03B wallet object-detail failure renders safe checkout error', async ({ page, request }) => {
  const auth = await loginCustomer(request);
  const { restaurant, item } = await getRestaurantAndMenuItem(request);

  await page.route('**/api/payment/payments/initiate', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }

    await route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: {
          code: 'INSUFFICIENT_WALLET_BALANCE',
          message: 'Insufficient wallet balance',
        },
      }),
    });
  });

  await seedAuthAndCartBeforeNavigation(page, auth, restaurant, item);
  await page.goto(`${BASE_URL}/checkout`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');

  await expect(page.getByTestId('checkout-ready')).toBeVisible({ timeout: 15000 });
  await ensureAddress(page);

  const walletOption = page.locator('input[name="payment"][value="wallet"]').first();
  await expect(walletOption).toBeVisible();
  await walletOption.check();

  const paymentFailurePromise = page.waitForResponse((response) =>
    response.url().includes('/api/payment/payments/initiate') && response.status() === 400
  );

  await page.getByRole('button', { name: /place order/i }).click();
  await paymentFailurePromise;

  await expect(page.getByText(/Insufficient wallet balance/i)).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/Objects are not valid as a React child/i)).toHaveCount(0);
  await expect(page.getByText(/Unhandled Runtime Error/i)).toHaveCount(0);

  await takeScreenshot(page, 'spr03b-wallet-error-safe.png');
});

async function getWalletBalance(request: APIRequestContext, token: string) {
  const response = await request.get(`${PAYMENT_URL}/api/v1/wallet/balance`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.status(), 'wallet balance must be available').toBe(200);
  return response.json();
}

async function topUpWallet(request: APIRequestContext, token: string, amount: number, currency: string) {
  const response = await request.post(`${PAYMENT_URL}/api/v1/wallet/topup`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { amount, currency, payment_method_id: 'spr03b_wallet01_checkout_topup' },
  });
  expect(response.status(), 'wallet dummy top-up must succeed').toBe(200);
  return response.json();
}

async function getWalletTransactions(request: APIRequestContext, token: string) {
  const response = await request.get(`${PAYMENT_URL}/api/v1/wallet/transactions?limit=50`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.status(), 'wallet transaction ledger must be available').toBe(200);
  return response.json();
}

test('SPR-03B-WALLET-01 wallet checkout debits balance and records transaction', async ({ page, request }) => {
  const auth = await loginCustomer(request);
  const { restaurant, item } = await getRestaurantAndMenuItem(request);
  const seededBalance = await getWalletBalance(request, auth.access_token);
  const currency = seededBalance.currency ?? (auth.user?.country === 'IN' ? 'INR' : 'USD');
  const toppedUpBalance = await topUpWallet(request, auth.access_token, 100, currency);
  const startingBalance = Number(toppedUpBalance.balance);

  await seedAuthAndCartBeforeNavigation(page, auth, restaurant, item);
  await page.goto(`${BASE_URL}/checkout`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');

  await expect(page.getByTestId('checkout-ready')).toBeVisible({ timeout: 15000 });
  await ensureAddress(page);

  const walletOption = page.locator('input[name="payment"][value="wallet"]').first();
  await expect(walletOption).toBeVisible();
  await walletOption.check();

  const orderResponsePromise = page.waitForResponse((response) =>
    response.url().includes('/api/order/orders') && response.request().method() === 'POST'
  );
  const paymentResponsePromise = page.waitForResponse((response) =>
    response.url().includes('/api/payment/payments/initiate') && response.request().method() === 'POST'
  );

  await page.getByRole('button', { name: /place order/i }).click();

  const orderResponse = await orderResponsePromise;
  expect(orderResponse.status(), 'wallet checkout order creation must succeed').toBe(201);
  const order = await orderResponse.json();
  const orderTotal = Number(order.total);
  expect(orderTotal).toBeGreaterThan(0);

  const paymentResponse = await paymentResponsePromise;
  expect(paymentResponse.status(), 'wallet payment initiation must succeed').toBe(201);
  const payment = await paymentResponse.json();
  expect(payment.provider).toBe('wallet');

  await expect(page).toHaveURL(/\/orders\//, { timeout: 15000 });

  const endingBalance = await getWalletBalance(request, auth.access_token);
  expect(Math.abs(Number(endingBalance.balance) - (startingBalance - orderTotal))).toBeLessThan(0.05);

  const ledger = await getWalletTransactions(request, auth.access_token);
  const debit = (ledger.items ?? []).find((txn: any) => txn.reference_id === order.id && txn.reference_type === 'order');
  expect(debit, 'wallet order debit transaction must be present').toBeTruthy();
  expect(debit.type).toBe('debit');
  expect(Math.abs(Number(debit.amount) - orderTotal)).toBeLessThan(0.05);

  await expect(page.getByText(/Objects are not valid as a React child/i)).toHaveCount(0);
  await expect(page.getByText(/Unhandled Runtime Error/i)).toHaveCount(0);
});

