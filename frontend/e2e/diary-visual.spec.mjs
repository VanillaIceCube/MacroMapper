import { test, expect } from '@playwright/test';

const sampleItems = [
  {
    id: 21,
    food_name: 'Apple',
    servings: '1.0000',
    provider_name: '',
    serving_label: 'one apple',
    provenance: 'user_entered',
    confidence_score: null,
    nutrients: [{ key: 'calories', amount: '95.0000' }],
  },
  {
    id: 22,
    food_name: 'Roasted vegetables with brown rice and a lemon herb dressing',
    servings: '2.0000',
    provider_name: 'Example Kitchen',
    serving_label: 'one bowl with vegetables, rice, and dressing served on the side',
    provenance: 'ai_estimate',
    confidence_score: '0.910',
    nutrients: [{ key: 'calories', amount: '320.0000' }],
  },
];

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('accessToken', 'visual-test-placeholder');
    sessionStorage.setItem('email', 'visual-test@example.test');
    sessionStorage.setItem('username', 'Visual Test');
    const showPicker = HTMLInputElement.prototype.showPicker;
    window.diaryPickerRequests = 0;
    HTMLInputElement.prototype.showPicker = function () {
      window.diaryPickerRequests += 1;
      return showPicker?.call(this);
    };
  });
  // Intercept before navigation, including remote verification. Unexpected API
  // requests are aborted, so placeholder credentials never reach the server.
  await page.route(/\/(api|auth)\//, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() === 'GET' && url.pathname === '/api/meals/daily/') {
      await route.fulfill({
        json: {
          date: url.searchParams.get('date'),
          totals: [{ key: 'calories', name: 'Calories', unit: 'kcal', amount: '415' }],
          meals: [
            {
              id: 11,
              name: 'Sample lunch',
              entry_date: url.searchParams.get('date'),
              notes: '',
              confidence_score: null,
              items: sampleItems,
            },
          ],
        },
      });
    } else if (request.method() === 'GET' && url.pathname === '/api/notifications/') {
      await route.fulfill({ json: [] });
    } else {
      await route.abort('blockedbyclient');
    }
  });
});

const bounds = async (locator) => {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  return box;
};
const centerY = (box) => box.y + box.height / 2;

const expectNoOverflow = async (page, width) => {
  const layout = await page.evaluate(() => ({
    width: document.documentElement.scrollWidth,
    overflow: [...document.querySelectorAll('body *')]
      .filter((element) => element.getBoundingClientRect().right > innerWidth + 0.5)
      .map((element) => `${element.tagName}: ${element.textContent.slice(0, 100)}`)
      .slice(0, 10),
  }));
  expect(layout.width, JSON.stringify(layout.overflow)).toBeLessThanOrEqual(width);
};

for (const width of [320, 375, 600, 768, 1024, 1440]) {
  test(`date picker anchor at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/diary');
    const table = page.getByRole('table', { name: 'Sample lunch food breakdown' });
    await expect(table).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    const control = page.getByTestId('diary-date-control');
    const trigger = page.getByRole('button', { name: /^choose diary date/ });
    const input = page.getByLabel('diary date', { exact: true });
    const initialControl = await bounds(control);

    const checkAnchor = async () => {
      const buttonBox = await bounds(trigger);
      const inputBox = await bounds(input);
      for (const key of ['x', 'y', 'width', 'height']) {
        expect(Math.abs(inputBox[key] - buttonBox[key]), `input ${key}`).toBeLessThan(1);
      }
      const headerBox = await bounds(page.getByTestId('diary-header'));
      const controlBox = await bounds(control);
      expect(
        Math.abs(controlBox.x + controlBox.width - headerBox.x - headerBox.width),
      ).toBeLessThan(1);
      expect(controlBox.x).toBeGreaterThanOrEqual(0);
      expect(controlBox.x + controlBox.width).toBeLessThanOrEqual(width);
    };

    await checkAnchor();
    await trigger.click();
    expect(await page.evaluate(() => window.diaryPickerRequests)).toBe(1);
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: 'previous day', exact: true }).click();
    await expect(page.getByRole('button', { name: 'return to today' })).toBeVisible();
    await checkAnchor();
    expect((await bounds(control)).x).toBeCloseTo(initialControl.x, 0);
    await page.getByRole('button', { name: 'next day', exact: true }).click();
    await expect(page.getByRole('button', { name: 'return to today' })).toHaveCount(0);
    await page.getByRole('button', { name: 'previous day', exact: true }).click();
    await page.getByRole('button', { name: 'return to today' }).click();
    await checkAnchor();
    expect((await bounds(control)).x).toBeCloseTo(initialControl.x, 0);
    await input.fill('2026-08-16');
    await expect(trigger).toHaveAccessibleName('choose diary date, current date 2026-08-16');
    await checkAnchor();
    await expect(table).toBeVisible();
    await expectNoOverflow(page, width);

    await page.screenshot({ path: testInfo.outputPath(`date-${width}.png`), fullPage: true });
    await testInfo.attach(`date-${width}`, {
      path: testInfo.outputPath(`date-${width}.png`),
      contentType: 'image/png',
    });
  });

  test(`food cells at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/diary');
    const table = page.getByRole('table', { name: 'Sample lunch food breakdown' });
    await expect(table).toBeVisible();
    await page.evaluate(() => document.fonts.ready);

    const rows = table.getByRole('row');
    if (width >= 600) {
      await expect(
        table.getByRole('columnheader', { name: 'Food & Servings', exact: true }),
      ).toBeVisible();
      for (const row of await rows.all()) {
        const cells = row.getByRole('cell');
        if (!(await cells.count())) continue;
        const foodBox = await bounds(cells.nth(0));
        for (const index of [1, 2, 3]) {
          expect(Math.abs(centerY(await bounds(cells.nth(index))) - centerY(foodBox))).toBeLessThan(
            1,
          );
        }
      }
    } else {
      for (const row of await rows.all()) {
        const cells = row.getByRole('cell');
        if (!(await cells.count())) continue;
        const foodBox = await bounds(cells.nth(0));
        for (const index of [1, 2, 3]) {
          expect((await bounds(cells.nth(index))).y).toBeGreaterThanOrEqual(
            foodBox.y + foodBox.height,
          );
        }
        for (const label of ['Calories', 'Confidence', 'Provenance']) {
          await expect(row.getByText(label, { exact: true })).toBeVisible();
        }
      }
    }
    await expect(table.getByText('1 × Apple', { exact: true })).toBeVisible();
    await expect(table.getByText('95 kcal', { exact: true })).toBeVisible();
    await expect(table.getByText('91%', { exact: true })).toBeVisible();
    await expectNoOverflow(page, width);
    await page.screenshot({ path: testInfo.outputPath(`diary-${width}.png`), fullPage: true });
    await testInfo.attach(`diary-${width}`, {
      path: testInfo.outputPath(`diary-${width}.png`),
      contentType: 'image/png',
    });
  });
}
