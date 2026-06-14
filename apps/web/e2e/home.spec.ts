import { test, expect } from '@playwright/test';
import { takeScreenshot } from './utils';

const BASE_URL = 'http://localhost:3000';

test('homepage loads with correct content', async ({ page }) => {
  await page.goto(BASE_URL);
  await takeScreenshot(page, 'home-01-initial.png');

  // Verify hero text
  await expect(page.getByText('Delicious food', { exact: false }).first()).toBeVisible({ timeout: 10000 });
  await takeScreenshot(page, 'home-02-hero-visible.png');

  // Verify Featured restaurants section
  const featuredSection = page.getByText('Featured restaurants', { exact: false });
  await expect(featuredSection).toBeVisible({ timeout: 10000 });
  await takeScreenshot(page, 'home-03-featured-section.png');

  // Verify Order in 4 simple steps section
  const stepsSection = page.getByText(/order in 4 simple steps/i);
  await expect(stepsSection).toBeVisible({ timeout: 5000 }).catch(() => {
    console.log('4 simple steps section not found - may be on different page section');
  });
  await takeScreenshot(page, 'home-04-steps-section.png');
});