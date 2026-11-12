import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MealItemEditorRow from './MealItemEditorRow';
import { changeMealItemNutrient } from '../domain/mealItem';

const row = (overrides = {}) => ({
  key: 'pizza',
  name: 'Costco Pizza',
  servings: '1',
  serving_quantity: '1',
  serving_unit: 'item',
  serving_label: '1 slice',
  nutrients: { calories: '710' },
  source_kind: 'official_verified',
  confidence_score: '.98',
  components: [],
  ...overrides,
});

const renderRow = (item) => render(<MealItemEditorRow item={item} renderNutrition={() => null} />);

async function details(name) {
  await userEvent.click(screen.getByRole('button', { name: `More actions for ${name}` }));
  await userEvent.click(
    screen.getByRole('menuitem', { name: `Show estimate details for ${name}` }),
  );
}

test('explains official parent, AI components, nutrient coverage and confidence with linked evidence', async () => {
  renderRow(
    row({
      evidence: {
        status: 'source_backed_ai_components',
        research_status: 'found',
        confidence: { model: 0.98, evidence: null, combined: 0.5 },
        nutrients: {
          calories: { status: 'official_verified' },
          sugar: { status: 'ai_estimate' },
        },
      },
      sources: [
        { title: 'Costco nutrition', url: 'https://www.costco.com/nutrition', is_official: true },
      ],
      components: [
        row({ key: 'crust', name: 'Crust', source_kind: 'ai_estimate', confidence_score: '.5' }),
      ],
    }),
  );
  await details('Costco Pizza');
  expect(screen.getByText('Official parent; AI components')).toBeVisible();
  expect(screen.getByText('Official source for parent; components estimated by AI.')).toBeVisible();
  expect(screen.getByText('calories: Official source verified')).toBeVisible();
  expect(screen.getByText('sugar: Estimated; not source verified')).toBeVisible();
  expect(screen.getByText(/Combined confidence: 50%/)).toBeVisible();
  expect(screen.getByRole('link', { name: 'Costco nutrition' })).toHaveAttribute(
    'href',
    'https://www.costco.com/nutrition',
  );
  await userEvent.click(screen.getByRole('button', { name: 'Expand components for Costco Pizza' }));
  await details('Crust');
  expect(screen.getByText('AI Estimate')).toBeVisible();
});

test.each([
  ['no_source_found', 'No matching nutrition source found'],
  ['failed', 'Nutrition source retrieval failed'],
])('shows %s research warning', async (status, message) => {
  renderRow(
    row({
      evidence: { status: 'ai_estimate', research_status: status },
      source_kind: 'ai_estimate',
    }),
  );
  await details('Costco Pizza');
  expect(screen.getByRole('status')).toHaveTextContent(message);
});

test('renders unknown legacy classification safely', async () => {
  renderRow(row({ source_kind: 'unknown_old_value' }));
  await details('Costco Pizza');
  expect(screen.getByText('AI Estimate')).toBeVisible();
});

test('does not present an unrecorded legacy official claim as verified', async () => {
  renderRow(row({ evidence: { status: 'legacy_unverified', research_status: 'not_recorded' } }));
  await details('Costco Pizza');
  expect(screen.getByText('Legacy official; evidence unrecorded')).toBeVisible();
  expect(screen.queryByText('Official / Verified')).not.toBeInTheDocument();
});

test('clears prior model and combined confidence after editing nutrition', async () => {
  const item = row({
    evidence: {
      status: 'official_verified',
      confidence: { model: 0.98, evidence: null, combined: 0.5 },
    },
  });
  const edited = changeMealItemNutrient([item], item.key, 'calories', '600')[0];
  renderRow(edited);
  await details('Costco Pizza');
  expect(edited.evidence.confidence).toEqual({ model: null, evidence: null, combined: null });
  expect(screen.queryByText(/Combined confidence: 50%/)).not.toBeInTheDocument();
  expect(screen.queryByText('98% Confidence')).not.toBeInTheDocument();
});
