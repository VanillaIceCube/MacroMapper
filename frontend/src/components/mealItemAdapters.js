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
    key: nextKey('meal-component', component.food_version_id || component.id),
    food_item: component.food_item_id,
    food_version: component.food_version_id,
    name: component.food_name || component.food_item_name,
    provider_name: component.provider_name || '',
    origin_type: component.origin_type,
    servings: String(component.servings ?? '1'),
    serving_quantity: component.serving_quantity || '1',
    serving_unit: component.serving_unit || 'serving',
    serving_label: component.serving_label || 'one serving',
    serving_weight_grams: component.serving_weight_grams ?? null,
    serving_volume_ml: component.serving_volume_ml ?? null,
    portion_options: component.portion_options || [],
    provenance: component.provenance || 'community_estimate',
    source_kind: sourceKindForProvenance(component.provenance || 'community_estimate'),
    confidence_score: component.confidence_score,
    nutrients: nutrientArrayToValues(component.nutrients),
    sources: component.sources || [],
    components: (component.components || []).map(componentSnapshotToMealItem),
  });

export const catalogFoodToMealItem = (food) => {
  const version = food.current_version || {};
  const provenance =
    version.provenance || (food.scope === 'personal' ? 'user_entered' : 'official');
  return withPortionSelection({
    key: nextKey('meal-food', food.id),
    food_item: food.id,
    food_version: null,
    catalog_food_version: version.id,
    name: food.name,
    provider_name: food.provider_name,
    origin_type: food.origin_type,
    servings: '1',
    serving_quantity: version.serving_quantity || '1',
    serving_unit: version.serving_unit || 'serving',
    serving_label: version.serving_label || 'one serving',
    serving_weight_grams: version.serving_weight_grams ?? null,
    serving_volume_ml: version.serving_volume_ml ?? null,
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

export const proposalItemToMealItem = (item) => {
  const normalized = withPortionSelection({
    ...item,
    key: item.key,
    food_item: item.food_item_id,
    food_version: item.food_version_id,
    catalog_food_version: item.food_version_id,
    nutrients: Array.isArray(item.nutrients)
      ? nutrientArrayToValues(item.nutrients)
      : item.nutrients || {},
    sources: item.sources || [],
    components: (item.components || []).map(proposalItemToMealItem),
  });
  return {
    ...normalized,
    selected_portion_key: item.selected_portion_key || normalized.selected_portion_key,
  };
};

export const mealItemToProposalItem = (item) => ({
  key: item.key,
  food_item_id: item.food_item ?? null,
  food_version_id: item.food_version || item.catalog_food_version || null,
  name: item.name,
  provider_name: item.provider_name || '',
  origin_type: item.origin_type || 'generic',
  servings: String(item.servings ?? '1'),
  serving_quantity: item.serving_quantity || '1',
  serving_unit: item.serving_unit || 'serving',
  serving_label: item.serving_label || 'one serving',
  serving_weight_grams: item.serving_weight_grams ?? null,
  serving_volume_ml: item.serving_volume_ml ?? null,
  portion_options: item.portion_options || [],
  selected_portion_key: item.selected_portion_key,
  provenance: item.provenance || 'community_estimate',
  source_kind: item.source_kind || sourceKindForProvenance(item.provenance),
  confidence_score: item.confidence_score ?? null,
  is_user_modified: Boolean(item.is_user_modified),
  nutrients: item.nutrients || {},
  sources: item.sources || [],
  components: (item.components || []).map(mealItemToProposalItem),
});

export const savedMealItemToEditableMealItem = (item) => {
  const servings = Number(item.servings);
  return withPortionSelection({
    key: nextKey('saved-meal-item', item.id || item.food_item_id),
    food_item: item.food_item_id,
    food_version: item.food_version_id,
    name: item.food_name,
    provider_name: item.provider_name,
    origin_type: item.origin_type,
    servings: String(servings),
    serving_quantity: item.serving_quantity,
    serving_unit: item.serving_unit,
    serving_label: item.serving_label,
    serving_weight_grams: item.serving_weight_grams ?? null,
    serving_volume_ml: item.serving_volume_ml ?? null,
    portion_options: item.portion_options || [],
    provenance: item.provenance,
    source_kind: sourceKindForProvenance(item.provenance),
    confidence_score: item.confidence_score,
    nutrients: nutrientArrayToValues(item.nutrients, servings),
    sources: item.sources || [],
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
    components: (version.components || [])
      .map(componentSnapshotToMealItem)
      .map(mealItemToProposalItem),
  });
};
