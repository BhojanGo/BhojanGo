import { test as setup } from '@playwright/test';
import * as path from 'path';
import { takeScreenshot } from './utils';

const BASE_URL = 'http://localhost:3000';
const authFile = path.join(__dirname, '.auth', 'customer-state.json');

setup('authenticate as customer1', async ({ page }) => {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForLoadState('domcontentloaded');
  await takeScreenshot(page, 'auth-01-login-page.png');

  // Try different input selectors
  const emailInput = page.locator('input[name="email"], input[type="email"], input[placeholder*="email" i]').first();
  const passwordInput = page.locator('input[name="password"], input[type="password"]').first();

  await emailInput.fill('customer1@test.com');
  await takeScreenshot(page, 'auth-02-after-fill.png');

  await passwordInput.fill('Test1234!');
  await takeScreenshot(page, 'auth-03-password-filled.png');

  const submitBtn = page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Sign in")').first();
  await submitBtn.click();
  await page.waitForTimeout(5000);
  await takeScreenshot(page, 'auth-04-after-submit.png');

  await page.context().storageState({ path: authFile });
});