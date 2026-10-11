import {
  catalogFoodToMealItem,
  mealItemToProposalItem,
  proposalItemToMealItem,
  savedMealItemToEditableMealItem,
} from './adapters';
import {
  changeMealItemNutrient,
  changeMealItemPortion,
  changeMealItemServings,
  removeMealItemFromTree,
} from './tree';
import { itemNutrientTotal } from '../nutrition/calculations';

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
  test('keeps decimal entry text and updates nested trees immutably', () => {
    const child = editableLeaf({
      key: 'child',
      selected_portion_key: 'base',
    });
    const parent = editableLeaf({ key: 'parent', components: [child] });
    const updated = changeMealItemServings([parent], 'child', '1.', child);

    expect(updated[0].components[0].servings).toBe('1.');
    expect(parent.components[0].servings).toBe('2');
    expect(updated[0]).not.toBe(parent);
    expect(updated[0].components[0]).not.toBe(child);
  });
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

  test('clamps negative serving amounts and negative nutrient inputs to zero', () => {
    const item = editableLeaf({ key: 'negative-test', servings: '2' });

    const negativeServings = changeMealItemServings([item], 'negative-test', '-5', item);
    expect(negativeServings[0].servings).toBe('0');

    const negativeNutrient = changeMealItemNutrient([item], 'negative-test', 'calories', '-100');
    expect(negativeNutrient[0].nutrients.calories).toBe('0');
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

    const zeroed = changeMealItemNutrient([composite], 'composite', 'calories', '0')[0];
    expect(zeroed.components.map((component) => component.servings)).toEqual(['1', '1']);
    expect(zeroed.components.map((component) => component.nutrients.calories)).toEqual(['0', '0']);

    const nestedComposite = editableLeaf({
      key: 'nested-composite',
      components: [
        editableLeaf({
          key: 'nested-child',
          components: [editableLeaf({ key: 'nested-leaf', nutrients: { calories: '100' } })],
        }),
      ],
    });
    const nestedZeroed = changeMealItemNutrient(
      [nestedComposite],
      'nested-composite',
      'calories',
      '0',
    )[0];
    expect(nestedZeroed.components[0].components[0].nutrients.calories).toBe('0');
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
      food_item: 7,
      food_version: null,
      source_kind: 'official_verified',
      nutrients: { calories: '95' },
      selected_portion_key: 'base',
    });
    expect(mealItem.components[0]).toMatchObject({
      food_item: 8,
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
