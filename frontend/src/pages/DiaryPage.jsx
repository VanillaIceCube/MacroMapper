import AddIcon from '@mui/icons-material/Add';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import RefreshIcon from '@mui/icons-material/Refresh';
import RestaurantMenuOutlinedIcon from '@mui/icons-material/RestaurantMenuOutlined';
import SearchIcon from '@mui/icons-material/Search';
import TodayOutlinedIcon from '@mui/icons-material/TodayOutlined';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Paper,
  Skeleton,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  createMeal,
  createPersonalFood,
  deleteMeal,
  fetchDailyDiary,
  searchFoods,
  updateMeal,
} from '../services/mealApiClient';
import MealEstimateDialog from '../components/MealEstimateDialog';

const launchNutrients = [
  {
    key: 'calories',
    label: 'Calories',
    unit: 'kcal',
    color: 'var(--calorie-color)',
    background: 'var(--atlas-paper)',
  },
  {
    key: 'protein',
    label: 'Protein',
    unit: 'g',
    color: 'var(--protein-color)',
    background: 'var(--atlas-forest-soft)',
  },
  {
    key: 'carbohydrates',
    label: 'Carbs',
    unit: 'g',
    color: 'var(--carbohydrate-color)',
    background: 'var(--atlas-mineral-soft)',
  },
  {
    key: 'fat',
    label: 'Fat',
    unit: 'g',
    color: 'var(--fat-color)',
    background: 'var(--atlas-persimmon-soft)',
  },
  {
    key: 'fiber',
    label: 'Fiber',
    unit: 'g',
    color: 'var(--fiber-color)',
    background: 'var(--atlas-paper)',
  },
  {
    key: 'sugar',
    label: 'Sugar',
    unit: 'g',
    color: 'var(--sugar-color)',
    background: 'var(--atlas-paper)',
  },
  {
    key: 'sodium',
    label: 'Sodium',
    unit: 'mg',
    color: 'var(--sodium-color)',
    background: 'var(--atlas-paper)',
  },
  {
    key: 'cholesterol',
    label: 'Cholesterol',
    unit: 'mg',
    color: 'var(--cholesterol-color)',
    background: 'var(--atlas-paper)',
  },
];

const macroCalorieFields = [
  { key: 'protein', label: 'protein', caloriesPerGram: 4, color: 'var(--protein-color)' },
  {
    key: 'carbohydrates',
    label: 'carbs',
    caloriesPerGram: 4,
    color: 'var(--carbohydrate-color)',
  },
  { key: 'fat', label: 'fat', caloriesPerGram: 9, color: 'var(--fat-color)' },
];

const provenanceLabels = {
  official: 'Official',
  community_estimate: 'Community',
  ai_estimate: 'AI estimate',
  user_modified_estimate: 'User adjusted',
  user_entered: 'User entered',
};

const emptyPersonalFood = () => ({
  name: '',
  ...Object.fromEntries(launchNutrients.map((nutrient) => [nutrient.key, ''])),
});

const localDate = () => {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
};

const shiftDate = (date, days) => {
  const value = new Date(`${date}T12:00:00`);
  value.setDate(value.getDate() + days);
  return value.toISOString().slice(0, 10);
};

const formatAmount = (amount) => {
  if (amount === null || amount === undefined || amount === '') return '—';
  const numeric = Number(amount);
  return Number.isFinite(numeric)
    ? numeric.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : '—';
};

const formatWholeAmount = (amount) => {
  const numeric = Number(amount);
  return Number.isFinite(numeric) ? Math.round(numeric).toLocaleString() : '—';
};

const mealContextText = (notes) => notes.replace(/^Estimated from:\s*/i, '').trim() || notes;

const diaryDateParts = (date) => {
  const value = new Date(`${date}T12:00:00`);
  return {
    weekday: value.toLocaleDateString(undefined, { weekday: 'long' }),
    date: value.toLocaleDateString(undefined, { month: 'long', day: 'numeric' }),
  };
};

const compactDiaryDate = (date) =>
  new Date(`${date}T12:00:00`).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });

const mealNutrientAmount = (meal, nutrientKey) => {
  let found = false;
  const total = meal.items.reduce((sum, item) => {
    const amount = Number(item.nutrients.find((value) => value.key === nutrientKey)?.amount);
    if (!Number.isFinite(amount)) return sum;
    found = true;
    return sum + amount;
  }, 0);
  return found ? total : null;
};

const mealNutrientText = (meal, nutrientKey) => {
  const amount = mealNutrientAmount(meal, nutrientKey);
  return amount === null ? '—' : formatAmount(amount);
};

const mealItemNutrientAmount = (item, nutrientKey) => {
  const amount = Number(item.nutrients.find((value) => value.key === nutrientKey)?.amount);
  return Number.isFinite(amount) ? amount : null;
};

const mealItemMacroSegments = (item) => {
  const segments = macroCalorieFields.flatMap((field) => {
    const grams = mealItemNutrientAmount(item, field.key);
    if (grams === null) return [];
    return [{ ...field, calories: Math.max(grams, 0) * field.caloriesPerGram }];
  });
  const totalCalories = segments.reduce((total, segment) => total + segment.calories, 0);

  return totalCalories
    ? segments.map((segment) => ({
        ...segment,
        percentage: (segment.calories / totalCalories) * 100,
      }))
    : [];
};

const mealMacroSegments = (meal) => {
  const segments = macroCalorieFields.flatMap((field) => {
    const grams = mealNutrientAmount(meal, field.key);
    if (grams === null) return [];
    return [{ ...field, calories: Math.max(grams, 0) * field.caloriesPerGram }];
  });
  const totalCalories = segments.reduce((total, segment) => total + segment.calories, 0);

  return totalCalories
    ? segments.map((segment) => ({
        ...segment,
        percentage: (segment.calories / totalCalories) * 100,
      }))
    : [];
};

const macroDonutBackground = (segments) => {
  if (!segments.length) return 'var(--atlas-border)';
  let cursor = 0;
  const stops = segments.map((segment) => {
    const start = cursor;
    cursor += segment.percentage;
    return `${segment.color} ${start}% ${cursor}%`;
  });
  return `conic-gradient(${stops.join(', ')})`;
};

async function responseError(response, fallback) {
  try {
    const body = await response.json();
    const firstValue = Object.values(body)[0];
    if (Array.isArray(firstValue)) return firstValue[0];
    if (typeof firstValue === 'string') return firstValue;
  } catch (_error) {
    // Use the stable fallback below.
  }
  return fallback;
}

function MealItemBreakdown({ components }) {
  if (!components?.length) return null;
  return (
    <Box component="ul" sx={{ mt: 0.75, mb: 0, pl: 2.5 }}>
      {components.map((component) => (
        <Box component="li" key={`${component.food_version_id}-${component.food_name}`}>
          <Typography variant="caption">
            {formatAmount(component.servings)} × {component.food_name}
          </Typography>
          <MealItemBreakdown components={component.components} />
        </Box>
      ))}
    </Box>
  );
}

function MealEditor({ date, meal, open, token, onClose, onSaved }) {
  const [name, setName] = useState('');
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState([]);
  const [query, setQuery] = useState('');
  const [foods, setFoods] = useState([]);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [newFood, setNewFood] = useState(emptyPersonalFood);

  const runSearch = useCallback(async () => {
    setSearching(true);
    setError('');
    const response = await searchFoods(query, token);
    if (response.ok) {
      setFoods(await response.json());
    } else {
      setError(await responseError(response, 'Could not search the food catalog.'));
    }
    setSearching(false);
  }, [query, token]);

  useEffect(() => {
    if (!open) return;
    let active = true;
    setName(meal?.name ?? '');
    setNotes(meal?.notes ?? '');
    setItems(
      meal?.items?.map((item) => ({
        food_item: item.food_item_id,
        food_version: item.food_version_id,
        name: item.food_name,
        provider: item.provider_name,
        servings: String(Number(item.servings)),
      })) ?? [],
    );
    setQuery('');
    setError('');
    setNewFood(emptyPersonalFood());
    setSearching(true);
    searchFoods('', token).then(async (response) => {
      if (!active) return;
      if (response.ok) {
        setFoods(await response.json());
      } else {
        setError(await responseError(response, 'Could not search the food catalog.'));
      }
      setSearching(false);
    });
    return () => {
      active = false;
    };
  }, [meal, open, token]);

  const addFood = (food) => {
    setItems((current) => [
      ...current,
      {
        food_item: food.id,
        food_version: null,
        name: food.name,
        provider: food.provider_name,
        servings: '1',
      },
    ]);
  };

  const save = async () => {
    if (!name.trim() || !items.length) {
      setError('Name the meal and add at least one food.');
      return;
    }
    setSaving(true);
    setError('');
    const payload = {
      entry_date: date,
      name: name.trim(),
      notes: notes.trim(),
      item_inputs: items.map((item, order) => ({
        food_item: item.food_item,
        servings: item.servings,
        order,
        ...(item.food_version ? { food_version: item.food_version } : {}),
      })),
    };
    const response = meal
      ? await updateMeal(meal.id, payload, token)
      : await createMeal(payload, token);
    if (response.ok) {
      onSaved(meal ? 'Meal updated.' : 'Meal added.');
    } else {
      setError(await responseError(response, 'Could not save this meal.'));
    }
    setSaving(false);
  };

  const createFood = async () => {
    if (!newFood.name.trim() || !newFood.calories) {
      setError('A food name and calories are required.');
      return;
    }
    const nutrients = Object.fromEntries(
      Object.entries(newFood).filter(([key, value]) => key !== 'name' && value !== ''),
    );
    setSaving(true);
    setError('');
    const response = await createPersonalFood(
      {
        name: newFood.name.trim(),
        origin_type: 'generic',
        provider_name: '',
        definition: {
          serving_quantity: '1',
          serving_unit: 'serving',
          serving_label: 'one serving',
          provenance: 'user_entered',
          confidence_score: null,
          nutrients,
          sources: [],
          components: [],
        },
      },
      token,
    );
    if (response.ok) {
      const food = await response.json();
      addFood(food);
      setFoods((current) => [food, ...current.filter((value) => value.id !== food.id)]);
      setNewFood(emptyPersonalFood());
    } else {
      setError(await responseError(response, 'Could not create this personal food.'));
    }
    setSaving(false);
  };

  return (
    <Dialog
      open={open}
      onClose={saving ? undefined : onClose}
      fullWidth
      maxWidth="md"
      fullScreen={false}
      sx={{
        '& .MuiDialog-paper': {
          bgcolor: 'var(--atlas-paper)',
          border: '1px solid var(--atlas-border-strong)',
          boxShadow: '0 24px 64px rgba(23, 50, 77, 0.16)',
        },
      }}
    >
      <DialogTitle
        sx={{
          bgcolor: 'var(--atlas-mineral-soft)',
          color: 'var(--atlas-ink)',
          borderBottom: '1px solid var(--atlas-border)',
        }}
      >
        <Typography component="span" variant="overline" sx={{ display: 'block' }}>
          {meal ? 'Saved meal' : 'Manual entry'}
        </Typography>
        <Typography component="span" variant="h5">
          {meal ? 'Edit meal' : 'Add meal manually'}
        </Typography>
      </DialogTitle>
      <DialogContent dividers sx={{ bgcolor: 'var(--atlas-paper)', borderColor: 'transparent' }}>
        <Stack spacing={2.5}>
          {error && <Alert severity="error">{error}</Alert>}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField
              label="Meal name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              fullWidth
            />
            <TextField label="Date" type="date" value={date} disabled sx={{ minWidth: 170 }} />
          </Stack>
          <TextField
            label="Notes (optional)"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            multiline
            minRows={2}
          />

          <Box
            sx={{
              p: { xs: 2, sm: 2.5 },
              bgcolor: 'var(--atlas-mineral-soft)',
              border: '1px solid rgba(71, 121, 138, 0.24)',
              borderRadius: 2,
            }}
          >
            <Typography component="h3" variant="h6">
              Meal items
            </Typography>
            {!items.length && (
              <Typography color="text.secondary" sx={{ mt: 1 }}>
                Search below to add foods.
              </Typography>
            )}
            <List disablePadding>
              {items.map((item, index) => (
                <ListItem
                  key={`${item.food_item}-${index}`}
                  disableGutters
                  sx={{ borderBottom: '1px solid var(--atlas-border)' }}
                  secondaryAction={
                    <IconButton
                      aria-label={`remove ${item.name}`}
                      onClick={() =>
                        setItems((current) =>
                          current.filter((_value, itemIndex) => itemIndex !== index),
                        )
                      }
                    >
                      <DeleteOutlineIcon />
                    </IconButton>
                  }
                >
                  <ListItemText
                    primary={item.name}
                    secondary={item.provider || 'Personal or generic food'}
                  />
                  <TextField
                    label="Servings"
                    type="number"
                    value={item.servings}
                    onChange={(event) =>
                      setItems((current) =>
                        current.map((value, itemIndex) =>
                          itemIndex === index ? { ...value, servings: event.target.value } : value,
                        ),
                      )
                    }
                    inputProps={{ min: 0.0001, step: 0.25 }}
                    sx={{ width: 120, mr: 6 }}
                  />
                </ListItem>
              ))}
            </List>
          </Box>

          <Box>
            <Typography component="h3" variant="h6">
              Find a food
            </Typography>
            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
              <TextField
                label="Search catalog"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') runSearch();
                }}
                fullWidth
              />
              <Button
                variant="outlined"
                onClick={runSearch}
                disabled={searching}
                aria-label="search foods"
              >
                <SearchIcon />
              </Button>
            </Stack>
            {searching ? (
              <CircularProgress size={24} sx={{ mt: 2 }} />
            ) : (
              <List
                sx={{
                  maxHeight: 230,
                  mt: 1,
                  overflow: 'auto',
                  borderBlock: '1px solid var(--atlas-border)',
                }}
              >
                {foods.map((food) => (
                  <ListItem
                    key={food.id}
                    disableGutters
                    sx={{ borderBottom: '1px solid var(--atlas-border)' }}
                    secondaryAction={<Button onClick={() => addFood(food)}>Add</Button>}
                  >
                    <ListItemText
                      primary={food.name}
                      secondary={`${food.provider_name || (food.scope === 'personal' ? 'Personal' : 'Shared')} · ${food.current_version?.serving_label || `${food.current_version?.serving_quantity} ${food.current_version?.serving_unit}`}`}
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </Box>

          <Box
            component="details"
            sx={{
              p: { xs: 2, sm: 2.5 },
              bgcolor: 'var(--atlas-persimmon-soft)',
              border: '1px solid rgba(169, 68, 32, 0.24)',
              borderRadius: 2,
            }}
          >
            <Typography
              component="summary"
              variant="h6"
              sx={{ color: 'var(--atlas-persimmon-dark)', cursor: 'pointer' }}
            >
              Create a personal food
            </Typography>
            <Stack spacing={1.5} sx={{ mt: 2 }}>
              <TextField
                label="Food name"
                value={newFood.name}
                onChange={(event) =>
                  setNewFood((current) => ({ ...current, name: event.target.value }))
                }
              />
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr 1fr', sm: 'repeat(4, 1fr)' },
                  gap: 1.5,
                }}
              >
                {launchNutrients.map(({ key, label, unit }) => (
                  <TextField
                    key={key}
                    label={`${label} (${unit})`}
                    type="number"
                    value={newFood[key]}
                    onChange={(event) =>
                      setNewFood((current) => ({ ...current, [key]: event.target.value }))
                    }
                    inputProps={{ min: 0, step: 0.1 }}
                  />
                ))}
              </Box>
              <Button variant="outlined" color="secondary" onClick={createFood} disabled={saving}>
                Create and add food
              </Button>
            </Stack>
          </Box>
        </Stack>
      </DialogContent>
      <DialogActions
        sx={{ bgcolor: 'var(--atlas-paper)', borderTop: '1px solid var(--atlas-border)' }}
      >
        <Button onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button variant="contained" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save meal'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function DiaryPage({ showSnackbar = () => {} }) {
  const [date, setDate] = useState(localDate);
  const [data, setData] = useState({ meals: [], totals: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editor, setEditor] = useState({ open: false, meal: null });
  const [estimateOpen, setEstimateOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const dateInputRef = useRef(null);
  const token = sessionStorage.getItem('accessToken');

  const loadDiary = useCallback(async () => {
    setLoading(true);
    setError('');
    const response = await fetchDailyDiary(date, token);
    if (response.ok) {
      setData(await response.json());
    } else {
      setError(await responseError(response, 'Could not load this day.'));
    }
    setLoading(false);
  }, [date, token]);

  useEffect(() => {
    loadDiary();
  }, [loadDiary]);

  const totalsByKey = useMemo(
    () => Object.fromEntries(data.totals.map((item) => [item.key, item])),
    [data.totals],
  );

  const dailyMacroSummary = useMemo(() => {
    const macros = macroCalorieFields.map((field) => {
      const amount = Number(totalsByKey[field.key]?.amount);
      const grams = Number.isFinite(amount) ? amount : 0;

      return {
        ...field,
        grams,
        calories: grams * field.caloriesPerGram,
      };
    });
    const totalCalories = macros.reduce((total, macro) => total + macro.calories, 0);
    let chartPosition = 0;
    const chartSegments = macros.map((macro) => {
      const percentage = totalCalories ? (macro.calories / totalCalories) * 100 : 0;
      const start = chartPosition;
      chartPosition += percentage;

      return {
        ...macro,
        percentage,
        gradientStop: `${macro.color} ${start}% ${chartPosition}%`,
      };
    });

    return {
      macros: chartSegments,
      totalCalories,
      background: totalCalories
        ? `conic-gradient(${chartSegments.map((macro) => macro.gradientStop).join(', ')})`
        : 'var(--atlas-border)',
    };
  }, [totalsByKey]);

  const mealCalorieSummary = useMemo(() => {
    const contributions = data.meals
      .flatMap((meal) => {
        const calories = mealNutrientAmount(meal, 'calories');
        return calories === null
          ? []
          : [
              {
                key: meal.id,
                name: meal.name,
                calories: Math.max(calories, 0),
                ...Object.fromEntries(
                  macroCalorieFields.map(({ key }) => [key, mealNutrientAmount(meal, key)]),
                ),
              },
            ];
      })
      .sort((first, second) => second.calories - first.calories);
    const displayedContributions =
      contributions.length > 5
        ? [
            ...contributions.slice(0, 4),
            {
              key: 'other-meals',
              name: `Other meals (${contributions.length - 4})`,
              calories: contributions
                .slice(4)
                .reduce((total, contribution) => total + contribution.calories, 0),
              ...Object.fromEntries(
                macroCalorieFields.map(({ key }) => [
                  key,
                  contributions.slice(4).some((contribution) => contribution[key] !== null)
                    ? contributions
                        .slice(4)
                        .reduce((total, contribution) => total + (contribution[key] || 0), 0)
                    : null,
                ]),
              ),
            },
          ]
        : contributions;
    const totalCalories = displayedContributions.reduce(
      (total, contribution) => total + contribution.calories,
      0,
    );
    const highestCalories = Math.max(
      ...displayedContributions.map((contribution) => contribution.calories),
      0,
    );
    return {
      totalCalories,
      meals: displayedContributions.map((contribution) => {
        const macroSegments = macroCalorieFields
          .filter(({ key }) => contribution[key] !== null)
          .map((field) => ({
            ...field,
            calories: Math.max(Number(contribution[field.key]) || 0, 0) * field.caloriesPerGram,
          }));
        const macroCalories = macroSegments.reduce((total, segment) => total + segment.calories, 0);

        return {
          ...contribution,
          percentage: totalCalories ? (contribution.calories / totalCalories) * 100 : 0,
          relativeBarWidth: highestCalories ? (contribution.calories / highestCalories) * 100 : 0,
          macroSegments: macroCalories
            ? macroSegments.map((segment) => ({
                ...segment,
                percentage: (segment.calories / macroCalories) * 100,
              }))
            : [],
        };
      }),
    };
  }, [data.meals]);

  const removeMeal = async () => {
    const response = await deleteMeal(pendingDelete.id, token);
    if (response.ok) {
      setPendingDelete(null);
      showSnackbar('success', 'Meal deleted.');
      await loadDiary();
    } else {
      setPendingDelete(null);
      setError(await responseError(response, 'Could not delete this meal.'));
    }
  };

  const dateParts = diaryDateParts(date);
  const isToday = date === localDate();

  return (
    <Box className="atlas-contours" sx={{ minHeight: 'calc(100vh - 65px)' }}>
      <Container maxWidth="lg" sx={{ py: { xs: 2.5, sm: 4.5 } }}>
        <Stack spacing={{ xs: 2.5, sm: 3 }}>
          <Stack
            direction={{ xs: 'column', md: 'row' }}
            alignItems={{ md: 'flex-end' }}
            justifyContent="space-between"
            spacing={1.5}
          >
            <Box>
              <Typography
                variant="overline"
                sx={{ color: 'var(--atlas-forest-dark)', fontWeight: 700, letterSpacing: '0.12em' }}
              >
                Daily nutrition
              </Typography>
              <Typography
                component="h1"
                variant="h3"
                sx={{ fontSize: { xs: '2.4rem', sm: '3.35rem' }, lineHeight: 1.02 }}
              >
                Meal diary
              </Typography>
              <Typography sx={{ mt: 0.75, color: 'var(--atlas-ink-muted)' }}>
                Log meals and see how your nutrition adds up.
              </Typography>
            </Box>
            <Stack
              component="nav"
              aria-label="diary date navigation"
              direction="row"
              alignItems="center"
              spacing={0.75}
              sx={{ alignSelf: { xs: 'flex-start', md: 'auto' } }}
            >
              <Paper
                elevation={0}
                sx={{
                  position: 'relative',
                  p: 0.375,
                  bgcolor: 'var(--atlas-paper)',
                  color: 'var(--atlas-ink)',
                  border: '1px solid var(--atlas-border)',
                  borderRadius: 999,
                }}
              >
                <Stack direction="row" alignItems="center" spacing={0.125}>
                  <IconButton
                    aria-label="previous day"
                    onClick={() => setDate((current) => shiftDate(current, -1))}
                    sx={{ width: 44, height: 44 }}
                  >
                    <ChevronLeftIcon />
                  </IconButton>
                  <Button
                    aria-label={`choose diary date, current date ${date}`}
                    startIcon={<CalendarMonthOutlinedIcon />}
                    onClick={() => {
                      if (dateInputRef.current?.showPicker) {
                        dateInputRef.current.showPicker();
                      } else {
                        dateInputRef.current?.click();
                      }
                    }}
                    sx={{
                      minWidth: { xs: 126, sm: 142 },
                      minHeight: 40,
                      px: 1.25,
                      color: 'var(--atlas-ink)',
                      fontWeight: 800,
                    }}
                  >
                    {isToday ? 'Today' : compactDiaryDate(date)}
                  </Button>
                  <IconButton
                    aria-label="next day"
                    onClick={() => setDate((current) => shiftDate(current, 1))}
                    sx={{ width: 44, height: 44 }}
                  >
                    <ChevronRightIcon />
                  </IconButton>
                </Stack>
                <Box
                  component="input"
                  ref={dateInputRef}
                  aria-label="diary date"
                  type="date"
                  value={date}
                  onChange={(event) => setDate(event.target.value)}
                  tabIndex={-1}
                  sx={{
                    position: 'absolute',
                    width: 1,
                    height: 1,
                    overflow: 'hidden',
                    opacity: 0,
                    pointerEvents: 'none',
                  }}
                />
              </Paper>
              {!isToday && (
                <IconButton
                  aria-label="return to today"
                  onClick={() => setDate(localDate())}
                  sx={{
                    width: 44,
                    height: 44,
                    color: 'var(--atlas-mineral-dark)',
                    border: '1px solid transparent',
                    '&:hover': { borderColor: 'var(--atlas-border)' },
                  }}
                >
                  <TodayOutlinedIcon />
                </IconButton>
              )}
            </Stack>
          </Stack>

          {error && (
            <Alert
              severity="error"
              action={
                <Button
                  color="inherit"
                  size="small"
                  startIcon={<RefreshIcon />}
                  onClick={loadDiary}
                >
                  Try again
                </Button>
              }
            >
              {error}
            </Alert>
          )}

          <Paper
            component="section"
            aria-labelledby="daily-totals-heading"
            elevation={0}
            sx={{
              p: { xs: 2, sm: 2.5 },
              bgcolor: 'var(--atlas-paper)',
              border: '1px solid var(--atlas-border)',
              borderRadius: 2.5,
            }}
          >
            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              justifyContent="space-between"
              spacing={0.5}
              sx={{ mb: 1.75 }}
            >
              <Typography id="daily-totals-heading" component="h2" variant="h5">
                Daily summary
              </Typography>
              <Typography variant="body2" sx={{ color: 'var(--atlas-ink-muted)' }}>
                Saved nutrition for {isToday ? 'today' : `${dateParts.weekday}, ${dateParts.date}`}
              </Typography>
            </Stack>
            <Box
              aria-label="Daily nutrition totals"
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(4, 1fr)' },
                gap: 1,
              }}
            >
              {launchNutrients.map((nutrient) => (
                <Paper
                  key={nutrient.key}
                  elevation={0}
                  sx={{
                    minWidth: 0,
                    p: { xs: 1.25, sm: 1.5 },
                    bgcolor: 'var(--atlas-paper)',
                    border: '1px solid var(--atlas-border)',
                    borderTop: `3px solid ${nutrient.color}`,
                    borderRadius: 1.5,
                  }}
                >
                  <Typography
                    variant="overline"
                    sx={{
                      display: 'block',
                      color: nutrient.color,
                      fontWeight: 800,
                      lineHeight: 1.1,
                    }}
                  >
                    {nutrient.label}
                  </Typography>
                  {loading ? (
                    <Skeleton width="72%" height={34} />
                  ) : (
                    <Stack direction="row" alignItems="baseline" spacing={0.5} sx={{ mt: 0.5 }}>
                      <Typography
                        variant="h5"
                        noWrap
                        className="numeric-data"
                        sx={{
                          minWidth: 0,
                          fontWeight: 750,
                          fontSize: { xs: '1.25rem', sm: '1.5rem' },
                        }}
                      >
                        {totalsByKey[nutrient.key]
                          ? formatAmount(totalsByKey[nutrient.key].amount)
                          : '—'}
                      </Typography>
                      <Typography variant="caption" noWrap sx={{ color: 'var(--atlas-ink-muted)' }}>
                        {nutrient.unit}
                      </Typography>
                    </Stack>
                  )}
                </Paper>
              ))}
            </Box>

            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: {
                  xs: '1fr',
                  md: 'minmax(320px, 0.65fr) minmax(0, 1.35fr)',
                },
                gap: 1,
                mt: 1,
              }}
            >
              <Paper
                component="figure"
                aria-label="Macro calorie split"
                elevation={0}
                sx={{
                  m: 0,
                  p: { xs: 1.25, sm: 1.5 },
                  bgcolor: 'var(--atlas-paper)',
                  border: '1px solid var(--atlas-border)',
                  borderRadius: 1.5,
                }}
              >
                <Typography
                  component="figcaption"
                  variant="subtitle2"
                  sx={{ fontWeight: 800, mb: 0.75 }}
                >
                  Macro calorie split
                </Typography>
                {loading ? (
                  <Stack direction="row" spacing={1.5} alignItems="center" justifyContent="center">
                    <Skeleton variant="circular" width={128} height={128} />
                    <Stack spacing={0.5} sx={{ width: 120 }}>
                      {[0, 1, 2].map((row) => (
                        <Skeleton key={row} />
                      ))}
                    </Stack>
                  </Stack>
                ) : (
                  <Stack
                    direction="row"
                    spacing={1}
                    alignItems="center"
                    justifyContent="center"
                    sx={{ width: '100%', maxWidth: 310, mx: 'auto' }}
                  >
                    <Box
                      role="img"
                      aria-label={`Macro calorie split: ${dailyMacroSummary.macros
                        .map((macro) => `${macro.label} ${Math.round(macro.percentage)} percent`)
                        .join(', ')}`}
                      sx={{
                        position: 'relative',
                        width: 'clamp(120px, 44%, 140px)',
                        aspectRatio: '1 / 1',
                        flex: '0 0 auto',
                        borderRadius: '50%',
                        background: dailyMacroSummary.background,
                        display: 'grid',
                        placeItems: 'center',
                        '&::after': {
                          content: '""',
                          position: 'absolute',
                          width: '58%',
                          aspectRatio: '1 / 1',
                          borderRadius: '50%',
                          bgcolor: 'var(--atlas-paper)',
                        },
                      }}
                    >
                      <Box sx={{ position: 'relative', zIndex: 1, textAlign: 'center' }}>
                        <Typography
                          variant="subtitle1"
                          className="numeric-data"
                          sx={{ fontWeight: 800, lineHeight: 1.1 }}
                        >
                          {totalsByKey.calories
                            ? formatWholeAmount(totalsByKey.calories.amount)
                            : '—'}
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'var(--atlas-ink-muted)' }}>
                          kcal
                        </Typography>
                      </Box>
                    </Box>
                    <Stack spacing={0.5} sx={{ minWidth: 0, flex: '0 1 auto' }}>
                      {dailyMacroSummary.macros.map((macro) => (
                        <Stack key={macro.key} direction="row" alignItems="center" spacing={0.75}>
                          <Box
                            aria-hidden="true"
                            sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: macro.color }}
                          />
                          <Typography variant="caption" sx={{ flex: '0 0 48px' }}>
                            {macro.label === 'carbs'
                              ? 'Carbs'
                              : `${macro.label.charAt(0).toUpperCase()}${macro.label.slice(1)}`}
                          </Typography>
                          <Typography
                            variant="caption"
                            className="numeric-data"
                            sx={{ fontWeight: 800, whiteSpace: 'nowrap' }}
                          >
                            {formatWholeAmount(macro.grams)} g ({Math.round(macro.percentage)}%)
                          </Typography>
                        </Stack>
                      ))}
                    </Stack>
                  </Stack>
                )}
              </Paper>

              <Paper
                component="figure"
                aria-label="Calories by meal"
                elevation={0}
                sx={{
                  m: 0,
                  p: { xs: 1.25, sm: 1.5 },
                  bgcolor: 'var(--atlas-paper)',
                  border: '1px solid var(--atlas-border)',
                  borderRadius: 1.5,
                }}
              >
                <Typography
                  component="figcaption"
                  variant="subtitle2"
                  sx={{ fontWeight: 800, mb: 1 }}
                >
                  Calories by meal
                </Typography>

                {loading ? (
                  <Stack spacing={0.75}>
                    {[0, 1, 2].map((row) => (
                      <Skeleton key={row} variant="rounded" height={20} />
                    ))}
                  </Stack>
                ) : mealCalorieSummary.meals.length ? (
                  <Stack spacing={0.8} aria-label="Meal calorie chart">
                    {mealCalorieSummary.meals.map((meal) => {
                      const stackLabel = meal.macroSegments.length
                        ? `${meal.name} macro calorie stack: ${meal.macroSegments
                            .map(
                              (segment) =>
                                `${segment.label} ${formatWholeAmount(
                                  segment.calories,
                                )} kilocalories`,
                            )
                            .join(', ')}`
                        : `${meal.name} macro calorie stack unavailable`;

                      return (
                        <Box
                          key={meal.key}
                          aria-label={`${meal.name} ${formatWholeAmount(
                            meal.calories,
                          )} kilocalories (${Math.round(meal.percentage)} percent)`}
                        >
                          <Stack
                            direction="row"
                            spacing={0.75}
                            alignItems="center"
                            sx={{ minWidth: 0 }}
                          >
                            <Box
                              sx={{
                                width: { xs: 104, sm: 180, lg: 240 },
                                flex: '0 0 auto',
                                height: '2rem',
                                display: 'flex',
                                alignItems: 'center',
                              }}
                            >
                              <Typography
                                variant="caption"
                                title={meal.name}
                                sx={{
                                  display: '-webkit-box',
                                  WebkitBoxOrient: 'vertical',
                                  WebkitLineClamp: 2,
                                  overflow: 'hidden',
                                  lineHeight: 1.2,
                                }}
                              >
                                {meal.name}
                              </Typography>
                            </Box>
                            <Box
                              role="img"
                              aria-label={stackLabel}
                              sx={{
                                height: 20,
                                minWidth: 0,
                                flex: 1,
                                borderRadius: 10,
                                bgcolor: 'var(--atlas-border)',
                                overflow: 'hidden',
                              }}
                            >
                              <Box
                                sx={{
                                  display: 'flex',
                                  width: `${Math.max(
                                    meal.relativeBarWidth,
                                    meal.calories > 0 ? 2 : 0,
                                  )}%`,
                                  height: '100%',
                                  bgcolor: meal.macroSegments.length
                                    ? 'transparent'
                                    : 'var(--calorie-color)',
                                  borderRadius: 10,
                                  overflow: 'hidden',
                                }}
                              >
                                {meal.macroSegments.map((segment) => (
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
                              className="numeric-data"
                              sx={{
                                width: { xs: 92, sm: 106 },
                                flex: '0 0 auto',
                                color: 'var(--atlas-ink-muted)',
                                fontSize: { xs: '0.68rem', sm: '0.75rem' },
                                textAlign: 'right',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {formatWholeAmount(meal.calories)} kcal ({Math.round(meal.percentage)}
                              %)
                            </Typography>
                          </Stack>
                        </Box>
                      );
                    })}
                  </Stack>
                ) : (
                  <Typography variant="body2" sx={{ color: 'var(--atlas-ink-muted)' }}>
                    Add a meal to see its calorie contribution.
                  </Typography>
                )}
              </Paper>
            </Box>
          </Paper>

          <Box component="section" aria-labelledby="meals-heading">
            <Stack
              direction={{ xs: 'column', md: 'row' }}
              justifyContent="space-between"
              alignItems={{ md: 'flex-end' }}
              spacing={1.5}
              sx={{ mb: 1.5 }}
            >
              <Box>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <Typography id="meals-heading" component="h2" variant="h5">
                    Meal log
                  </Typography>
                  {!loading && (
                    <Stack direction="row" spacing={0.75}>
                      <Chip
                        size="small"
                        label={`${data.meals.length} ${data.meals.length === 1 ? 'entry' : 'entries'}`}
                        sx={{
                          bgcolor: 'var(--atlas-forest-soft)',
                          color: 'var(--atlas-forest-dark)',
                        }}
                      />
                      <Chip
                        size="small"
                        label={`${data.meals.reduce(
                          (total, meal) => total + meal.items.length,
                          0,
                        )} saved foods`}
                        sx={{ bgcolor: 'var(--atlas-mineral-soft)', color: 'var(--atlas-ink)' }}
                      />
                    </Stack>
                  )}
                </Stack>
                <Typography variant="body2" sx={{ mt: 0.25, color: 'var(--atlas-ink-muted)' }}>
                  Food calories, serving context, confidence, provenance, and macro balance for each
                  meal.
                </Typography>
              </Box>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                <Button
                  variant="contained"
                  color="secondary"
                  startIcon={<AutoAwesomeIcon />}
                  onClick={() => setEstimateOpen(true)}
                  sx={{ minHeight: 44 }}
                >
                  Estimate meal
                </Button>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={() => setEditor({ open: true, meal: null })}
                  sx={{ minHeight: 44 }}
                >
                  Add manually
                </Button>
              </Stack>
            </Stack>
            {loading ? (
              <Stack spacing={1} aria-label="loading diary">
                {[0, 1, 2].map((value) => (
                  <Skeleton key={value} variant="rounded" height={68} />
                ))}
              </Stack>
            ) : !data.meals.length ? (
              <Paper
                elevation={0}
                sx={{
                  p: { xs: 3, sm: 4.5 },
                  textAlign: 'center',
                  bgcolor: 'var(--atlas-paper)',
                  color: 'var(--atlas-ink)',
                  border: '1px dashed var(--atlas-border-strong)',
                  borderRadius: 2.5,
                }}
              >
                <RestaurantMenuOutlinedIcon
                  sx={{ fontSize: 42, color: 'var(--atlas-forest)', mb: 1 }}
                />
                <Typography variant="h6">Nothing logged yet</Typography>
                <Typography sx={{ mt: 0.5, color: 'var(--atlas-ink-muted)' }}>
                  Estimate a meal or add foods manually to start this day’s log.
                </Typography>
              </Paper>
            ) : (
              <>
                <Stack spacing={1.25} aria-label="meal log">
                  {data.meals.map((meal, index) => {
                    const calories = mealNutrientAmount(meal, 'calories');
                    const dailyCalories = Number(totalsByKey.calories?.amount);
                    const dailyShare =
                      calories !== null && Number.isFinite(dailyCalories) && dailyCalories > 0
                        ? Math.round((calories / dailyCalories) * 100)
                        : null;
                    const mealConfidence = Number(meal.confidence_score);
                    const hasMealConfidence =
                      meal.confidence_score !== null && Number.isFinite(mealConfidence);
                    const macroSegments = mealMacroSegments(meal);
                    const highestFoodCalories = Math.max(
                      ...meal.items.map((item) => mealItemNutrientAmount(item, 'calories') ?? 0),
                    );

                    return (
                      <Paper
                        component="article"
                        key={meal.id}
                        elevation={0}
                        sx={{
                          p: 2,
                          bgcolor: 'var(--atlas-paper)',
                          border: '1px solid var(--atlas-border)',
                          borderRadius: 2,
                        }}
                      >
                        <Stack
                          direction={{ xs: 'column', sm: 'row' }}
                          justifyContent="space-between"
                          alignItems={{ sm: 'flex-start' }}
                          spacing={1.5}
                        >
                          <Box sx={{ minWidth: 0, flex: 1 }}>
                            <Typography
                              variant="overline"
                              sx={{
                                color: 'var(--atlas-mineral-dark)',
                                fontWeight: 800,
                                lineHeight: 1,
                              }}
                            >
                              Meal {String(index + 1).padStart(2, '0')}
                            </Typography>
                            <Typography
                              component="h3"
                              variant="h6"
                              sx={{ mt: 0.25, fontWeight: 750, lineHeight: 1.25 }}
                            >
                              {meal.name}
                            </Typography>
                            <Stack
                              direction="row"
                              spacing={0.75}
                              useFlexGap
                              flexWrap="wrap"
                              sx={{ mt: 1 }}
                            >
                              <Chip
                                size="small"
                                label={`${meal.items.length} ${meal.items.length === 1 ? 'food' : 'foods'}`}
                                sx={{
                                  bgcolor: 'var(--atlas-mineral-soft)',
                                  color: 'var(--atlas-ink)',
                                }}
                              />
                              {dailyShare !== null && (
                                <Chip
                                  size="small"
                                  label={`${dailyShare}% of daily calories`}
                                  sx={{
                                    bgcolor: 'var(--atlas-persimmon-soft)',
                                    color: 'var(--atlas-persimmon-dark)',
                                  }}
                                />
                              )}
                              {hasMealConfidence && (
                                <Chip
                                  size="small"
                                  label={`${Math.round(mealConfidence * 100)}% confidence`}
                                  sx={{
                                    bgcolor: 'var(--atlas-forest-soft)',
                                    color: 'var(--atlas-forest-dark)',
                                  }}
                                />
                              )}
                            </Stack>
                          </Box>
                          <Stack
                            direction="row"
                            alignItems="center"
                            justifyContent="flex-end"
                            spacing={0.25}
                            sx={{ width: { xs: '100%', sm: 'auto' } }}
                          >
                            <IconButton
                              aria-label={`edit ${meal.name}`}
                              onClick={() => setEditor({ open: true, meal })}
                              sx={{ width: 44, height: 44, color: 'var(--atlas-forest-dark)' }}
                            >
                              <EditOutlinedIcon />
                            </IconButton>
                            <IconButton
                              aria-label={`delete ${meal.name}`}
                              onClick={() => setPendingDelete(meal)}
                              sx={{ width: 44, height: 44, color: 'var(--atlas-persimmon-dark)' }}
                            >
                              <DeleteOutlineIcon />
                            </IconButton>
                          </Stack>
                        </Stack>

                        <Box
                          sx={{
                            display: 'grid',
                            gridTemplateColumns: {
                              xs: '1fr',
                              md: 'minmax(0, 1.35fr) minmax(320px, 0.65fr)',
                            },
                            gap: { xs: 1.5, md: 2.5 },
                            mt: 2,
                            pt: 2,
                            borderTop: '1px solid var(--atlas-border)',
                          }}
                        >
                          <Box sx={{ minWidth: 0 }}>
                            <Typography
                              variant="overline"
                              sx={{
                                color: 'var(--atlas-ink-muted)',
                                fontWeight: 800,
                                lineHeight: 1,
                              }}
                            >
                              Foods &amp; servings
                            </Typography>
                            <Box
                              role="table"
                              aria-label={`${meal.name} food breakdown`}
                              sx={{
                                mt: 0.75,
                                border: '1px solid var(--atlas-border)',
                                borderRadius: 0.75,
                                overflow: 'hidden',
                              }}
                            >
                              <Box
                                role="row"
                                sx={{
                                  display: { xs: 'none', sm: 'grid' },
                                  gridTemplateColumns: 'minmax(0, 1fr) 104px 92px 122px',
                                  gap: 1,
                                  px: 1.25,
                                  py: 0.65,
                                  bgcolor: 'var(--atlas-bone)',
                                  borderBottom: '1px solid var(--atlas-border)',
                                }}
                              >
                                {['Food', 'Calories', 'Confidence', 'Provenance'].map((label) => (
                                  <Typography
                                    key={label}
                                    role="columnheader"
                                    variant="caption"
                                    sx={{ color: 'var(--atlas-ink-muted)', fontWeight: 800 }}
                                  >
                                    {label}
                                  </Typography>
                                ))}
                              </Box>
                              {meal.items.map((item, itemIndex) => {
                                const itemCalories = mealItemNutrientAmount(item, 'calories');
                                const itemMacroSegments = mealItemMacroSegments(item);
                                const confidence = Number(item.confidence_score);
                                const hasConfidence =
                                  item.confidence_score !== null && Number.isFinite(confidence);
                                const itemContext = [item.provider_name, item.serving_label]
                                  .filter(Boolean)
                                  .join(' · ');

                                return (
                                  <Box
                                    key={item.id}
                                    role="row"
                                    sx={{
                                      display: 'grid',
                                      gridTemplateColumns: {
                                        xs: 'repeat(3, minmax(0, 1fr))',
                                        sm: 'minmax(0, 1fr) 104px 92px 122px',
                                      },
                                      gap: { xs: 0.75, sm: 1 },
                                      px: 1.25,
                                      py: 1,
                                      borderBottom:
                                        itemIndex < meal.items.length - 1
                                          ? '1px solid var(--atlas-border)'
                                          : 'none',
                                    }}
                                  >
                                    <Box
                                      role="cell"
                                      sx={{
                                        minWidth: 0,
                                        gridColumn: { xs: '1 / -1', sm: 'auto' },
                                      }}
                                    >
                                      <Typography
                                        variant="body2"
                                        sx={{ fontWeight: 800, lineHeight: 1.25 }}
                                      >
                                        {formatAmount(item.servings)} × {item.food_name}
                                      </Typography>
                                      {itemContext && (
                                        <Typography
                                          variant="caption"
                                          sx={{
                                            display: 'block',
                                            mt: 0.2,
                                            color: 'var(--atlas-ink-muted)',
                                          }}
                                        >
                                          {itemContext}
                                        </Typography>
                                      )}
                                    </Box>
                                    <Box role="cell" sx={{ minWidth: 0 }}>
                                      <Typography
                                        variant="caption"
                                        sx={{
                                          display: { sm: 'none' },
                                          color: 'var(--atlas-ink-muted)',
                                        }}
                                      >
                                        Calories
                                      </Typography>
                                      <Typography
                                        variant="body2"
                                        className="numeric-data"
                                        sx={{ fontWeight: 800, color: 'var(--calorie-color)' }}
                                      >
                                        {formatWholeAmount(itemCalories)} kcal
                                      </Typography>
                                      <Box
                                        sx={{
                                          mt: 0.35,
                                          width: '100%',
                                          height: 4,
                                          bgcolor: 'var(--atlas-border)',
                                          borderRadius: 999,
                                          overflow: 'hidden',
                                        }}
                                      >
                                        <Box
                                          role="img"
                                          aria-label={
                                            itemMacroSegments.length
                                              ? `${item.food_name} macro calorie stack: ${itemMacroSegments
                                                  .map(
                                                    (segment) =>
                                                      `${segment.label} ${formatWholeAmount(
                                                        segment.calories,
                                                      )} kilocalories`,
                                                  )
                                                  .join(', ')}`
                                              : `${item.food_name} macro calorie stack unavailable`
                                          }
                                          sx={{
                                            display: 'flex',
                                            width: `${
                                              itemCalories !== null && highestFoodCalories > 0
                                                ? (itemCalories / highestFoodCalories) * 100
                                                : 0
                                            }%`,
                                            height: '100%',
                                            bgcolor: itemMacroSegments.length
                                              ? 'transparent'
                                              : 'var(--calorie-color)',
                                            borderRadius: 999,
                                            overflow: 'hidden',
                                          }}
                                        >
                                          {itemMacroSegments.map((segment) => (
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
                                    </Box>
                                    <Box role="cell" sx={{ minWidth: 0 }}>
                                      <Typography
                                        variant="caption"
                                        sx={{
                                          display: { sm: 'none' },
                                          color: 'var(--atlas-ink-muted)',
                                        }}
                                      >
                                        Confidence
                                      </Typography>
                                      <Typography
                                        variant="body2"
                                        className="numeric-data"
                                        sx={{ fontWeight: 750 }}
                                      >
                                        {hasConfidence
                                          ? `${Math.round(confidence * 100)}%`
                                          : 'Not scored'}
                                      </Typography>
                                    </Box>
                                    <Box role="cell" sx={{ minWidth: 0 }}>
                                      <Typography
                                        variant="caption"
                                        sx={{
                                          display: { sm: 'none' },
                                          color: 'var(--atlas-ink-muted)',
                                        }}
                                      >
                                        Provenance
                                      </Typography>
                                      <Typography variant="body2" sx={{ fontWeight: 750 }}>
                                        {provenanceLabels[item.provenance] || 'Unknown'}
                                      </Typography>
                                    </Box>
                                  </Box>
                                );
                              })}
                            </Box>
                            {meal.notes && (
                              <Box
                                sx={{
                                  mt: 1.25,
                                  px: 1.25,
                                  py: 1,
                                  bgcolor: 'var(--atlas-bone)',
                                  borderLeft: '3px solid var(--atlas-mineral)',
                                  borderRadius: 1,
                                }}
                              >
                                <Typography
                                  variant="caption"
                                  sx={{
                                    display: 'block',
                                    color: 'var(--atlas-ink-muted)',
                                    fontWeight: 800,
                                  }}
                                >
                                  Context
                                </Typography>
                                <Typography
                                  variant="body2"
                                  sx={{
                                    mt: 0.15,
                                    color: 'var(--atlas-ink-muted)',
                                    whiteSpace: 'pre-line',
                                  }}
                                >
                                  {mealContextText(meal.notes)}
                                </Typography>
                              </Box>
                            )}
                          </Box>

                          <Box sx={{ minWidth: 0 }}>
                            <Stack
                              direction="row"
                              justifyContent="space-between"
                              alignItems="baseline"
                            >
                              <Typography
                                variant="overline"
                                sx={{
                                  color: 'var(--atlas-ink-muted)',
                                  fontWeight: 800,
                                  lineHeight: 1,
                                }}
                              >
                                Macro balance
                              </Typography>
                              <Typography
                                variant="caption"
                                sx={{ color: 'var(--atlas-ink-muted)' }}
                              >
                                calorie share
                              </Typography>
                            </Stack>
                            <Stack
                              direction="row"
                              alignItems="center"
                              spacing={{ xs: 1.5, sm: 2 }}
                              sx={{ mt: 1 }}
                            >
                              <Box
                                role="img"
                                aria-label={
                                  macroSegments.length
                                    ? `${meal.name} macro balance: ${macroSegments
                                        .map(
                                          (segment) =>
                                            `${segment.label} ${Math.round(segment.percentage)} percent`,
                                        )
                                        .join(', ')}`
                                    : `${meal.name} macro balance unavailable`
                                }
                                sx={{
                                  position: 'relative',
                                  display: 'grid',
                                  placeItems: 'center',
                                  flexShrink: 0,
                                  width: { xs: 120, sm: 140 },
                                  aspectRatio: '1 / 1',
                                  borderRadius: '50%',
                                  background: macroDonutBackground(macroSegments),
                                  '&::after': {
                                    content: '""',
                                    position: 'absolute',
                                    width: '58%',
                                    aspectRatio: '1 / 1',
                                    borderRadius: '50%',
                                    bgcolor: 'var(--atlas-paper)',
                                  },
                                }}
                              >
                                <Box sx={{ position: 'relative', zIndex: 1, textAlign: 'center' }}>
                                  <Typography
                                    className="numeric-data"
                                    sx={{ fontWeight: 800, lineHeight: 1.05 }}
                                  >
                                    {formatWholeAmount(calories)}
                                  </Typography>
                                  <Typography
                                    variant="caption"
                                    sx={{ color: 'var(--atlas-ink-muted)' }}
                                  >
                                    kcal
                                  </Typography>
                                </Box>
                              </Box>
                              <Stack spacing={0.65} sx={{ minWidth: 0, flex: 1 }}>
                                {macroSegments.map((segment) => (
                                  <Stack
                                    key={segment.key}
                                    direction="row"
                                    justifyContent="space-between"
                                    alignItems="baseline"
                                    spacing={1}
                                  >
                                    <Stack direction="row" alignItems="center" spacing={0.6}>
                                      <Box
                                        sx={{
                                          width: 8,
                                          height: 8,
                                          flexShrink: 0,
                                          bgcolor: segment.color,
                                          borderRadius: '50%',
                                        }}
                                      />
                                      <Typography
                                        variant="caption"
                                        sx={{ fontWeight: 800, textTransform: 'capitalize' }}
                                      >
                                        {segment.label}
                                      </Typography>
                                    </Stack>
                                    <Typography
                                      variant="caption"
                                      className="numeric-data"
                                      sx={{ fontWeight: 750, whiteSpace: 'nowrap' }}
                                    >
                                      {mealNutrientText(meal, segment.key)} g (
                                      {Math.round(segment.percentage)}%)
                                    </Typography>
                                  </Stack>
                                ))}
                              </Stack>
                            </Stack>
                            <Box
                              sx={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                                gap: 0.75,
                                mt: 1.25,
                              }}
                            >
                              {[
                                ['fiber', 'Fiber', 'g', 'var(--fiber-color)'],
                                ['sugar', 'Sugar', 'g', 'var(--sugar-color)'],
                                ['sodium', 'Sodium', 'mg', 'var(--sodium-color)'],
                                ['cholesterol', 'Cholesterol', 'mg', 'var(--cholesterol-color)'],
                              ].map(([key, label, unit, color]) => (
                                <Box
                                  key={key}
                                  sx={{
                                    px: 1,
                                    py: 0.75,
                                    bgcolor: 'var(--atlas-paper)',
                                    border: '1px solid var(--atlas-border-strong)',
                                    borderTop: `2px solid ${color}`,
                                    borderRadius: 1.25,
                                  }}
                                >
                                  <Typography variant="caption" sx={{ color, fontWeight: 800 }}>
                                    {label}
                                  </Typography>
                                  <Typography className="numeric-data" sx={{ fontWeight: 800 }}>
                                    {mealNutrientText(meal, key)} {unit}
                                  </Typography>
                                </Box>
                              ))}
                            </Box>
                          </Box>
                        </Box>
                      </Paper>
                    );
                  })}
                </Stack>
              </>
            )}
          </Box>
        </Stack>

        <MealEditor
          date={date}
          meal={editor.meal}
          open={editor.open}
          token={token}
          onClose={() => setEditor({ open: false, meal: null })}
          onSaved={async (message) => {
            setEditor({ open: false, meal: null });
            showSnackbar('success', message);
            await loadDiary();
          }}
        />

        <MealEstimateDialog
          date={date}
          open={estimateOpen}
          token={token}
          onClose={() => setEstimateOpen(false)}
          onSaved={async (message) => {
            setEstimateOpen(false);
            showSnackbar('success', message);
            await loadDiary();
          }}
        />

        <Dialog
          open={Boolean(pendingDelete)}
          onClose={() => setPendingDelete(null)}
          aria-describedby="delete-meal-description"
          sx={{
            '& .MuiDialog-paper': {
              bgcolor: 'var(--atlas-paper)',
              border: '1px solid var(--atlas-border-strong)',
            },
          }}
        >
          <DialogTitle>Delete {pendingDelete?.name}?</DialogTitle>
          <DialogContent>
            <Typography id="delete-meal-description">
              This removes the meal from {dateParts.weekday}, {dateParts.date}. This cannot be
              undone.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setPendingDelete(null)}>Cancel</Button>
            <Button color="error" variant="contained" onClick={removeMeal}>
              Delete meal
            </Button>
          </DialogActions>
        </Dialog>
      </Container>
    </Box>
  );
}
