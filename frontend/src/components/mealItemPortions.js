import { formatNutritionAmount } from './nutrition/nutritionMath';

const servingDescription = (item) => {
  if (!item) return 'one serving';
  if (item.serving_label) return item.serving_label;
  return `${formatNutritionAmount(item.serving_quantity)} ${item.serving_unit || 'serving'}`;
};

export const portionOptions = (item) =>
  item?.portion_options?.length
    ? item.portion_options
    : [
        {
          key: 'base',
          label: servingDescription(item),
          unit_label: 'serving',
          serving_multiplier: '1',
        },
      ];

export const standardPortionLabels = {
  g: 'g',
  ml: 'ml',
  oz: 'oz',
  fl_oz: 'fl oz',
  cup: 'cup',
  tbsp: 'tbsp',
  tsp: 'tsp',
};

export const nativeMeasurementPortion = (item) =>
  item?.serving_unit && standardPortionLabels[item.serving_unit]
    ? portionOptions(item).find((option) => option.key === item.serving_unit)
    : null;

export const displayedPortionOptions = (item) => {
  const options = portionOptions(item);
  return nativeMeasurementPortion(item)
    ? options.filter((option) => option.key !== 'base')
    : options;
};

export const selectedPortion = (item) => {
  const options = portionOptions(item);
  const selected = options.find((option) => option?.key === item?.selected_portion_key);
  return (selected?.key === 'base' && nativeMeasurementPortion(item)) || selected || options[0];
};

export const portionOptionLabel = (option) =>
  option ? standardPortionLabels[option.key] || option.label || '' : '';

export const roundedNumberString = (value, fractionDigits = 8) =>
  String(Number(value.toFixed(fractionDigits)));

export const servingAmountValue = (item) => {
  if (!item || item.servings === '' || item.servings === null || item.servings === undefined) {
    return '';
  }
  const servings = Number(item.servings);
  const activeOption = selectedPortion(item);
  const multiplier = Number(activeOption?.serving_multiplier);
  if (
    !Number.isFinite(servings) ||
    servings < 0 ||
    !Number.isFinite(multiplier) ||
    multiplier <= 0
  ) {
    return item.servings;
  }
  return roundedNumberString(servings / multiplier, 6);
};
