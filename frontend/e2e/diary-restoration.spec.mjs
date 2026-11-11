import { test, expect } from '@playwright/test';

const apple = {
  id: 7,
  name: 'Apple',
  provider_name: '',
  scope: 'personal',
  current_version: {
    id: 9,
    serving_quantity: '1',
    serving_unit: 'item',
    serving_label: 'one apple',
    provenance: 'user_entered',
    confidence_score: null,
    nutrients: [{ key: 'calories', name: 'Calories', unit: 'kcal', amount: '95' }],
    sources: [],
    components: [],
  },
};
const items = [
  {
    id: 21,
    food_item_id: 7,
    food_version_id: 9,
    food_name: 'Apple',
    provider_name: '',
    servings: '1',
    serving_quantity: '1',
    serving_unit: 'item',
    serving_label: 'one apple',
    provenance: 'user_entered',
    confidence_score: null,
    component_snapshot: [],
    nutrients: [{ key: 'calories', name: 'Calories', unit: 'kcal', amount: '95' }],
  },
  {
    id: 22,
    food_item_id: 8,
    food_version_id: 10,
    food_name: 'Roasted vegetables with brown rice and a lemon herb dressing',
    provider_name: 'Example Kitchen',
    servings: '2',
    serving_quantity: '1',
    serving_unit: 'bowl',
    serving_label: 'one bowl with vegetables, rice, and dressing served on the side',
    provenance: 'ai_estimate',
    confidence_score: '0.910',
    component_snapshot: [],
    nutrients: [{ key: 'calories', name: 'Calories', unit: 'kcal', amount: '320' }],
  },
];

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('accessToken', 'restoration-fixture-placeholder');
    sessionStorage.setItem('email', 'restoration@example.test');
    sessionStorage.setItem('username', 'Restoration fixture');
    window.fixturePageErrors = [];
    window.addEventListener('error', (event) => window.fixturePageErrors.push(event.message));
    window.addEventListener('unhandledrejection', (event) =>
      window.fixturePageErrors.push(String(event.reason)),
    );
  });
  // The same fixture can load public production assets. Intercept every app
  // request before navigation; placeholder credentials/writes never reach a host.
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
              items,
            },
          ],
        },
      });
    } else if (request.method() === 'GET' && url.pathname === '/api/foods/') {
      await route.fulfill({ json: [apple] });
    } else if (request.method() === 'GET' && url.pathname === '/api/notifications/') {
      await route.fulfill({ json: [] });
    } else {
      await route.abort('blockedbyclient');
    }
  });
});

const box = async (locator) => {
  const result = await locator.boundingBox();
  expect(result).not.toBeNull();
  return result;
};

for (const width of [320, 375, 600, 768, 1024, 1440]) {
  test(`native date picker uses its visible trigger at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/diary');
    await expect(page.getByRole('table', { name: 'Sample lunch food breakdown' })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    const input = page.getByLabel('diary date', { exact: true });
    const trigger = page.getByRole('button', { name: /^choose diary date/ });
    const navigation = page.getByRole('navigation', { name: 'diary date navigation' });
    const today = await input.inputValue();
    const samples = [];
    for (const date of [today, '2026-09-30', '2026-11-11', today]) {
      await input.fill(date);
      samples.push({
        date,
        input: await box(input),
        trigger: await box(trigger),
        navigation: await box(navigation),
      });
    }
    await testInfo.attach('native-date-geometry', {
      body: JSON.stringify(samples, null, 2),
      contentType: 'application/json',
    });
    for (const sample of samples) {
      for (const key of ['x', 'y', 'width', 'height']) {
        expect(
          Math.abs(sample.input[key] - sample.trigger[key]),
          `${sample.date}: input ${key}`,
        ).toBeLessThan(1);
      }
      expect(sample.navigation.x).toBeGreaterThanOrEqual(0);
      expect(sample.navigation.x + sample.navigation.width).toBeLessThanOrEqual(width);
    }
    expect(Math.abs(samples[0].navigation.x - samples.at(-1).navigation.x)).toBeLessThan(1);
    expect(Math.abs(samples[0].navigation.width - samples.at(-1).navigation.width)).toBeLessThan(1);
    await page.evaluate(() => {
      const original = HTMLInputElement.prototype.showPicker;
      window.fixturePickerCalls = [];
      if (original) {
        HTMLInputElement.prototype.showPicker = function () {
          window.fixturePickerCalls.push({
            active: navigator.userActivation.isActive,
            label: this.getAttribute('aria-label'),
          });
          return original.call(this);
        };
      }
    });
    await trigger.click();
    expect(await page.evaluate(() => window.fixturePickerCalls)).toEqual([
      { active: true, label: 'diary date' },
    ]);
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: 'next day', exact: true }).click();
    await expect(input).not.toHaveValue(today);
    await page.getByRole('button', { name: 'return to today', exact: true }).click();
    await expect(input).toHaveValue(today);
    expect(await page.evaluate(() => window.fixturePageErrors)).toEqual([]);
    await page.screenshot({
      path: testInfo.outputPath(`picker-anchor-${width}.png`),
      animations: 'disabled',
    });
  });
}

for (const width of [375, 1280]) {
  test(`prior date visuals, safe navigation and food presentation at ${width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/diary');
    const table = page.getByRole('table', { name: 'Sample lunch food breakdown' });
    await expect(table).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    const header = await box(page.getByTestId('diary-header'));
    const navigation = await box(page.getByRole('navigation', { name: 'diary date navigation' }));
    if (width < 900) {
      expect(Math.abs(navigation.x - header.x)).toBeLessThan(1);
      expect(
        (await box(page.getByRole('button', { name: /^choose diary date/ }))).width,
      ).toBeLessThan(140);
    } else {
      expect(Math.abs(navigation.x + navigation.width - header.x - header.width)).toBeLessThan(1);
    }

    const input = page.getByLabel('diary date', { exact: true });
    const initialDate = await input.inputValue();
    await input.fill('');
    await expect(input).toHaveValue(initialDate);
    await page.getByRole('button', { name: 'next day', exact: true }).click();
    await expect(input).not.toHaveValue(initialDate);
    await page.getByRole('button', { name: 'return to today', exact: true }).click();
    await expect(input).toHaveValue(initialDate);
    for (const row of await table.getByRole('row').all()) {
      const cells = row.getByRole('cell');
      if (!(await cells.count())) continue;
      const identity = await box(cells.nth(0));
      for (const index of [1, 2, 3]) {
        const metadata = await box(cells.nth(index));
        if (width >= 600) {
          expect(
            Math.abs(metadata.y + metadata.height / 2 - identity.y - identity.height / 2),
          ).toBeLessThan(1);
        } else {
          expect(metadata.y).toBeGreaterThanOrEqual(identity.y + identity.height);
        }
      }
    }
    if (width >= 600) {
      await expect(
        table.getByRole('columnheader', { name: 'Food & Servings', exact: true }),
      ).toBeVisible();
    }
    await expect(table.getByText('1 × Apple', { exact: true })).toBeVisible();
    await expect(table.getByText('95 kcal', { exact: true })).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Meal Log', level: 1, exact: true }),
    ).toBeVisible();
    expect(await page.evaluate(() => window.fixturePageErrors)).toEqual([]);
    await page.screenshot({
      path: testInfo.outputPath(`diary-restored-${width}.png`),
      fullPage: true,
    });
  });

  test(`meal review and manual/estimate dialogs remain usable at ${width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/diary');
    await page.getByRole('button', { name: 'edit Sample lunch', exact: true }).click();
    const review = page.getByRole('dialog', { name: /^Edit meal/ });
    await expect(review).toBeVisible();
    await expect(review.getByRole('region', { name: 'Meal Items', exact: true })).toBeVisible();
    await expect(
      review.getByRole('region', { name: 'Meal macro breakdown', exact: true }),
    ).toBeVisible();
    await expect(review.getByText('AI Adjustments', { exact: true })).toBeVisible();
    const reviewBox = await box(review);
    expect(reviewBox.x).toBeGreaterThanOrEqual(0);
    expect(reviewBox.x + reviewBox.width).toBeLessThanOrEqual(width);
    await page.screenshot({
      path: testInfo.outputPath(`meal-review-${width}.png`),
      fullPage: true,
    });
    await review.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(review).toHaveCount(0);

    await page.getByRole('button', { name: 'Map your Meal with AI', exact: true }).click();
    const estimate = page.getByRole('dialog', { name: /^Map it with AI/ });
    await expect(estimate).toBeVisible();
    await estimate.getByRole('button', { name: 'Create estimate', exact: true }).click();
    await expect(
      estimate.getByText('Describe the meal you want to estimate.', { exact: true }),
    ).toBeVisible();
    await estimate.getByRole('button', { name: 'Cancel', exact: true }).click();
    await page.getByRole('button', { name: 'Chart your Course Manually', exact: true }).click();
    const manual = page.getByRole('dialog', { name: /^Map Your Meal/ });
    await expect(manual.getByRole('region', { name: 'Meal Details', exact: true })).toBeVisible();
    await expect(
      manual.getByRole('textbox', { name: 'Search catalog', exact: true }),
    ).toBeVisible();
    await manual.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(manual).toHaveCount(0);
    expect(await page.evaluate(() => window.fixturePageErrors)).toEqual([]);
  });
}
