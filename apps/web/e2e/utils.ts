import { Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const SCREENSHOT_DIR = path.join(process.cwd(), '..', '..', 'tests', 'results', 'playwright', 'screenshots');

export async function takeScreenshot(page: Page, name: string) {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }
  await page.screenshot({ fullPage: true, path: path.join(SCREENSHOT_DIR, name) });
}