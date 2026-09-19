import { formatNutritionAmount } from './nutrition/nutritionMath';

const servingDescription = (item = {}) => {
  if (item?.serving_label) return item.serving_label;
  return `${formatNutritionAmount(item?.serving_quantity)} ${item?.serving_unit || 'serving'}`;
};

export const portionOptions = (item = {}) =>
  Array.isArray(item?.portion_options) && item.portion_options.length
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

export const nativeMeasurementPortion = (item = {}) =>
  item?.serving_unit && standardPortionLabels[item.serving_unit]
    ? portionOptions(item).find((option) => option.key === item.serving_unit)
    : null;

export const displayedPortionOptions = (item = {}) => {
  const options = portionOptions(item);
  return nativeMeasurementPortion(item)
    ? options.filter((option) => option.key !== 'base')
    : options;
};

export const selectedPortion = (item = {}) => {
  const options = portionOptions(item);
  const selected = options.find((option) => option && option.key === item?.selected_portion_key);
  const fallback =
    (selected?.key === 'base' && nativeMeasurementPortion(item)) || selected || options[0];
  return (
    fallback || { key: 'base', label: 'serving', unit_label: 'serving', serving_multiplier: '1' }
  );
};

export const portionOptionLabel = (option = {}) => {
  if (!option || typeof option !== 'object') return 'serving';
  return standardPortionLabels[option.key] || option.label || option.key || 'serving';
};

export const roundedNumberString = (value, fractionDigits = 8) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '0';
  return String(Number(numeric.toFixed(fractionDigits)));
};

export const servingAmountValue = (item = {}) => {
  if (!item || typeof item !== 'object') return '';
  if (item.servings === '' || item.servings === null || item.servings === undefined) return '';
  const servings = Number(item.servings);
  const activePortion = selectedPortion(item);
  const multiplier = Number(activePortion?.serving_multiplier);

  if (!Number.isFinite(servings) || !Number.isFinite(multiplier) || multiplier <= 0) {
    return String(item.servings ?? '');
  }

  // Preserve in-progress string typing when using multiplier 1
  if (typeof item.servings === 'string' && (multiplier === 1 || Math.abs(multiplier - 1) < 1e-9)) {
    return item.servings;
  }

  return roundedNumberString(servings / multiplier, 6);
};
