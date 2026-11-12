import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { renderWithProviders } from '../test-support/utils';
import { changeMealItemPortion, changeMealItemServings } from '../domain/mealItem';
import { itemNutrientTotal } from '../domain/nutrition';
import MealItemEditorRow from './MealItemEditorRow';

const apple = {
  key: 'apple',
  name: 'Red apple',
  servings: '2',
  serving_unit: 'item',
  selected_portion_key: 'size:small',
  portion_options: [
    { key: 'size:small', label: 'Small', serving_multiplier: '1' },
    { key: 'size:medium', label: 'Medium', serving_multiplier: '1.2' },
    { key: 'size:large', label: 'Large', serving_multiplier: '1.5' },
  ],
  nutrients: { calories: '80' },
  components: [],
};

function EditableRow({ initialItem }) {
  const [items, setItems] = useState([initialItem]);
  return (
    <MealItemEditorRow
      item={items[0]}
      onServings={(key, amount, item) =>
        setItems((current) => changeMealItemServings(current, key, amount, item))
      }
      onPortionChange={(key, portion) =>
        setItems((current) => changeMealItemPortion(current, key, portion))
      }
      onNutrientChange={vi.fn()}
      onRemove={vi.fn()}
      renderNutrition={(item) => (
        <span aria-label={`${item.name} calories`}>{itemNutrientTotal(item, 'calories')}</span>
      )}
    />
  );
}

describe('meal item food and portion presentation', () => {
  test('keeps the apple name and count when selecting larger natural portions', async () => {
    const user = userEvent.setup();
    renderWithProviders(<EditableRow initialItem={apple} />);

    expect(screen.getByText('Red apple')).toBeVisible();
    expect(screen.getByRole('spinbutton', { name: 'Count' })).toHaveValue(2);
    expect(screen.getByRole('combobox', { name: 'Unit' })).toHaveTextContent('Small');
    expect(screen.getByLabelText('Red apple calories')).toHaveTextContent('160');

    await user.click(screen.getByRole('combobox', { name: 'Unit' }));
    await user.click(screen.getByRole('option', { name: 'Medium' }));
    expect(screen.getByRole('spinbutton', { name: 'Count' })).toHaveValue(2);
    expect(screen.getByLabelText('Red apple calories')).toHaveTextContent('192');

    await user.click(screen.getByRole('combobox', { name: 'Unit' }));
    await user.click(screen.getByRole('option', { name: 'Large' }));
    expect(screen.getByRole('spinbutton', { name: 'Count' })).toHaveValue(2);
    expect(screen.getByLabelText('Red apple calories')).toHaveTextContent('240');
    expect(screen.getByText('Red apple')).toBeVisible();
  });

  test('labels full recipe ingredient amounts while retaining the consumed fraction', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <EditableRow
        initialItem={{
          key: 'recipe',
          name: 'Chilaquiles',
          servings: '0.75',
          components: [{ ...apple, name: 'Tomato', servings: '3' }],
        }}
      />,
    );

    expect(screen.getByLabelText('Chilaquiles calories')).toHaveTextContent('180');
    await user.click(screen.getByRole('button', { name: 'Expand components for Chilaquiles' }));
    expect(
      screen.getByText(
        'Ingredients shown per full portion; totals above reflect the amount eaten.',
      ),
    ).toBeVisible();
    expect(screen.getByLabelText('Tomato calories')).toHaveTextContent('240');
    expect(
      screen.getAllByRole('spinbutton', { name: 'Count' }).map((field) => field.value),
    ).toEqual(['0.75', '3']);
  });
});
