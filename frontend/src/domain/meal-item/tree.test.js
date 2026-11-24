import {
  changeMealItemNutrient,
  changeMealItemPortion,
  changeMealItemServings,
  removeMealItemFromTree,
} from './tree';
import { servingAmountValue } from './portions';
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

describe('meal item tree operations', () => {
  test('leaves every node and its evidence unchanged when an edit targets a missing key', () => {
    const child = editableLeaf({ key: 'child' });
    const parent = editableLeaf({
      key: 'parent',
      evidence: { status: 'official_verified' },
      components: [child],
    });
    const sibling = editableLeaf({ key: 'sibling' });
    const items = [parent, sibling];

    const results = [
      changeMealItemServings(items, 'missing', '3', child),
      changeMealItemPortion(items, 'missing', 'base'),
      changeMealItemNutrient(items, 'missing', 'calories', '300'),
      removeMealItemFromTree(items, 'missing'),
    ];

    for (const result of results) {
      expect(result[0]).toBe(parent);
      expect(result[0].components[0]).toBe(child);
      expect(result[1]).toBe(sibling);
    }
  });

  test.each([
    ['protein', '10'],
    ['calories', ''],
    ['calories', 'invalid'],
  ])('ignores unsupported composite edits (%s = %s)', (nutrient, value) => {
    const composite = editableLeaf({
      key: 'recipe',
      components: [editableLeaf({ key: 'ingredient' })],
    });

    const updated = changeMealItemNutrient([composite], 'recipe', nutrient, value);

    expect(updated[0]).toBe(composite);
  });

  test('does not invent a scaling ratio when a composite has no known calories', () => {
    const composite = editableLeaf({
      key: 'recipe',
      components: [editableLeaf({ key: 'ingredient', nutrients: { calories: null } })],
    });

    expect(changeMealItemNutrient([composite], 'recipe', 'calories', '100')[0]).toBe(composite);
    expect(composite.components[0].nutrients.calories).toBeNull();
  });

  test('zeroing a nested composite preserves unknown nutrients and the original tree', () => {
    const ingredient = editableLeaf({
      key: 'ingredient',
      nutrients: { calories: '100', protein: '3', carbohydrates: null, fat: '' },
    });
    const composite = editableLeaf({
      key: 'recipe',
      components: [editableLeaf({ key: 'layer', components: [ingredient] })],
    });

    const updated = changeMealItemNutrient([composite], 'recipe', 'calories', '0')[0];

    expect(updated.components[0].components[0].nutrients).toEqual({
      calories: '0',
      protein: '0',
      carbohydrates: null,
      fat: '',
    });
    expect(itemNutrientTotal(updated, 'calories')).toBe(0);
    expect(itemNutrientTotal(updated, 'carbohydrates')).toBeNull();
    expect(ingredient.nutrients.calories).toBe('100');
  });

  test('changes natural serving sizes while preserving count and food identity', () => {
    const apple = editableLeaf({
      name: 'Red apple',
      food_item_id: 7,
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
    expect(medium).toMatchObject({ name: 'Red apple', food_item_id: 7, food_version: 9 });
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
