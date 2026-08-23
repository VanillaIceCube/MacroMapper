import AddIcon from '@mui/icons-material/Add';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import SearchIcon from '@mui/icons-material/Search';
import SendIcon from '@mui/icons-material/Send';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  InputAdornment,
  Link,
  List,
  ListItem,
  ListItemText,
  Menu,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useEffect, useState } from 'react';
import {
  acceptMealProposal,
  createMealProposal,
  followUpMealProposal,
  searchFoods,
  updateMealProposal,
} from '../services/mealApiClient';

const sourceLabels = {
  official_verified: { label: 'Official / verified', color: 'success' },
  catalog_estimate: { label: 'Catalog estimate', color: 'info' },
  ai_estimate: { label: 'AI estimate', color: 'warning' },
  user_modified_estimate: { label: 'AI estimate — adjusted by you', color: 'warning' },
};

const nutrientMap = (nutrients = []) =>
  Object.fromEntries(nutrients.map((nutrient) => [nutrient.key, nutrient.amount]));

const formatAmount = (amount) => {
  const numeric = Number(amount);
  return Number.isFinite(numeric)
    ? numeric.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : '—';
};

const NUTRIENT_FIELDS = [
  {
    key: 'calories',
    label: 'Calories',
    unit: 'kcal',
    note: 'Total energy',
    color: 'var(--calorie-color)',
  },
  {
    key: 'protein',
    label: 'Protein',
    unit: 'g',
    note: '4 kcal per gram',
    color: 'var(--protein-color)',
  },
  {
    key: 'carbohydrates',
    label: 'Carbs',
    unit: 'g',
    note: '4 kcal per gram',
    color: 'var(--carbohydrate-color)',
  },
  {
    key: 'fat',
    label: 'Fat',
    unit: 'g',
    note: '9 kcal per gram',
    color: 'var(--fat-color)',
  },
];

const MACRO_CALORIE_FIELDS = [
  { key: 'protein', label: 'protein', caloriesPerGram: 4, color: 'var(--protein-color)' },
  {
    key: 'carbohydrates',
    label: 'carbs',
    caloriesPerGram: 4,
    color: 'var(--carbohydrate-color)',
  },
  { key: 'fat', label: 'fat', caloriesPerGram: 9, color: 'var(--fat-color)' },
];

const servingsValue = (item) => {
  const servings = Number(item.servings);
  return Number.isFinite(servings) && servings > 0 ? servings : 0;
};

const servingDescription = (item) => {
  if (item.serving_label) return item.serving_label;
  const quantity = formatAmount(item.serving_quantity);
  const unit = item.serving_unit || 'serving';
  return `${quantity} ${unit}`;
};

const portionOptions = (item) =>
  item.portion_options?.length
    ? item.portion_options
    : [
        {
          key: 'base',
          label: servingDescription(item),
          unit_label: 'serving',
          serving_multiplier: '1',
        },
      ];

const STANDARD_PORTION_LABELS = {
  g: 'g',
  ml: 'ml',
  oz: 'oz',
  fl_oz: 'fl oz',
  cup: 'cup',
  tbsp: 'tbsp',
  tsp: 'tsp',
};

const nativeMeasurementPortion = (item) =>
  STANDARD_PORTION_LABELS[item.serving_unit]
    ? portionOptions(item).find((option) => option.key === item.serving_unit)
    : null;

const displayedPortionOptions = (item) => {
  const options = portionOptions(item);
  return nativeMeasurementPortion(item)
    ? options.filter((option) => option.key !== 'base')
    : options;
};

const selectedPortion = (item) => {
  const options = portionOptions(item);
  const selected = options.find((option) => option.key === item.selected_portion_key);
  return (selected?.key === 'base' && nativeMeasurementPortion(item)) || selected || options[0];
};

const portionOptionLabel = (option) => STANDARD_PORTION_LABELS[option.key] || option.label;

const roundedNumberString = (value, fractionDigits = 8) =>
  String(Number(value.toFixed(fractionDigits)));

const servingAmountValue = (item) => {
  if (item.servings === '') return '';
  const servings = Number(item.servings);
  const multiplier = Number(selectedPortion(item).serving_multiplier);
  if (!Number.isFinite(servings) || !Number.isFinite(multiplier) || multiplier <= 0) {
    return item.servings;
  }
  return roundedNumberString(servings / multiplier, 6);
};

function perServingNutrient(item, key) {
  const components = item.components || [];
  if (components.length) {
    const knownValues = components
      .map((component) => ({
        value: perServingNutrient(component, key),
        servings: servingsValue(component),
      }))
      .filter(({ value }) => value != null);
    if (!knownValues.length) return null;
    return knownValues.reduce((total, entry) => total + entry.value * entry.servings, 0);
  }
  const value = item.nutrients?.[key];
  if (value == null || value === '') return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function itemNutrientTotal(item, key) {
  const value = perServingNutrient(item, key);
  return value == null ? null : value * servingsValue(item);
}

function mealNutrientTotal(items, key) {
  const knownValues = items
    .map((item) => itemNutrientTotal(item, key))
    .filter((value) => value != null);
  if (!knownValues.length) return null;
  return knownValues.reduce((total, value) => total + value, 0);
}

function calorieContributions(items) {
  const singleComposite = items.length === 1 && items[0].components?.length;
  const chartItems = singleComposite ? items[0].components : items;
  const parentServings = singleComposite ? servingsValue(items[0]) : 1;

  return chartItems.flatMap((item) => {
    const calories = itemNutrientTotal(item, 'calories');
    if (calories == null) return [];
    return [
      {
        key: item.key,
        name: item.name,
        calories: calories * parentServings,
        ...Object.fromEntries(
          MACRO_CALORIE_FIELDS.map(({ key }) => {
            const value = itemNutrientTotal(item, key);
            return [key, value == null ? null : value * parentServings];
          }),
        ),
      },
    ];
  });
}

function summarizedContributions(items) {
  const sorted = calorieContributions(items).sort((a, b) => b.calories - a.calories);
  if (sorted.length <= 5) return sorted;
  const remaining = sorted.slice(4);
  return [
    ...sorted.slice(0, 4),
    {
      key: 'other-components',
      name: `Other (${sorted.length - 4})`,
      calories: remaining.reduce((total, item) => total + item.calories, 0),
      ...Object.fromEntries(
        MACRO_CALORIE_FIELDS.map(({ key }) => [
          key,
          remaining.some((item) => item[key] != null)
            ? remaining.reduce((total, item) => total + (item[key] || 0), 0)
            : null,
        ]),
      ),
    },
  ];
}

function macroCalorieSegments(item) {
  const segments = MACRO_CALORIE_FIELDS.filter((field) => item[field.key] != null).map((field) => ({
    ...field,
    calories: Math.max(Number(item[field.key]) || 0, 0) * field.caloriesPerGram,
  }));
  const total = segments.reduce((sum, segment) => sum + segment.calories, 0);
  return total
    ? segments.map((segment) => ({
        ...segment,
        percentage: (segment.calories / total) * 100,
      }))
    : [];
}

function NutritionCards({
  values,
  ariaLabel,
  compact = false,
  itemName,
  onNutrientChange,
  editableNutrientKeys,
}) {
  return (
    <Box
      aria-label={ariaLabel}
      sx={{
        display: 'grid',
        width: '100%',
        gridTemplateColumns: {
          xs: 'repeat(2, minmax(0, 1fr))',
          sm: 'repeat(4, minmax(0, 1fr))',
        },
        gap: compact ? 0.5 : 0.75,
      }}
    >
      {NUTRIENT_FIELDS.map(({ key, label, unit, note, color }) => {
        const isEditable =
          onNutrientChange && (!editableNutrientKeys || editableNutrientKeys.includes(key));
        return (
          <Paper
            key={key}
            elevation={0}
            sx={{
              minWidth: 0,
              minHeight: compact ? 58 : undefined,
              height: '100%',
              p: compact ? 0.75 : 1,
              border: '1px solid var(--atlas-border)',
              borderTop: `${compact ? 2 : 3}px solid ${color}`,
              bgcolor: 'var(--atlas-paper)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
            }}
          >
            <Typography
              variant={compact ? 'caption' : 'overline'}
              sx={{
                color: 'var(--atlas-ink-muted)',
                lineHeight: 1.1,
                fontWeight: 700,
              }}
            >
              {label}
            </Typography>
            {isEditable ? (
              <TextField
                type="number"
                variant="standard"
                size="small"
                fullWidth
                value={values[key] ?? ''}
                onChange={(event) => onNutrientChange(key, event.target.value)}
                inputProps={{
                  min: 0,
                  step: 'any',
                  'aria-label': `${label} for ${itemName}`,
                }}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <Typography variant="caption">{unit}</Typography>
                    </InputAdornment>
                  ),
                }}
                sx={{
                  '& .MuiInputBase-input': {
                    py: 0.25,
                    fontSize: '1rem',
                    fontWeight: 700,
                    lineHeight: 1.15,
                  },
                }}
              />
            ) : (
              <Stack direction="row" spacing={0.4} alignItems="baseline" sx={{ minWidth: 0 }}>
                <Typography variant={compact ? 'subtitle1' : 'h6'} noWrap sx={{ lineHeight: 1.15 }}>
                  {formatAmount(values[key])}
                </Typography>
                <Typography variant="caption" noWrap sx={{ color: 'var(--atlas-ink-muted)' }}>
                  {unit}
                </Typography>
              </Stack>
            )}
            {!compact && (
              <Typography
                variant="caption"
                sx={{ color: 'var(--atlas-ink-muted)', display: 'block', mt: 0.15 }}
              >
                {note}
              </Typography>
            )}
          </Paper>
        );
      })}
    </Box>
  );
}

function ItemNutritionCards({ item, compact = false, onNutrientChange }) {
  const values = Object.fromEntries(
    NUTRIENT_FIELDS.map(({ key }) => [key, itemNutrientTotal(item, key)]),
  );
  return (
    <NutritionCards
      values={values}
      ariaLabel={`${item.name} macro values`}
      compact={compact}
      itemName={item.name}
      onNutrientChange={onNutrientChange}
      editableNutrientKeys={item.components?.length ? ['calories'] : undefined}
    />
  );
}

function MacroCalorieChart({ values }) {
  const macroCalories = {
    protein: Math.max(Number(values.protein) || 0, 0) * 4,
    carbohydrates: Math.max(Number(values.carbohydrates) || 0, 0) * 4,
    fat: Math.max(Number(values.fat) || 0, 0) * 9,
  };
  const total = Object.values(macroCalories).reduce((sum, value) => sum + value, 0);
  const proteinEnd = total ? (macroCalories.protein / total) * 100 : 0;
  const carbohydrateEnd = total ? proteinEnd + (macroCalories.carbohydrates / total) * 100 : 0;
  const percentages = {
    protein: total ? Math.round((macroCalories.protein / total) * 100) : 0,
    carbohydrates: total ? Math.round((macroCalories.carbohydrates / total) * 100) : 0,
    fat: total ? Math.round((macroCalories.fat / total) * 100) : 0,
  };
  const background = total
    ? `conic-gradient(
        var(--protein-color) 0 ${proteinEnd}%,
        var(--carbohydrate-color) ${proteinEnd}% ${carbohydrateEnd}%,
        var(--fat-color) ${carbohydrateEnd}% 100%
      )`
    : 'var(--atlas-border)';

  return (
    <Paper elevation={0} sx={{ p: 1, border: '1px solid var(--atlas-border)' }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 800, mb: 0.75 }}>
        Macro calorie split
      </Typography>
      <Stack
        direction="row"
        spacing={1.5}
        alignItems="center"
        justifyContent="center"
        sx={{ width: '100%', maxWidth: 380, mx: 'auto' }}
      >
        <Box
          role="img"
          aria-label={`Macro calorie split: protein ${percentages.protein}%, carbs ${percentages.carbohydrates}%, fat ${percentages.fat}%`}
          sx={{
            position: 'relative',
            width: 'clamp(104px, 38%, 144px)',
            aspectRatio: '1 / 1',
            flex: '0 0 auto',
            borderRadius: '50%',
            background,
            display: 'grid',
            placeItems: 'center',
            '&::after': {
              content: '""',
              position: 'absolute',
              inset: '15%',
              borderRadius: '50%',
              bgcolor: 'var(--atlas-paper)',
            },
          }}
        >
          <Box sx={{ position: 'relative', zIndex: 1, textAlign: 'center' }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 800, lineHeight: 1.1 }}>
              {formatAmount(values.calories)}
            </Typography>
            <Typography variant="caption" sx={{ color: 'var(--atlas-ink-muted)' }}>
              kcal
            </Typography>
          </Box>
        </Box>
        <Stack spacing={0.5} sx={{ minWidth: 0, flex: '0 1 auto' }}>
          {[
            ['Protein', values.protein, percentages.protein, 'var(--protein-color)'],
            ['Carbs', values.carbohydrates, percentages.carbohydrates, 'var(--carbohydrate-color)'],
            ['Fat', values.fat, percentages.fat, 'var(--fat-color)'],
          ].map(([label, grams, percentage, color]) => (
            <Stack key={label} direction="row" alignItems="center" spacing={0.75}>
              <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: color }} />
              <Typography variant="caption" sx={{ flex: '0 0 48px' }}>
                {label}
              </Typography>
              <Typography variant="caption" sx={{ fontWeight: 800, whiteSpace: 'nowrap' }}>
                {formatAmount(grams)} g ({percentage}%)
              </Typography>
            </Stack>
          ))}
        </Stack>
      </Stack>
    </Paper>
  );
}

function ComponentCalorieChart({ items }) {
  const contributions = summarizedContributions(items);
  const total = contributions.reduce((sum, item) => sum + item.calories, 0);
  const highestCalories = Math.max(...contributions.map((item) => item.calories), 0);

  return (
    <Paper elevation={0} sx={{ p: 1, border: '1px solid var(--atlas-border)' }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 800, mb: 0.75 }}>
        Calories by component
      </Typography>
      {contributions.length ? (
        <Stack spacing={0.6} aria-label="Component calorie chart">
          {contributions.map((item) => {
            const percentage = total ? (item.calories / total) * 100 : 0;
            const relativeBarWidth = highestCalories ? (item.calories / highestCalories) * 100 : 0;
            const roundedPercentage = Math.round(percentage);
            const segments = macroCalorieSegments(item);
            const stackLabel = segments.length
              ? `${item.name} macro calorie stack: ${segments
                  .map((segment) => `${segment.label} ${formatAmount(segment.calories)} kcal`)
                  .join(', ')}`
              : `${item.name} macro calorie stack unavailable`;
            return (
              <Box
                key={item.key}
                aria-label={`${item.name} ${formatAmount(item.calories)} kcal (${roundedPercentage}%)`}
              >
                <Stack direction="row" spacing={0.75} alignItems="center">
                  <Typography variant="caption" noWrap title={item.name} sx={{ width: 112 }}>
                    {item.name}
                  </Typography>
                  <Box
                    role="img"
                    aria-label={stackLabel}
                    sx={{
                      height: 14,
                      flex: 1,
                      borderRadius: 7,
                      bgcolor: 'var(--atlas-border)',
                      overflow: 'hidden',
                    }}
                  >
                    <Box
                      sx={{
                        height: '100%',
                        width: `${Math.max(relativeBarWidth, item.calories > 0 ? 2 : 0)}%`,
                        display: 'flex',
                        bgcolor: segments.length ? 'transparent' : 'var(--calorie-color)',
                        borderRadius: 7,
                        overflow: 'hidden',
                      }}
                    >
                      {segments.map((segment) => (
                        <Box
                          key={segment.key}
                          sx={{
                            width: `${segment.percentage}%`,
                            bgcolor: segment.color,
                          }}
                        />
                      ))}
                    </Box>
                  </Box>
                  <Typography
                    variant="caption"
                    sx={{ width: 92, textAlign: 'right', whiteSpace: 'nowrap' }}
                  >
                    {formatAmount(item.calories)} kcal ({roundedPercentage}%)
                  </Typography>
                </Stack>
              </Box>
            );
          })}
        </Stack>
      ) : (
        <Typography variant="caption" sx={{ color: 'var(--atlas-ink-muted)' }}>
          Component calories are unavailable.
        </Typography>
      )}
    </Paper>
  );
}

function MacroChart({ items }) {
  const [open, setOpen] = useState(true);
  const values = Object.fromEntries(
    NUTRIENT_FIELDS.map(({ key }) => [key, mealNutrientTotal(items, key)]),
  );

  return (
    <Paper
      component="section"
      aria-label="Meal macro breakdown"
      elevation={0}
      sx={{ p: 1.25, border: '1px solid var(--atlas-border-strong)', bgcolor: 'var(--atlas-bone)' }}
    >
      <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
            Meal nutrition summary
          </Typography>
          <Typography variant="body2" sx={{ color: 'var(--atlas-ink-muted)' }}>
            Full-meal totals from the components below.
          </Typography>
        </Box>
        <Stack direction="row" spacing={0.5} alignItems="center">
          {!open && (
            <Chip
              size="small"
              label={`${formatAmount(values.calories)} kcal`}
              sx={{ fontWeight: 800, bgcolor: 'var(--atlas-paper)' }}
            />
          )}
          <IconButton
            size="small"
            aria-label={`${open ? 'Collapse' : 'Expand'} meal nutrition summary`}
            aria-expanded={open}
            onClick={() => setOpen((current) => !current)}
          >
            {open ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
        </Stack>
      </Stack>
      <Collapse in={open} unmountOnExit>
        <Box sx={{ mt: 1 }}>
          <NutritionCards values={values} ariaLabel="Full meal nutrition values" />
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'minmax(210px, 0.8fr) minmax(0, 1.2fr)' },
              gap: 0.75,
              mt: 0.75,
            }}
          >
            <MacroCalorieChart values={values} />
            <ComponentCalorieChart items={items} />
          </Box>
        </Box>
      </Collapse>
    </Paper>
  );
}

async function responseError(response, fallback) {
  try {
    const body = await response.json();
    if (typeof body.detail === 'string') return body.detail;
    const first = Object.values(body)[0];
    if (Array.isArray(first)) return first[0];
    if (typeof first === 'string') return first;
  } catch (_error) {
    // Use the stable fallback below.
  }
  return fallback;
}

function updateTree(items, key, update) {
  return items.map((item) => {
    if (item.key === key) return update(item);
    return { ...item, components: updateTree(item.components || [], key, update) };
  });
}

function removeFromTree(items, key) {
  return items
    .filter((item) => item.key !== key)
    .map((item) => ({
      ...item,
      components: removeFromTree(item.components || [], key),
    }));
}

function ProposalFood({
  item,
  depth = 0,
  onServings,
  onPortionChange,
  onNutrientChange,
  onRemove,
}) {
  const [componentsOpen, setComponentsOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [nutritionEditing, setNutritionEditing] = useState(false);
  const [actionsAnchorEl, setActionsAnchorEl] = useState(null);
  const source = sourceLabels[item.source_kind] || sourceLabels.ai_estimate;
  const isComponent = depth > 0;
  const options = displayedPortionOptions(item);
  const activePortion = selectedPortion(item);
  const hasDetails =
    item.confidence_score != null || item.provider_name || Boolean(item.sources?.length);
  const accentColor =
    item.source_kind === 'ai_estimate' || item.source_kind === 'user_modified_estimate'
      ? 'var(--atlas-persimmon)'
      : item.source_kind === 'official_verified'
        ? 'var(--atlas-forest)'
        : 'var(--atlas-mineral)';
  return (
    <Paper
      elevation={0}
      sx={{
        ml: depth > 1 ? { xs: 1, sm: 2 } : 0,
        my: isComponent ? 0.25 : 0.35,
        bgcolor: isComponent ? 'var(--atlas-bone)' : 'var(--atlas-paper)',
        border: isComponent
          ? '1px solid var(--atlas-border-strong)'
          : '1px solid var(--atlas-border)',
        borderLeft: `4px solid ${accentColor}`,
        overflow: 'hidden',
      }}
    >
      <Box sx={{ p: 0.6 }}>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: 'minmax(0, 1fr) auto',
              sm: 'minmax(110px, 0.65fr) minmax(280px, 1.7fr) 80px',
              md: '150px minmax(270px, 1fr) auto 80px',
            },
            gridTemplateAreas: {
              xs: '"identity actions" "nutrition nutrition" "controls controls"',
              sm: '"identity nutrition actions" "controls controls controls"',
              md: '"identity nutrition controls actions"',
            },
            columnGap: 0.75,
            rowGap: { xs: 0, sm: 0.5 },
            alignItems: 'center',
          }}
        >
          <Box sx={{ gridArea: 'identity', minWidth: 0, pl: 0.25 }}>
            <Typography
              variant="body2"
              title={item.name}
              sx={{
                color: 'var(--atlas-ink)',
                fontSize: '0.84rem',
                fontWeight: 800,
                lineHeight: 1.15,
                overflowWrap: 'anywhere',
              }}
            >
              {item.name}
            </Typography>
          </Box>
          <Box sx={{ minWidth: 0, gridArea: 'nutrition' }}>
            <ItemNutritionCards
              item={item}
              compact
              onNutrientChange={
                nutritionEditing
                  ? (nutrient, value) => onNutrientChange(item.key, nutrient, value)
                  : undefined
              }
            />
          </Box>
          <Box
            sx={{
              gridArea: 'controls',
              mt: { xs: 1.1, sm: 0 },
              display: 'grid',
              width: '100%',
              gridTemplateColumns: {
                xs: '72px minmax(0, 1fr)',
                sm: '72px 112px',
              },
              gridTemplateAreas: '"quantity portion"',
              alignItems: 'center',
              justifyContent: { sm: 'end' },
              columnGap: 0.75,
            }}
          >
            <TextField
              label="Count"
              type="number"
              size="small"
              value={servingAmountValue(item)}
              onChange={(event) => onServings(item.key, event.target.value, item)}
              inputProps={{ min: 0, step: 1 }}
              sx={{ gridArea: 'quantity', minWidth: 0, width: '100%' }}
            />
            <TextField
              select
              label="Unit"
              size="small"
              value={activePortion.key}
              onChange={(event) => onPortionChange(item.key, event.target.value)}
              disabled={options.length < 2}
              sx={{ gridArea: 'portion', minWidth: 0, width: '100%' }}
            >
              {options.map((option) => (
                <MenuItem key={option.key} value={option.key}>
                  {portionOptionLabel(option)}
                </MenuItem>
              ))}
            </TextField>
          </Box>
          <Stack
            direction="row"
            spacing={0}
            alignItems="center"
            justifyContent="flex-end"
            sx={{ gridArea: 'actions', flexShrink: 0 }}
          >
            {!!item.components?.length && (
              <Button
                size="small"
                color="inherit"
                endIcon={componentsOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                aria-label={`${componentsOpen ? 'Collapse' : 'Expand'} components for ${item.name}`}
                aria-expanded={componentsOpen}
                onClick={() => setComponentsOpen((current) => !current)}
                title={`${componentsOpen ? 'Hide' : 'Show'} components`}
                sx={{
                  minWidth: 0,
                  minHeight: 24,
                  px: 0.35,
                  py: 0,
                  color: 'var(--atlas-ink-muted)',
                  fontWeight: 800,
                  '& .MuiButton-endIcon': { ml: 0.2 },
                }}
              >
                {item.components.length}
              </Button>
            )}
            <IconButton
              size="small"
              aria-label={`More actions for ${item.name}`}
              aria-haspopup="menu"
              aria-expanded={Boolean(actionsAnchorEl)}
              onClick={(event) => setActionsAnchorEl(event.currentTarget)}
              sx={{ p: 0.2 }}
            >
              <MoreVertIcon fontSize="small" />
            </IconButton>
            <Menu
              anchorEl={actionsAnchorEl}
              open={Boolean(actionsAnchorEl)}
              onClose={() => setActionsAnchorEl(null)}
              MenuListProps={{ 'aria-label': `Actions for ${item.name}` }}
            >
              {hasDetails && (
                <MenuItem
                  aria-label={`${detailsOpen ? 'Hide' : 'Show'} estimate details for ${item.name}`}
                  onClick={() => {
                    setDetailsOpen((current) => !current);
                    setActionsAnchorEl(null);
                  }}
                >
                  <InfoOutlinedIcon fontSize="small" sx={{ mr: 1.25 }} />
                  {detailsOpen ? 'Hide details' : 'Estimate details'}
                </MenuItem>
              )}
              <MenuItem
                aria-label={`${nutritionEditing ? 'Finish editing' : 'Edit'} nutrition for ${item.name}`}
                selected={nutritionEditing}
                onClick={() => {
                  setNutritionEditing((current) => !current);
                  setActionsAnchorEl(null);
                }}
              >
                <EditOutlinedIcon fontSize="small" sx={{ mr: 1.25 }} />
                {nutritionEditing ? 'Finish editing' : 'Edit nutrition'}
              </MenuItem>
              <MenuItem
                aria-label={`remove ${item.name}`}
                onClick={() => {
                  setActionsAnchorEl(null);
                  onRemove(item.key);
                }}
                sx={{ color: 'error.main' }}
              >
                <DeleteOutlineIcon fontSize="small" sx={{ mr: 1.25 }} />
                Remove
              </MenuItem>
            </Menu>
          </Stack>
        </Box>
        {hasDetails && (
          <Collapse in={detailsOpen} unmountOnExit>
            <Paper elevation={0} sx={{ mt: 0.5, p: 0.75, border: '1px solid var(--atlas-border)' }}>
              <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mt: 0.25 }}>
                <Chip size="small" label={source.label} color={source.color} variant="outlined" />
                {item.confidence_score != null && (
                  <Chip
                    size="small"
                    label={`${Math.round(Number(item.confidence_score) * 100)}% confidence`}
                    variant="outlined"
                  />
                )}
                {item.provider_name && (
                  <Chip size="small" label={item.provider_name} variant="outlined" />
                )}
              </Stack>
              {!!item.sources?.length && (
                <Stack component="ul" spacing={0.25} sx={{ my: 0.5, pl: 2.25 }}>
                  {item.sources.map((entry) => (
                    <Typography component="li" variant="caption" key={entry.url}>
                      <Link href={entry.url} target="_blank" rel="noopener noreferrer">
                        {entry.title}
                      </Link>
                      {entry.is_official ? ' · official source' : ''}
                    </Typography>
                  ))}
                </Stack>
              )}
            </Paper>
          </Collapse>
        )}
        {!!item.components?.length && (
          <Collapse in={componentsOpen} unmountOnExit>
            <Stack spacing={0.75} sx={{ mt: 0.85 }}>
              {item.components.map((component) => (
                <ProposalFood
                  key={component.key}
                  item={component}
                  depth={depth + 1}
                  onServings={onServings}
                  onPortionChange={onPortionChange}
                  onNutrientChange={onNutrientChange}
                  onRemove={onRemove}
                />
              ))}
            </Stack>
          </Collapse>
        )}
      </Box>
    </Paper>
  );
}

function catalogProposalItem(food) {
  const version = food.current_version;
  const sourceKind =
    version.provenance === 'official'
      ? 'official_verified'
      : version.provenance === 'ai_estimate'
        ? 'ai_estimate'
        : version.provenance === 'user_modified_estimate'
          ? 'user_modified_estimate'
          : 'catalog_estimate';
  const item = {
    key: `catalog-added-${food.id}-${Date.now()}`,
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
    selected_portion_key: 'base',
    provenance: version.provenance,
    source_kind: sourceKind,
    confidence_score: version.confidence_score,
    nutrients: nutrientMap(version.nutrients),
    sources: version.sources.map((source) => ({
      ...source,
      is_official: sourceKind === 'official_verified',
    })),
    components: [],
  };
  item.portion_options = portionOptions(item);
  item.selected_portion_key = item.portion_options.some(
    (option) => option.key === item.serving_unit,
  )
    ? item.serving_unit
    : item.portion_options[0].key;
  return item;
}

export default function MealEstimateDialog({ date, open, token, onClose, onSaved }) {
  const [description, setDescription] = useState('');
  const [proposal, setProposal] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [foods, setFoods] = useState([]);
  const [searching, setSearching] = useState(false);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [followUp, setFollowUp] = useState('');
  const [followUpBusy, setFollowUpBusy] = useState(false);
  const [followUpFeedback, setFollowUpFeedback] = useState(null);

  useEffect(() => {
    if (!open) return;
    setDescription('');
    setProposal(null);
    setError('');
    setQuery('');
    setFoods([]);
    setCatalogOpen(false);
    setFollowUp('');
    setFollowUpBusy(false);
    setFollowUpFeedback(null);
  }, [open]);

  const estimate = async () => {
    if (!description.trim()) {
      setError('Describe the meal you want to estimate.');
      return;
    }
    setBusy(true);
    setError('');
    const response = await createMealProposal(
      { description: description.trim(), entry_date: date },
      token,
    );
    if (response.ok) {
      setProposal(await response.json());
    } else {
      setError(await responseError(response, 'Could not estimate this meal.'));
    }
    setBusy(false);
  };

  const runSearch = async () => {
    setSearching(true);
    setError('');
    const response = await searchFoods(query, token);
    if (response.ok) {
      setFoods(await response.json());
    } else {
      setError(await responseError(response, 'Could not search the food catalog.'));
    }
    setSearching(false);
  };

  const save = async () => {
    if (!proposal.name.trim() || !proposal.items.length) {
      setError('Name the meal and keep at least one food before saving.');
      return;
    }
    setBusy(true);
    setError('');
    const updateResponse = await updateMealProposal(
      proposal.id,
      { name: proposal.name.trim(), items: proposal.items },
      token,
    );
    if (!updateResponse.ok) {
      setError(await responseError(updateResponse, 'Could not save your proposal edits.'));
      setBusy(false);
      return;
    }
    const acceptResponse = await acceptMealProposal(proposal.id, token);
    if (acceptResponse.ok) {
      onSaved('Estimated meal added to your diary.');
    } else {
      setError(await responseError(acceptResponse, 'Could not add this estimate to your diary.'));
    }
    setBusy(false);
  };

  const changeServings = (key, amount, item) => {
    const activePortion = selectedPortion(item);
    const multiplier = Number(activePortion.serving_multiplier);
    const numericAmount = Number(amount);
    const servings =
      amount === '' || !Number.isFinite(numericAmount) || !Number.isFinite(multiplier)
        ? amount
        : roundedNumberString(numericAmount * (multiplier > 0 ? multiplier : 1));
    setProposal((current) => ({
      ...current,
      items: updateTree(current.items, key, (item) => ({
        ...item,
        servings,
        selected_portion_key: activePortion.key,
      })),
    }));
  };

  const changePortion = (key, selectedPortionKey) => {
    setProposal((current) => ({
      ...current,
      items: updateTree(current.items, key, (item) => ({
        ...item,
        selected_portion_key: selectedPortionKey,
      })),
    }));
  };

  const changeNutrient = (key, nutrient, totalValue) => {
    setProposal((current) => ({
      ...current,
      items: updateTree(current.items, key, (item) => {
        const numeric = Number(totalValue);
        if (item.components?.length) {
          const currentCalories = itemNutrientTotal(item, 'calories');
          if (
            nutrient !== 'calories' ||
            totalValue === '' ||
            !Number.isFinite(numeric) ||
            numeric < 0 ||
            !currentCalories
          ) {
            return item;
          }
          const scale = numeric / currentCalories;
          return {
            ...item,
            components: item.components.map((component) => ({
              ...component,
              servings: roundedNumberString(servingsValue(component) * scale),
            })),
          };
        }
        const servings = servingsValue(item);
        const perServingValue =
          totalValue === '' || !Number.isFinite(numeric) || !servings
            ? totalValue
            : String(numeric / servings);
        return {
          ...item,
          nutrients: { ...item.nutrients, [nutrient]: perServingValue },
        };
      }),
    }));
  };

  const removeItem = (key) => {
    setProposal((current) => ({
      ...current,
      items: removeFromTree(current.items, key),
    }));
  };

  const applyFollowUp = async () => {
    const request = followUp.trim();
    if (!request) {
      setFollowUpFeedback({
        severity: 'warning',
        message: 'Describe what you want to add, remove, or correct.',
      });
      return;
    }
    if (!proposal.name.trim() || !proposal.items.length) {
      setFollowUpFeedback({
        severity: 'warning',
        message: 'Name the meal and keep at least one food before asking for a change.',
      });
      return;
    }

    setFollowUpBusy(true);
    setError('');
    setFollowUpFeedback(null);
    try {
      const response = await followUpMealProposal(
        proposal.id,
        {
          follow_up: request,
          name: proposal.name.trim(),
          items: proposal.items,
        },
        token,
      );
      if (response.ok) {
        const result = await response.json();
        if (result.applied) {
          setProposal(result.proposal);
          setFollowUp('');
          setFollowUpFeedback({ severity: 'success', message: result.message });
        } else {
          setFollowUpFeedback({ severity: 'warning', message: result.message });
        }
      } else {
        setFollowUpFeedback({
          severity: 'error',
          message: await responseError(
            response,
            'Could not apply that change. Your current draft is still here.',
          ),
        });
      }
    } catch (_error) {
      setFollowUpFeedback({
        severity: 'error',
        message: 'Could not reach AI. Try again—your current draft and request are still here.',
      });
    } finally {
      setFollowUpBusy(false);
    }
  };

  const dialogBusy = busy || followUpBusy;

  return (
    <Dialog
      open={open}
      onClose={dialogBusy ? undefined : onClose}
      fullWidth
      maxWidth="md"
      sx={{
        '& .MuiDialog-paper': {
          bgcolor: 'var(--atlas-paper)',
          border: '1px solid var(--atlas-border-strong)',
        },
      }}
    >
      <DialogTitle sx={{ bgcolor: 'var(--atlas-persimmon-soft)' }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <AutoAwesomeIcon sx={{ color: 'var(--atlas-persimmon-dark)' }} />
          <span>{proposal ? 'Review meal estimate' : 'Estimate a meal'}</span>
        </Stack>
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={proposal ? 1.25 : 2.5}>
          {error && <Alert severity="error">{error}</Alert>}
          <Alert severity="info" variant="outlined">
            Nutrition values are estimates and may vary. Review and adjust each item before saving.
          </Alert>
          {!proposal ? (
            <>
              <TextField
                label="Describe what you ate"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Double-Double from In-N-Out, no cheese"
                multiline
                minRows={3}
                autoFocus
              />
              <Typography variant="body2" sx={{ color: 'var(--atlas-ink-muted)' }}>
                MacroMapper searches your visible food catalog first. When there is no suitable
                match, GPT prepares a sourced, editable proposal.
              </Typography>
            </>
          ) : (
            <>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                <TextField
                  label="Meal name"
                  value={proposal.name}
                  onChange={(event) =>
                    setProposal((current) => ({ ...current, name: event.target.value }))
                  }
                  fullWidth
                />
                <TextField label="Date" value={date} disabled sx={{ minWidth: 170 }} />
              </Stack>
              <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                <Chip label={`Generated by ${proposal.provider_name}`} variant="outlined" />
                {proposal.provider_model && (
                  <Chip label={`Model ${proposal.provider_model}`} variant="outlined" />
                )}
                {proposal.confidence_score != null && (
                  <Chip
                    label={`${Math.round(Number(proposal.confidence_score) * 100)}% overall confidence`}
                    variant="outlined"
                  />
                )}
              </Stack>
              <MacroChart items={proposal.items} />
              <Stack spacing={1.5}>
                {proposal.items.map((item) => (
                  <ProposalFood
                    key={item.key}
                    item={item}
                    onServings={changeServings}
                    onPortionChange={changePortion}
                    onNutrientChange={changeNutrient}
                    onRemove={removeItem}
                  />
                ))}
              </Stack>
              <Divider />
              <Paper elevation={0} sx={{ p: 1, border: '1px solid var(--atlas-border)' }}>
                <Stack
                  direction="row"
                  alignItems="center"
                  justifyContent="space-between"
                  spacing={1}
                >
                  <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
                    Add another food
                  </Typography>
                  <IconButton
                    size="small"
                    aria-label={`${catalogOpen ? 'Collapse' : 'Expand'} add another food`}
                    aria-expanded={catalogOpen}
                    onClick={() => setCatalogOpen((current) => !current)}
                  >
                    {catalogOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                  </IconButton>
                </Stack>
                <Collapse in={catalogOpen} unmountOnExit>
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    <TextField
                      label="Search catalog"
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      onKeyDown={(event) => event.key === 'Enter' && runSearch()}
                      fullWidth
                    />
                    <Button
                      aria-label="search proposal foods"
                      variant="outlined"
                      onClick={runSearch}
                    >
                      <SearchIcon />
                    </Button>
                  </Stack>
                  {searching ? (
                    <CircularProgress size={24} sx={{ mt: 2 }} />
                  ) : (
                    <List sx={{ maxHeight: 200, overflow: 'auto' }}>
                      {foods.map((food) => (
                        <ListItem
                          key={food.id}
                          secondaryAction={
                            <Button
                              startIcon={<AddIcon />}
                              onClick={() => {
                                setProposal((current) => ({
                                  ...current,
                                  items: [...current.items, catalogProposalItem(food)],
                                }));
                                setFoods((current) =>
                                  current.filter((item) => item.id !== food.id),
                                );
                              }}
                            >
                              Add
                            </Button>
                          }
                        >
                          <ListItemText
                            primary={food.name}
                            secondary={food.provider_name || food.scope}
                          />
                        </ListItem>
                      ))}
                    </List>
                  )}
                </Collapse>
              </Paper>
              <Paper elevation={0} sx={{ p: 1.25, border: '1px solid var(--atlas-border)' }}>
                <Stack spacing={0.75}>
                  <Stack direction="row" spacing={0.75} alignItems="center">
                    <AutoAwesomeIcon
                      fontSize="small"
                      sx={{ color: 'var(--atlas-persimmon-dark)' }}
                    />
                    <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
                      Adjust with AI
                    </Typography>
                  </Stack>
                  <Stack
                    direction={{ xs: 'column', sm: 'row' }}
                    spacing={0.75}
                    alignItems={{ sm: 'flex-end' }}
                  >
                    <TextField
                      label="Ask AI to make changes"
                      value={followUp}
                      onChange={(event) => {
                        setFollowUp(event.target.value);
                        setFollowUpFeedback(null);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                          event.preventDefault();
                          applyFollowUp();
                        }
                      }}
                      placeholder="I also had a medium chocolate milkshake"
                      multiline
                      minRows={1}
                      maxRows={3}
                      size="small"
                      inputProps={{ maxLength: 500 }}
                      disabled={followUpBusy}
                      fullWidth
                    />
                    <Button
                      variant="outlined"
                      color="secondary"
                      startIcon={
                        followUpBusy ? <CircularProgress size={16} color="inherit" /> : <SendIcon />
                      }
                      onClick={applyFollowUp}
                      disabled={followUpBusy || !followUp.trim()}
                      sx={{ whiteSpace: 'nowrap', width: { xs: '100%', sm: 'auto' } }}
                    >
                      {followUpBusy ? 'Applying…' : 'Apply'}
                    </Button>
                  </Stack>
                  {followUpFeedback && (
                    <Alert severity={followUpFeedback.severity} sx={{ py: 0 }}>
                      {followUpFeedback.message}
                    </Alert>
                  )}
                </Stack>
              </Paper>
            </>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={dialogBusy}>
          Cancel
        </Button>
        {!proposal ? (
          <Button variant="contained" color="secondary" onClick={estimate} disabled={dialogBusy}>
            {busy ? 'Estimating…' : 'Create estimate'}
          </Button>
        ) : (
          <Button variant="contained" onClick={save} disabled={dialogBusy}>
            {busy ? 'Saving…' : 'Save to diary'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
