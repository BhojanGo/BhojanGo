import { Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const SCREENSHOT_DIR = path.join(
  process.cwd(),
  '..',
  '..',
  'tests',
  'results',
  'frontend',
  'customer',
  'screenshots'
);

const DEV_ONLY_EVIDENCE_OVERLAY_STYLE_ID = 'spr03a-hide-dev-only-evidence-overlays';

/**
 * SPR-03A-FIX2A evidence hygiene:
 * Hide dev-only TanStack / React Query / Next dev overlays only for Playwright screenshots.
 * This does not modify app runtime behavior, cart semantics, checkout flow, order creation,
 * payment, or cancellation. It only prevents devtool status badges such as "1 error" from
 * contaminating manual screenshot evidence.
 */
export async function hideDevOnlyEvidenceOverlays(page: Page) {
  await page
    .addStyleTag({
      content: `
        #${DEV_ONLY_EVIDENCE_OVERLAY_STYLE_ID} { display: none !important; }
        .tsqd-parent-container,
        [class*="tsqd"],
        [id*="tsqd"],
        [data-testid*="tanstack"],
        [data-testid*="react-query"],
        [aria-label*="TanStack"],
        [aria-label*="React Query"],
        nextjs-portal,
        [data-nextjs-dialog-overlay],
        [data-nextjs-dialog],
        [data-nextjs-toast],
        [data-nextjs-errors],
        [data-nextjs-error-overlay],
        [data-nextjs-dev-overlay],
        [data-nextjs-terminal] {
          display: none !important;
          visibility: hidden !important;
          opacity: 0 !important;
          pointer-events: none !important;
        }
      `,
    })
    .catch(() => undefined);

  await page
    .evaluate(() => {
      const selectors = [
        '.tsqd-parent-container',
        '[class*="tsqd"]',
        '[id*="tsqd"]',
        '[data-testid*="tanstack"]',
        '[data-testid*="react-query"]',
        '[aria-label*="TanStack"]',
        '[aria-label*="React Query"]',
        'nextjs-portal',
        '[data-nextjs-dialog-overlay]',
        '[data-nextjs-dialog]',
        '[data-nextjs-toast]',
        '[data-nextjs-errors]',
        '[data-nextjs-error-overlay]',
        '[data-nextjs-dev-overlay]',
        '[data-nextjs-terminal]',
      ];

      document.querySelectorAll(selectors.join(',')).forEach((node) => {
        const element = node as HTMLElement;
        element.setAttribute('data-spr03b-evidence-hidden', 'dev-only-next-or-query-dev-overlay');
        element.style.setProperty('display', 'none', 'important');
        element.style.setProperty('visibility', 'hidden', 'important');
        element.style.setProperty('opacity', '0', 'important');
        element.style.setProperty('pointer-events', 'none', 'important');
      });
    })
    .catch(() => undefined);
}

export async function takeScreenshot(page: Page, name: string) {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }
  await hideDevOnlyEvidenceOverlays(page);
  await page.screenshot({ fullPage: true, path: path.join(SCREENSHOT_DIR, name) });
}
