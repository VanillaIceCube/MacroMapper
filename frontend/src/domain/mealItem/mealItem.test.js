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
import { servingAmountValue } from './portions';

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
  test('changes natural serving sizes while preserving count and food identity', () => {
    const apple = editableLeaf({
      name: 'Red apple',
      food_item: 7,
      food_version: 9,
      servings: '2',
      selected_portion_key: 'size:small',
      serving_weight_grams: '149',
      portion_options: [
        { key: 'base', label: 'one small apple', serving_multiplier: '1' },
        { key: 'size:small', label: 'Small', serving_multiplier: '1' },
        { key: 'size:medium', label: 'Medium', serving_multiplier: '1.2' },
        { key: 'size:large', label: 'Large', serving_multiplier: '1.5' },
        { key: 'g', label: 'g', serving_multiplier: String(1 / 149) },
      ],
    });
    const medium = changeMealItemPortion([apple], 'food', 'size:medium')[0];
    expect(servingAmountValue(medium)).toBe('2');
    expect(medium).toMatchObject({ name: 'Red apple', food_item: 7, food_version: 9 });
    expect(itemNutrientTotal(medium, 'calories')).toBe(240);
    const large = changeMealItemPortion([medium], 'food', 'size:large')[0];
    expect(servingAmountValue(large)).toBe('2');
    expect(itemNutrientTotal(large, 'calories')).toBe(300);
    const grams = changeMealItemPortion([large], 'food', 'g')[0];
    expect(servingAmountValue(grams)).toBe('447');
    expect(itemNutrientTotal(grams, 'calories')).toBe(300);
    const backToSmall = changeMealItemPortion([grams], 'food', 'size:small')[0];
    expect(servingAmountValue(backToSmall)).toBe('3');
    expect(itemNutrientTotal(backToSmall, 'calories')).toBe(300);
    const base = { ...apple, selected_portion_key: 'base' };
    const baseToMedium = changeMealItemPortion([base], 'food', 'size:medium')[0];
    expect(servingAmountValue(baseToMedium)).toBe('2');
    expect(itemNutrientTotal(baseToMedium, 'calories')).toBe(240);
    expect(apple.servings).toBe('2');
    expect(changeMealItemPortion([apple], 'food', 'missing')[0]).toBe(apple);
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

describe('source-backed nutrition integrity', () => {
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

  test('component edits remove parent verification and use updated totals', () => {
    const item = official();
    const updated = changeMealItemNutrient([item], 'child', 'calories', '300')[0];
    expect(updated.evidence.status).toBe('user_modified_estimate');
    expect(updated.components[0].source_kind).toBe('user_modified_estimate');
    expect(itemNutrientTotal(updated, 'calories')).toBe(300);
    expect(itemNutrientTotal(item, 'calories')).toBe(710);
    const counted = changeMealItemServings([item], 'parent', '2', item)[0];
    expect(counted.evidence.status).toBe('source_backed_ai_components');
    const resized = changeMealItemNutrient([item], 'parent', 'calories', '600')[0];
    expect(itemNutrientTotal(resized, 'calories')).toBe(600);
    expect(resized.evidence.status).toBe('user_modified_estimate');
    const portionOnly = changeMealItemPortion([item], 'child', 'base')[0];
    expect(portionOnly.evidence.status).toBe('source_backed_ai_components');
  });

  test('natural size changes retain food evidence and invalidate affected composite ancestors', () => {
    const child = editableLeaf({
      key: 'apple',
      servings: '1',
      selected_portion_key: 'size:small',
      nutrients: { calories: '100' },
      provenance: 'official',
      evidence: { nutrients: { calories: { status: 'official_verified' } } },
      portion_options: [
        { key: 'size:small', label: 'Small', serving_multiplier: '1' },
        { key: 'size:medium', label: 'Medium', serving_multiplier: '1.2' },
        { key: 'g', label: 'g', serving_multiplier: '0.01' },
      ],
    });
    const parent = { ...official(), components: [child] };
    const outer = { ...official(), key: 'outer', components: [parent] };
    const resized = changeMealItemPortion([outer], 'apple', 'size:medium')[0];
    expect(resized.evidence.status).toBe('user_modified_estimate');
    expect(resized.components[0].evidence.status).toBe('user_modified_estimate');
    expect(resized.components[0].components[0].evidence).toBe(child.evidence);
    expect(resized.components[0].components[0].provenance).toBe('official');
    expect(itemNutrientTotal(resized, 'calories')).toBe(120);

    const measured = changeMealItemPortion([outer], 'apple', 'g')[0];
    expect(measured.evidence).toBe(outer.evidence);
    expect(measured.components[0].evidence).toBe(parent.evidence);
    expect(itemNutrientTotal(measured, 'calories')).toBe(710);
    const backToSize = changeMealItemPortion([measured], 'apple', 'size:medium')[0];
    expect(backToSize.evidence).toBe(outer.evidence);
    expect(itemNutrientTotal(backToSize, 'calories')).toBe(710);

    const sameSize = changeMealItemPortion(
      [{ ...parent, components: [{ ...child, servings: '1.0000' }] }],
      'apple',
      'size:small',
    )[0];
    expect(sameSize.evidence).toBe(parent.evidence);

    const ownSize = changeMealItemPortion(
      [{ ...parent, selected_portion_key: 'size:small', portion_options: child.portion_options }],
      'parent',
      'size:medium',
    )[0];
    expect(ownSize.evidence).toBe(parent.evidence);
    expect(servingAmountValue(ownSize)).toBe('1');
    expect(itemNutrientTotal(ownSize, 'calories')).toBe(852);
  });
});
