import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

import { takeScreenshot } from './utils';

const BASE_URL = 'http://localhost:3000';
const USER_URL = 'http://localhost:8001';
const AUTH_STORAGE_KEY = 'bhojango-auth';

async function loginCustomer(request: APIRequestContext) {
  const response = await request.post(`${USER_URL}/api/v1/auth/login`, {
    data: { email: 'customer1@test.com', password: 'Test1234!' },
  });
  expect(response.status(), 'customer login must succeed for SPR-03B-WALLET-01').toBe(200);
  const auth = await response.json();
  expect(auth.access_token).toBeTruthy();
  expect(auth.refresh_token).toBeTruthy();
  expect(auth.user).toBeTruthy();
  return auth;
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

async function numericBalance(page: Page) {
  const value = await page.getByTestId('wallet-balance').getAttribute('data-balance');
  expect(value, 'wallet balance data attribute must exist').toBeTruthy();
  return Number(value);
}

test('SPR-03B-WALLET-01 wallet seed, dummy top-up, and ledger render', async ({ page, request }) => {
  const auth = await loginCustomer(request);
  await seedAuthBeforeNavigation(page, auth);

  await page.goto(`${BASE_URL}/wallet`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveURL(/\/wallet$/);
  await expect(page.getByTestId('wallet-ready')).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('heading', { name: /^Wallet$/i })).toBeVisible();
  await expect(page.getByText(/Current Balance/i)).toBeVisible();

  const before = await numericBalance(page);
  expect(Number.isFinite(before)).toBeTruthy();

  await page.getByLabel(/Top-up amount/i).fill('25');
  await page.getByRole('button', { name: /^Add Money$/i }).click();
  await expect(page.getByText(/Wallet topped up by/i)).toBeVisible({ timeout: 15000 });

  const after = await numericBalance(page);
  expect(after).toBeGreaterThanOrEqual(before + 24.99);
  await expect(page.getByTestId('wallet-transactions').getByText(/Demo wallet top-up/i).first()).toBeVisible({ timeout: 15000 });

  await expect(page.getByText(/Objects are not valid as a React child/i)).toHaveCount(0);
  await expect(page.getByText(/Unhandled Runtime Error/i)).toHaveCount(0);
  await takeScreenshot(page, 'spr03b-wallet-seed-topup-ledger.png');
});
