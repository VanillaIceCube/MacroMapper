import {
  catalogFoodToManualMealItem,
  catalogFoodToProposalItem,
  savedMealItemToEditableMealItem,
} from './mealItemAdapters';
import {
  changeMealItemNutrient,
  changeMealItemPortion,
  changeMealItemServings,
  removeMealItemFromTree,
} from './mealItemTree';
import { itemNutrientTotal } from './nutrition/nutritionMath';

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

describe('meal item tree operations', () => {
  test('updates serving amount and portion anywhere in the tree', () => {
    const parent = editableLeaf({
      key: 'parent',
      components: [editableLeaf({ key: 'child' })],
    });

    const withServings = changeMealItemServings([parent], 'child', '3', parent.components[0]);
    expect(withServings[0].components[0]).toMatchObject({
      servings: '1.5',
      selected_portion_key: 'half',
    });

    const withPortion = changeMealItemPortion(withServings, 'child', 'base');
    expect(withPortion[0].components[0].selected_portion_key).toBe('base');
  });

  test('stores leaf nutrition per serving and scales composite children', () => {
    const leaf = editableLeaf();
    expect(changeMealItemNutrient([leaf], 'food', 'calories', '300')[0].nutrients.calories).toBe(
      '150',
    );

    const composite = editableLeaf({
      key: 'composite',
      servings: '1',
      components: [
        editableLeaf({ key: 'first', servings: '1', nutrients: { calories: '100' } }),
        editableLeaf({ key: 'second', servings: '1', nutrients: { calories: '200' } }),
      ],
    });
    const scaled = changeMealItemNutrient([composite], 'composite', 'calories', '600')[0];
    expect(scaled.components.map((component) => component.servings)).toEqual(['2', '2']);
  });

  test('removes nested items without disturbing their siblings', () => {
    const tree = [
      editableLeaf({
        key: 'parent',
        components: [editableLeaf({ key: 'remove' }), editableLeaf({ key: 'keep' })],
      }),
    ];

    expect(removeMealItemFromTree(tree, 'remove')[0].components.map((item) => item.key)).toEqual([
      'keep',
    ]);
  });
});

describe('meal item adapters', () => {
  test('normalizes catalog foods for manual and proposal editors', () => {
    const manual = catalogFoodToManualMealItem(catalogFood);
    const proposal = catalogFoodToProposalItem(catalogFood);

    expect(manual).toMatchObject({
      food_item: 7,
      food_version: null,
      source_kind: 'official_verified',
      nutrients: { calories: '95' },
      selected_portion_key: 'base',
    });
    expect(manual.components[0]).toMatchObject({
      food_item: 8,
      food_version: 10,
      name: 'Apple flesh',
      nutrients: { calories: '95' },
    });
    expect(itemNutrientTotal(manual.components[0], 'calories')).toBe(95);
    expect(itemNutrientTotal(manual, 'calories')).toBe(95);
    expect(proposal).toMatchObject({
      food_item_id: 7,
      food_version_id: 9,
      source_kind: 'official_verified',
      components: [],
    });
    expect(proposal.sources[0].is_official).toBe(true);
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
      food_item: 7,
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
