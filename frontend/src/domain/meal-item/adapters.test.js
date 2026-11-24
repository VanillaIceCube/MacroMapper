import {
  catalogFoodToMealItem,
  mealItemToProposalItem,
  proposalItemToMealItem,
  savedMealItemToEditableMealItem,
} from './adapters';
import { servingAmountValue } from './portions';
import { itemNutrientTotal } from '../nutrition';

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

describe('meal item adapters', () => {
  test('assigns independent editor keys when the same catalog food is added twice', () => {
    const first = catalogFoodToMealItem(catalogFood);
    const second = catalogFoodToMealItem(catalogFood);

    expect(
      new Set([first.key, second.key, first.components[0].key, second.components[0].key]).size,
    ).toBe(4);
    expect(first.food_item_id).toBe(second.food_item_id);
    expect(first.components[0].food_version).toBe(second.components[0].food_version);
    expect(catalogFood).not.toHaveProperty('key');
  });

  test.each([
    ['shared', 'catalog_estimate'],
    ['personal', 'user_entered'],
  ])('opens an unversioned %s food without inventing nutrient data', (scope, sourceKind) => {
    const item = catalogFoodToMealItem({ id: 1, name: 'New food', scope });

    expect(item).toMatchObject({
      name: 'New food',
      food_item_id: 1,
      servings: '1',
      serving_unit: 'serving',
      selected_portion_key: 'base',
      source_kind: sourceKind,
      nutrients: {},
      sources: [],
      components: [],
    });
    expect(servingAmountValue(item)).toBe('1');
    expect(itemNutrientTotal(item, 'calories')).toBeNull();
  });

  test.each([
    ['g', 'g'],
    ['bowl', 'base'],
  ])('recovers an obsolete selection using the available %s portions', (unit, selectedKey) => {
    const item = proposalItemToMealItem({
      key: 'proposal',
      servings: '2',
      serving_unit: unit,
      selected_portion_key: 'removed-size',
      portion_options: [
        { key: 'base', label: 'One serving', serving_multiplier: '1' },
        { key: 'g', label: 'g', serving_multiplier: '0.01' },
      ],
      nutrients: [{ key: 'calories', amount: '95' }],
    });

    expect(item.selected_portion_key).toBe(selectedKey);
    expect(item.servings).toBe('2');
    expect(itemNutrientTotal(item, 'calories')).toBe(190);
    expect(mealItemToProposalItem(item).selected_portion_key).toBe(selectedKey);
  });

  test('keeps saved natural serving selection and nutrition snapshots', () => {
    const saved = savedMealItemToEditableMealItem({
      id: 21,
      food_item_id: 7,
      food_version_id: 9,
      food_name: 'Red apple',
      servings: '3',
      serving_unit: 'item',
      serving_label: 'one small apple',
      selected_portion_key: 'size:large',
      portion_options: [
        { key: 'size:small', label: 'Small', serving_multiplier: '1' },
        { key: 'size:large', label: 'Large', serving_multiplier: '1.5' },
      ],
      nutrients: [{ key: 'calories', amount: '300' }],
      component_snapshot: [],
    });
    expect(servingAmountValue(saved)).toBe('2');
    expect(itemNutrientTotal(saved, 'calories')).toBe(300);
    expect(mealItemToProposalItem(saved).selected_portion_key).toBe('size:large');
  });

  test('preserves proposal identifiers, provenance, confidence, and nested sources', () => {
    const source = { title: 'Official source', url: 'https://example.com/food' };
    const proposal = {
      key: 'proposal',
      food_item_id: 7,
      food_version_id: 9,
      name: 'Meal',
      servings: '2',
      provenance: 'user_modified_estimate',
      source_kind: 'user_modified_estimate',
      confidence_score: '0.87',
      market: 'US',
      product_identifier: 'apple-123',
      identity_url: 'https://example.com/food',
      natural_servings: [{ key: 'small', label: 'Small', weight_grams: '149' }],
      nutrients: { calories: '100' },
      selected_portion_key: 'half',
      portion_options: [
        { key: 'base', label: 'one serving', serving_multiplier: '1' },
        { key: 'half', label: 'half serving', serving_multiplier: '0.5' },
      ],
      sources: [source],
      components: [
        {
          key: 'component',
          food_item_id: 8,
          food_version_id: 10,
          servings: '1',
          provenance: 'official',
          confidence_score: null,
          nutrients: { calories: '50' },
          sources: [source],
          components: [],
        },
      ],
    };

    const roundTrip = mealItemToProposalItem(proposalItemToMealItem(proposal));
    expect(roundTrip).toMatchObject(proposal);
    expect(roundTrip.sources).toEqual([source]);
    expect(roundTrip.components[0].sources).toEqual([source]);
  });
  test('normalizes catalog foods for the meal builder', () => {
    const mealItem = catalogFoodToMealItem(catalogFood);

    expect(mealItem).toMatchObject({
      food_item_id: 7,
      food_version: null,
      source_kind: 'official_verified',
      nutrients: { calories: '95' },
      selected_portion_key: 'base',
    });
    expect(mealItem.components[0]).toMatchObject({
      food_item_id: 8,
      food_version: 10,
      name: 'Apple flesh',
      nutrients: { calories: '95' },
    });
    expect(itemNutrientTotal(mealItem.components[0], 'calories')).toBe(95);
    expect(itemNutrientTotal(mealItem, 'calories')).toBe(95);
  });

  test('normalizes saved total nutrients back to per-serving editor values', () => {
    const saved = savedMealItemToEditableMealItem({
      id: 21,
      food_item_id: 7,
      food_version_id: 9,
      food_name: 'Apple',
      provider_name: '',
      servings: '2',
      serving_quantity: '1',
      serving_unit: 'item',
      serving_label: 'one apple',
      provenance: 'user_entered',
      nutrients: [{ key: 'calories', amount: '190' }],
      component_snapshot: [],
    });

    expect(saved).toMatchObject({
      food_item_id: 7,
      food_version: 9,
      servings: '2',
      nutrients: { calories: '95' },
      source_kind: 'user_entered',
    });
  });

  test('preserves component nutrients when normalizing a saved composite item', () => {
    const saved = savedMealItemToEditableMealItem({
      id: 22,
      food_item_id: 10,
      food_version_id: 12,
      food_name: 'Avocado toast',
      provider_name: '',
      servings: '1',
      serving_quantity: '1',
      serving_unit: 'item',
      serving_label: 'one serving',
      provenance: 'user_entered',
      nutrients: [{ key: 'calories', amount: '220' }],
      component_snapshot: [
        {
          food_item_id: 11,
          food_version_id: 13,
          food_name: 'Avocado',
          servings: '1',
          nutrients: [{ key: 'calories', amount: '160' }],
          components: [],
        },
        {
          food_item_id: 12,
          food_version_id: 14,
          food_name: 'Toast',
          servings: '1',
          nutrients: [{ key: 'calories', amount: '60' }],
          components: [],
        },
      ],
    });

    expect(saved.components.map((component) => itemNutrientTotal(component, 'calories'))).toEqual([
      160, 60,
    ]);
    expect(itemNutrientTotal(saved, 'calories')).toBe(220);
  });
});
