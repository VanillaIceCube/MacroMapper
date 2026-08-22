import AddIcon from '@mui/icons-material/Add';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import RestaurantMenuOutlinedIcon from '@mui/icons-material/RestaurantMenuOutlined';
import SearchIcon from '@mui/icons-material/Search';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useCallback, useEffect, useMemo, useState } from 'react';
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
    color: 'var(--atlas-ink)',
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
    color: 'var(--atlas-ink-muted)',
    background: 'var(--atlas-paper)',
  },
  {
    key: 'sugar',
    label: 'Sugar',
    unit: 'g',
    color: 'var(--atlas-ink-muted)',
    background: 'var(--atlas-paper)',
  },
  {
    key: 'sodium',
    label: 'Sodium',
    unit: 'mg',
    color: 'var(--atlas-ink-muted)',
    background: 'var(--atlas-paper)',
  },
  {
    key: 'cholesterol',
    label: 'Cholesterol',
    unit: 'mg',
    color: 'var(--atlas-ink-muted)',
    background: 'var(--atlas-paper)',
  },
];

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
  const numeric = Number(amount);
  return Number.isFinite(numeric)
    ? numeric.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : '—';
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
        {meal ? 'Edit meal' : 'Add meal'}
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

  return (
    <Box className="atlas-contours" sx={{ minHeight: 'calc(100vh - 65px)' }}>
      <Container maxWidth="lg" sx={{ py: { xs: 3, sm: 5 } }}>
        <Stack spacing={3}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            alignItems={{ sm: 'center' }}
            justifyContent="space-between"
            spacing={2}
          >
            <Box>
              <Typography
                variant="overline"
                sx={{ color: 'var(--atlas-forest-dark)', fontWeight: 700, letterSpacing: '0.12em' }}
              >
                Daily map
              </Typography>
              <Typography
                component="h1"
                variant="h3"
                sx={{ fontSize: { xs: '2.35rem', sm: '3.5rem' }, lineHeight: 1.05 }}
              >
                Meal diary
              </Typography>
              <Typography sx={{ mt: 1, color: 'var(--atlas-ink-muted)' }}>
                Your saved meals keep their original nutrition values.
              </Typography>
            </Box>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
              <Button
                variant="outlined"
                color="secondary"
                startIcon={<AutoAwesomeIcon />}
                onClick={() => setEstimateOpen(true)}
              >
                Estimate meal
              </Button>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => setEditor({ open: true, meal: null })}
              >
                Add manually
              </Button>
            </Stack>
          </Stack>

          <Paper
            elevation={0}
            sx={{
              p: 1.5,
              bgcolor: 'var(--atlas-mineral-soft)',
              color: 'var(--atlas-ink)',
              border: '1px solid rgba(71, 121, 138, 0.24)',
            }}
          >
            <Stack direction="row" alignItems="center" justifyContent="center" spacing={1.25}>
              <IconButton
                aria-label="previous day"
                onClick={() => setDate((current) => shiftDate(current, -1))}
              >
                <ChevronLeftIcon />
              </IconButton>
              <TextField
                aria-label="diary date"
                type="date"
                value={date}
                onChange={(event) => setDate(event.target.value)}
                size="small"
              />
              <IconButton
                aria-label="next day"
                onClick={() => setDate((current) => shiftDate(current, 1))}
              >
                <ChevronRightIcon />
              </IconButton>
            </Stack>
          </Paper>

          {error && <Alert severity="error">{error}</Alert>}

          <Box>
            <Typography component="h2" variant="h5" sx={{ mb: 1.5 }}>
              Daily totals
            </Typography>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(4, 1fr)' },
                gap: 1.5,
              }}
            >
              {launchNutrients.map((nutrient) => (
                <Paper
                  key={nutrient.key}
                  elevation={0}
                  sx={{
                    p: 2,
                    bgcolor: nutrient.background,
                    color: 'var(--atlas-ink)',
                    border: '1px solid var(--atlas-border)',
                    borderTop: `4px solid ${nutrient.color}`,
                  }}
                >
                  <Typography variant="body2" sx={{ color: nutrient.color, fontWeight: 700 }}>
                    {nutrient.label}
                  </Typography>
                  <Typography
                    variant="h5"
                    className="numeric-data"
                    sx={{ mt: 0.5, fontWeight: 650 }}
                  >
                    {totalsByKey[nutrient.key]
                      ? formatAmount(totalsByKey[nutrient.key].amount)
                      : '—'}{' '}
                    <Typography component="span" variant="caption">
                      {nutrient.unit}
                    </Typography>
                  </Typography>
                </Paper>
              ))}
            </Box>
          </Box>

          <Box>
            <Typography component="h2" variant="h5" sx={{ mb: 1.5 }}>
              Meals
            </Typography>
            {loading ? (
              <CircularProgress aria-label="loading diary" />
            ) : !data.meals.length ? (
              <Paper
                sx={{
                  p: 4,
                  textAlign: 'center',
                  bgcolor: 'var(--atlas-paper)',
                  color: 'var(--atlas-ink)',
                  border: '1px dashed var(--atlas-border-strong)',
                }}
              >
                <RestaurantMenuOutlinedIcon
                  sx={{ fontSize: 38, color: 'var(--atlas-forest)', mb: 1 }}
                />
                <Typography variant="h6">Nothing logged yet</Typography>
                <Typography sx={{ mt: 0.5, color: 'var(--atlas-ink-muted)' }}>
                  Add a meal to start this day’s diary.
                </Typography>
              </Paper>
            ) : (
              <Stack spacing={2}>
                {data.meals.map((meal) => (
                  <Paper
                    key={meal.id}
                    elevation={0}
                    sx={{
                      p: { xs: 2, sm: 2.5 },
                      bgcolor: 'var(--atlas-paper)',
                      color: 'var(--atlas-ink)',
                      border: '1px solid var(--atlas-border)',
                      borderLeft: '5px solid var(--atlas-forest)',
                      boxShadow: '0 12px 30px rgba(23, 50, 77, 0.05)',
                    }}
                  >
                    <Stack
                      direction="row"
                      justifyContent="space-between"
                      alignItems="flex-start"
                      spacing={1}
                    >
                      <Box>
                        <Typography component="h3" variant="h6">
                          {meal.name}
                        </Typography>
                        {meal.notes && (
                          <Typography variant="body2" sx={{ color: 'var(--atlas-ink-muted)' }}>
                            {meal.notes}
                          </Typography>
                        )}
                      </Box>
                      <Stack direction="row">
                        <IconButton
                          aria-label={`edit ${meal.name}`}
                          onClick={() => setEditor({ open: true, meal })}
                          sx={{ color: 'var(--atlas-forest)' }}
                        >
                          <EditOutlinedIcon />
                        </IconButton>
                        <IconButton
                          aria-label={`delete ${meal.name}`}
                          onClick={() => setPendingDelete(meal)}
                          sx={{ color: 'var(--atlas-persimmon-dark)' }}
                        >
                          <DeleteOutlineIcon />
                        </IconButton>
                      </Stack>
                    </Stack>
                    <Divider sx={{ my: 1.5 }} />
                    <List disablePadding>
                      {meal.items.map((item) => (
                        <ListItem key={item.id} disableGutters alignItems="flex-start">
                          <ListItemText
                            primary={`${formatAmount(item.servings)} × ${item.food_name}`}
                            secondaryTypographyProps={{ component: 'div' }}
                            secondary={
                              <>
                                {item.provider_name ||
                                  item.serving_label ||
                                  `${item.serving_quantity} ${item.serving_unit}`}
                                <MealItemBreakdown components={item.component_snapshot} />
                              </>
                            }
                          />
                          <Typography
                            className="numeric-data"
                            sx={{
                              color: 'var(--atlas-forest-dark)',
                              fontWeight: 700,
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {formatAmount(
                              item.nutrients.find((value) => value.key === 'calories')?.amount,
                            )}{' '}
                            kcal
                          </Typography>
                        </ListItem>
                      ))}
                    </List>
                  </Paper>
                ))}
              </Stack>
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
          sx={{
            '& .MuiDialog-paper': {
              bgcolor: 'var(--atlas-paper)',
              border: '1px solid var(--atlas-border-strong)',
            },
          }}
        >
          <DialogTitle>Delete {pendingDelete?.name}?</DialogTitle>
          <DialogContent>
            <Typography>This removes the meal from your diary and cannot be undone.</Typography>
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
