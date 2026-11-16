import { useState } from 'react';
import { fireEvent, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ItemNutritionCards, NutritionCards } from './NutritionCards';
import { renderWithProviders } from '../../test-helpers/utils';

describe('NutritionCards', () => {
  test('distinguishes known zero from unavailable values in read-only cards', () => {
    renderWithProviders(
      <NutritionCards
        ariaLabel="Daily nutrition"
        values={{ calories: 0, protein: 12.5, carbohydrates: null, fat: '' }}
      />,
    );

    const cards = within(screen.getByLabelText('Daily nutrition'));
    expect(cards.getByText('0')).toBeVisible();
    expect(cards.getByText('12.5')).toBeVisible();
    expect(cards.getAllByText('—')).toHaveLength(2);
    expect(cards.queryByRole('spinbutton')).not.toBeInTheDocument();
  });

  test('reports decimal input and clearing as editable strings', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    function EditableCards() {
      const [values, setValues] = useState({ calories: 0, protein: null });
      return (
        <NutritionCards
          values={values}
          itemName="Apple"
          onNutrientChange={(key, value) => {
            onChange(key, value);
            setValues((current) => ({ ...current, [key]: value }));
          }}
        />
      );
    }
    renderWithProviders(<EditableCards />);

    const calories = screen.getByRole('spinbutton', { name: 'Calories for Apple' });
    expect(calories).toHaveValue(0);
    expect(screen.getByRole('spinbutton', { name: 'Protein for Apple' })).toHaveValue(null);
    await user.clear(calories);
    expect(onChange).toHaveBeenLastCalledWith('calories', '');
    await user.type(calories, '125.5');
    expect(calories).toHaveValue(125.5);
    expect(onChange).toHaveBeenLastCalledWith('calories', '125.5');
  });

  test.each([
    [['calories'], 1],
    [[], 0],
  ])('limits editable controls to the explicitly allowed keys %j', (keys, expectedCount) => {
    renderWithProviders(
      <NutritionCards
        values={{ calories: 80, protein: 4, carbohydrates: 12, fat: 2 }}
        itemName="Snack"
        editableNutrientKeys={keys}
        onNutrientChange={vi.fn()}
      />,
    );

    expect(screen.queryAllByRole('spinbutton')).toHaveLength(expectedCount);
    expect(screen.queryByRole('spinbutton', { name: 'Protein for Snack' })).not.toBeInTheDocument();
    expect(screen.getByText('4')).toBeVisible();
  });
});

describe('ItemNutritionCards', () => {
  test('shows consumed totals and allows every primary nutrient to be edited for a leaf', () => {
    renderWithProviders(
      <ItemNutritionCards
        item={{
          name: 'Snack',
          servings: '2',
          nutrients: { calories: '50', protein: '3', carbohydrates: '4', fat: '1' },
          components: [],
        }}
        onNutrientChange={vi.fn()}
      />,
    );

    const cards = within(screen.getByLabelText('Snack macro values'));
    expect(cards.getByRole('spinbutton', { name: 'Calories for Snack' })).toHaveValue(100);
    expect(cards.getByRole('spinbutton', { name: 'Protein for Snack' })).toHaveValue(6);
    expect(cards.getByRole('spinbutton', { name: 'Carbs for Snack' })).toHaveValue(8);
    expect(cards.getByRole('spinbutton', { name: 'Fat for Snack' })).toHaveValue(2);
  });

  test('derives composite totals and routes only calorie edits to its callback', () => {
    const onNutrientChange = vi.fn();
    renderWithProviders(
      <ItemNutritionCards
        item={{
          name: 'Recipe',
          servings: '2',
          components: [
            {
              name: 'Ingredient',
              servings: '1',
              nutrients: { calories: '100', protein: '3', carbohydrates: '4', fat: '1' },
            },
          ],
        }}
        onNutrientChange={onNutrientChange}
      />,
    );

    const cards = within(screen.getByLabelText('Recipe macro values'));
    const calories = cards.getByRole('spinbutton', { name: 'Calories for Recipe' });
    expect(calories).toHaveValue(200);
    expect(cards.getAllByRole('spinbutton')).toHaveLength(1);
    expect(cards.getByText('6')).toBeVisible();
    expect(cards.getByText('8')).toBeVisible();
    expect(cards.getByText('2')).toBeVisible();
    fireEvent.change(calories, { target: { value: '250' } });
    expect(onNutrientChange).toHaveBeenCalledExactlyOnceWith('calories', '250');
  });
});
