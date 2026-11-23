import {
  catalogFoodToMealItem,
  mealItemToProposalItem,
  proposalItemToMealItem,
  savedMealItemToEditableMealItem,
  changeMealItemServings,
} from './index';
import { itemNutrientTotal } from '../nutrition';

const editableLeaf = (overrides = {}) => ({
  key: 'food',
  name: 'Food',
  servings: '2',
  serving_quantity: '1',
  serving_unit: 'item',
  serving_label: 'one item',
  selected_portion_key: 'half',
  portion_options: [
    { key: 'base', label: 'one item', serving_multiplier: '1' },
    { key: 'half', label: 'half item', serving_multiplier: '0.5' },
  ],
  nutrients: { calories: '100' },
  components: [],
  ...overrides,
});

const catalogFood = {
  id: 7,
  name: 'Apple',
  provider_name: 'Orchard',
  origin_type: 'branded',
  scope: 'shared',
  current_version: {
    id: 9,
    serving_quantity: '1',
    serving_unit: 'item',
    serving_label: 'one apple',
    provenance: 'official',
    confidence_score: '0.98',
    portion_options: [],
    nutrients: [{ key: 'calories', amount: '95' }],
    sources: [{ title: 'Official source', url: 'https://example.com/apple' }],
    components: [
      {
        id: 11,
        food_item_id: 8,
        food_version_id: 10,
        food_name: 'Apple flesh',
        servings: '1',
        nutrients: [{ key: 'calories', amount: '95' }],
        components: [],
      },
    ],
  },
};

describe('meal item public API workflows', () => {
  const official = () =>
    editableLeaf({
      key: 'parent',
      servings: '1',
      source_kind: 'official_verified',
      provenance: 'official',
      nutrients: { calories: '710' },
      evidence: {
        status: 'source_backed_ai_components',
        nutrients: { calories: { status: 'official_verified' } },
      },
      components: [editableLeaf({ key: 'child', servings: '1', nutrients: { calories: '400' } })],
    });

  test('retains full recipe ingredients and scales only the consumed parent', () => {
    const recipe = editableLeaf({
      key: 'recipe',
      servings: '0.75',
      selected_portion_key: 'base',
      components: [
        editableLeaf({ key: 'tomatoes', servings: '3', nutrients: { calories: '20' } }),
        editableLeaf({ key: 'chips', servings: '2', nutrients: { calories: '100' } }),
      ],
    });
    expect(itemNutrientTotal(recipe, 'calories')).toBe(195);
    const half = changeMealItemServings([recipe], 'recipe', '0.5', recipe)[0];
    expect(itemNutrientTotal(half, 'calories')).toBe(130);
    expect(half.components).toEqual(recipe.components);
    const reloaded = proposalItemToMealItem(mealItemToProposalItem(half));
    expect(itemNutrientTotal(reloaded, 'calories')).toBe(130);
    expect(reloaded.components.map((item) => item.servings)).toEqual(['3', '2']);
  });

  test('retains official direct parent values across catalog and diary adapters', () => {
    const food = {
      ...catalogFood,
      current_version: {
        ...catalogFood.current_version,
        evidence: official().evidence,
        nutrients: [{ key: 'calories', amount: '710' }],
        sources: [{ title: 'Secondary', url: 'https://example.com', is_official: false }],
      },
    };
    const item = catalogFoodToMealItem(food);
    expect(itemNutrientTotal(item, 'calories')).toBe(710);
    expect(item.sources[0].is_official).toBe(false);
    const saved = savedMealItemToEditableMealItem({
      ...official(),
      id: 1,
      food_name: 'Pizza',
      nutrients: [{ key: 'calories', amount: '1420' }],
      servings: '2',
      component_snapshot: [],
    });
    expect(itemNutrientTotal(saved, 'calories')).toBe(1420);
    expect(saved.evidence.status).toBe('source_backed_ai_components');
  });
});
