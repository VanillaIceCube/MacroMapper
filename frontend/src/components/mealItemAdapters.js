import { portionOptions } from './mealItemPortions';
import { nutrientArrayToValues } from './nutrition/nutritionMath';

let mealItemSequence = 0;

const nextKey = (prefix, identifier) => `${prefix}-${identifier}-${mealItemSequence++}`;

export const sourceKindForProvenance = (provenance) =>
  provenance === 'official'
    ? 'official_verified'
    : provenance === 'ai_estimate'
      ? 'ai_estimate'
      : provenance === 'user_modified_estimate'
        ? 'user_modified_estimate'
        : provenance === 'user_entered'
          ? 'user_entered'
          : 'catalog_estimate';

const withPortionSelection = (item) => {
  const options = portionOptions(item);
  return {
    ...item,
    portion_options: options,
    selected_portion_key: options.some((option) => option.key === item.serving_unit)
      ? item.serving_unit
      : options[0].key,
  };
};

export const componentSnapshotToMealItem = (component) =>
  withPortionSelection({
    key: nextKey('manual-component', component.food_version_id || component.id),
    food_item: component.food_item_id,
    food_version: component.food_version_id,
    name: component.food_name || component.food_item_name,
    provider_name: component.provider_name || '',
    origin_type: component.origin_type,
    servings: String(component.servings ?? '1'),
    serving_quantity: component.serving_quantity || '1',
    serving_unit: component.serving_unit || 'serving',
    serving_label: component.serving_label || 'one serving',
    portion_options: component.portion_options || [],
    provenance: component.provenance || 'community_estimate',
    source_kind: sourceKindForProvenance(component.provenance || 'community_estimate'),
    confidence_score: component.confidence_score,
    nutrients: nutrientArrayToValues(component.nutrients),
    sources: component.sources || [],
    components: (component.components || []).map(componentSnapshotToMealItem),
  });

export const catalogFoodToManualMealItem = (food) => {
  const version = food.current_version || {};
  const provenance =
    version.provenance || (food.scope === 'personal' ? 'user_entered' : 'official');
  return withPortionSelection({
    key: nextKey('manual-food', food.id),
    food_item: food.id,
    food_version: null,
    name: food.name,
    provider_name: food.provider_name,
    origin_type: food.origin_type,
    servings: '1',
    serving_quantity: version.serving_quantity || '1',
    serving_unit: version.serving_unit || 'serving',
    serving_label: version.serving_label || 'one serving',
    portion_options: version.portion_options || [],
    provenance,
    source_kind: sourceKindForProvenance(provenance),
    confidence_score: version.confidence_score,
    nutrients: nutrientArrayToValues(version.nutrients),
    sources: (version.sources || []).map((source) => ({
      ...source,
      is_official: provenance === 'official',
    })),
    components: (version.components || []).map(componentSnapshotToMealItem),
  });
};

export const savedMealItemToEditableMealItem = (item) => {
  const servings = Number(item.servings);
  return withPortionSelection({
    key: nextKey('manual-saved', item.id || item.food_item_id),
    food_item: item.food_item_id,
    food_version: item.food_version_id,
    name: item.food_name,
    provider_name: item.provider_name,
    origin_type: item.origin_type,
    servings: String(servings),
    serving_quantity: item.serving_quantity,
    serving_unit: item.serving_unit,
    serving_label: item.serving_label,
    portion_options: item.portion_options || [],
    provenance: item.provenance,
    source_kind: sourceKindForProvenance(item.provenance),
    confidence_score: item.confidence_score,
    nutrients: nutrientArrayToValues(item.nutrients, servings),
    sources: [],
    components: (item.component_snapshot || []).map(componentSnapshotToMealItem),
  });
};

export const catalogFoodToProposalItem = (food) => {
  const version = food.current_version || {};
  const sourceKind = sourceKindForProvenance(version.provenance);
  return withPortionSelection({
    key: nextKey('catalog-added', food.id),
    food_item_id: food.id,
    food_version_id: version.id,
    name: food.name,
    provider_name: food.provider_name,
    origin_type: food.origin_type,
    servings: '1',
    serving_quantity: version.serving_quantity,
    serving_unit: version.serving_unit,
    serving_label: version.serving_label,
    portion_options: version.portion_options || [],
    provenance: version.provenance,
    source_kind: sourceKind,
    confidence_score: version.confidence_score,
    nutrients: nutrientArrayToValues(version.nutrients),
    sources: (version.sources || []).map((source) => ({
      ...source,
      is_official: sourceKind === 'official_verified',
    })),
    components: [],
  });
};
