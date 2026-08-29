import AddIcon from '@mui/icons-material/Add';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import RefreshIcon from '@mui/icons-material/Refresh';
import RestaurantMenuOutlinedIcon from '@mui/icons-material/RestaurantMenuOutlined';
import SearchIcon from '@mui/icons-material/Search';
import SendIcon from '@mui/icons-material/Send';
import TodayOutlinedIcon from '@mui/icons-material/TodayOutlined';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Link,
  List,
  Menu,
  MenuItem,
  Paper,
  Skeleton,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  acceptMealProposal,
  createMeal,
  createPersonalFood,
  deleteMeal,
  fetchDailyDiary,
  followUpMealProposal,
  searchFoods,
  updateMealProposal,
  updateMeal,
} from '../services/mealApiClient';
import MealEstimateDialog from '../components/MealEstimateDialog';
import MealItemEditorRow from '../components/MealItemEditorRow';
import {
  catalogFoodToManualMealItem,
  manualMealItemToProposalItem,
  proposalItemToManualMealItem,
  savedMealItemToEditableMealItem,
} from '../components/mealItemAdapters';
import {
  changeMealItemNutrient,
  changeMealItemPortion,
  changeMealItemServings,
  removeMealItemFromTree,
} from '../components/mealItemTree';
import CalorieContributionChart from '../components/nutrition/CalorieContributionChart';
import MacroCalorieBar from '../components/nutrition/MacroCalorieBar';
import MacroCalorieSplit from '../components/nutrition/MacroCalorieSplit';
import MealNutritionSummary from '../components/nutrition/MealNutritionSummary';
import { ItemNutritionCards, NutritionCards } from '../components/nutrition/NutritionCards';
import {
  MACRO_CALORIE_FIELDS as macroCalorieFields,
  NUTRIENT_FIELDS as launchNutrients,
} from '../components/nutrition/nutritionDefinitions';
import {
  formatNutritionAmount as formatAmount,
  formatWholeNutritionAmount as formatWholeAmount,
  nutrientArrayToValues as nutrientValues,
} from '../components/nutrition/nutritionMath';

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

const manualDraftFingerprint = ({ name, notes, entryDate, items, newFood = {} }) =>
  JSON.stringify({
    name,
    notes,
    entryDate,
    items: items.map(({ food_item, food_version, servings }) => ({
      food_item,
      food_version,
      servings,
    })),
    newFood,
  });

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

function MealEditor({ date, meal, open, token, initialProposal, onClose, onSaved }) {
  const [name, setName] = useState('');
  const [notes, setNotes] = useState('');
  const [entryDate, setEntryDate] = useState(date);
  const [items, setItems] = useState([]);
  const [proposalId, setProposalId] = useState(null);
  const [proposalContext, setProposalContext] = useState(null);
  const [catalogPickerOpen, setCatalogPickerOpen] = useState(true);
  const [followUp, setFollowUp] = useState('');
  const [followUpBusy, setFollowUpBusy] = useState(false);
  const [followUpFeedback, setFollowUpFeedback] = useState(null);
  const [query, setQuery] = useState('');
  const [foods, setFoods] = useState([]);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [creatingFood, setCreatingFood] = useState(false);
  const [error, setError] = useState('');
  const [newFood, setNewFood] = useState(emptyPersonalFood);
  const [discardOpen, setDiscardOpen] = useState(false);
  const [catalogActionsAnchorEl, setCatalogActionsAnchorEl] = useState(null);
  const [catalogActionsFoodId, setCatalogActionsFoodId] = useState(null);
  const [catalogDetailFoodIds, setCatalogDetailFoodIds] = useState(() => new Set());
  const baselineRef = useRef('');
  const catalogSearchRef = useRef(null);
  const selectedFoodIds = useMemo(
    () => new Set(items.map((item) => String(item.food_item))),
    [items],
  );
  const availableFoods = useMemo(
    () => foods.filter((food) => !selectedFoodIds.has(String(food.id))),
    [foods, selectedFoodIds],
  );
  const activeCatalogFood = availableFoods.find((food) => food.id === catalogActionsFoodId);

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
    const initialName = meal?.name ?? initialProposal?.name ?? '';
    const initialNotes = meal?.notes ?? initialProposal?.notes ?? '';
    const initialDate = meal?.entry_date ?? initialProposal?.entry_date ?? date;
    const initialItems = meal
      ? meal.items.map(savedMealItemToEditableMealItem)
      : (initialProposal?.items?.map(proposalItemToManualMealItem) ?? []);
    setName(initialName);
    setNotes(initialNotes);
    setEntryDate(initialDate);
    setItems(initialItems);
    setProposalId(initialProposal?.id ?? null);
    setProposalContext(
      initialProposal
        ? {
            provider_name: initialProposal.provider_name,
            provider_model: initialProposal.provider_model,
            confidence_score: initialProposal.confidence_score,
          }
        : null,
    );
    setCatalogPickerOpen(!initialProposal);
    setFollowUp('');
    setFollowUpBusy(false);
    setFollowUpFeedback(null);
    const initialNewFood = emptyPersonalFood();
    baselineRef.current = manualDraftFingerprint({
      name: initialName,
      notes: initialNotes,
      entryDate: initialDate,
      items: initialItems,
      newFood: initialNewFood,
    });
    setQuery('');
    setError('');
    setDiscardOpen(false);
    setCatalogActionsAnchorEl(null);
    setCatalogActionsFoodId(null);
    setCatalogDetailFoodIds(new Set());
    setNewFood(initialNewFood);
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
    window.requestAnimationFrame(() => {
      if (!meal && !initialProposal) catalogSearchRef.current?.focus();
    });
    return () => {
      active = false;
    };
  }, [date, initialProposal, meal, open, token]);

  const addFood = (food) => {
    setItems((current) => {
      if (current.some((item) => String(item.food_item) === String(food.id))) return current;
      return [...current, catalogFoodToManualMealItem(food)];
    });
  };

  const closeCatalogActions = () => {
    setCatalogActionsAnchorEl(null);
    setCatalogActionsFoodId(null);
  };

  const toggleCatalogDetails = (foodId) => {
    setCatalogDetailFoodIds((current) => {
      const next = new Set(current);
      if (next.has(foodId)) next.delete(foodId);
      else next.add(foodId);
      return next;
    });
  };

  const changeServings = (key, amount, item) => {
    setItems((current) => changeMealItemServings(current, key, amount, item));
  };

  const changePortion = (key, selectedPortionKey) => {
    setItems((current) => changeMealItemPortion(current, key, selectedPortionKey));
  };

  const changeNutrient = (key, nutrient, totalValue) => {
    setItems((current) => changeMealItemNutrient(current, key, nutrient, totalValue));
  };

  const removeItem = (key) => {
    setItems((current) => removeMealItemFromTree(current, key));
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
    if (!proposalId || !name.trim() || !items.length) {
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
        proposalId,
        {
          follow_up: request,
          name: name.trim(),
          items: items.map(manualMealItemToProposalItem),
        },
        token,
      );
      if (response.ok) {
        const result = await response.json();
        if (result.applied) {
          const updatedProposal = result.proposal;
          setName(updatedProposal.name);
          setItems(updatedProposal.items.map(proposalItemToManualMealItem));
          setProposalContext({
            provider_name: updatedProposal.provider_name,
            provider_model: updatedProposal.provider_model,
            confidence_score: updatedProposal.confidence_score,
          });
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

  const currentFingerprint = manualDraftFingerprint({
    name,
    notes,
    entryDate,
    items,
    newFood,
  });
  const hasUnsavedChanges = Boolean(
    baselineRef.current && currentFingerprint !== baselineRef.current,
  );
  const requestClose = () => {
    if (hasUnsavedChanges) {
      setDiscardOpen(true);
    } else {
      onClose();
    }
  };

  const save = async () => {
    if (!name.trim() || !entryDate || !items.length) {
      setError('Name the meal and add at least one food.');
      return;
    }
    if (
      items.some((item) => !Number.isFinite(Number(item.servings)) || Number(item.servings) <= 0)
    ) {
      setError('Each meal item needs a quantity greater than zero.');
      return;
    }
    setSaving(true);
    setError('');
    if (proposalId && !meal) {
      const updateResponse = await updateMealProposal(
        proposalId,
        {
          name: name.trim(),
          notes: notes.trim(),
          items: items.map(manualMealItemToProposalItem),
        },
        token,
      );
      if (!updateResponse.ok) {
        setError(await responseError(updateResponse, 'Could not save your meal draft.'));
        setSaving(false);
        return;
      }
      const acceptResponse = await acceptMealProposal(proposalId, token);
      if (acceptResponse.ok) {
        onSaved('Meal added.');
      } else {
        setError(await responseError(acceptResponse, 'Could not add this meal to your diary.'));
      }
      setSaving(false);
      return;
    }
    const payload = {
      entry_date: entryDate,
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
    setCreatingFood(true);
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
    setCreatingFood(false);
  };

  return (
    <>
      <Dialog
        open={open}
        onClose={saving || creatingFood || followUpBusy ? undefined : requestClose}
        fullWidth
        maxWidth="md"
        aria-labelledby="manual-meal-editor-title"
        sx={{
          '& .MuiDialog-paper': {
            m: { xs: 0, sm: 2 },
            width: { xs: '100%', sm: 'calc(100% - 32px)' },
            height: { xs: '100%', sm: 'auto' },
            maxHeight: { xs: '100%', sm: 'calc(100% - 32px)' },
            borderRadius: { xs: 0, sm: 3 },
            bgcolor: 'var(--atlas-paper)',
            border: '1px solid var(--atlas-border-strong)',
            boxShadow: '0 24px 64px rgba(23, 50, 77, 0.16)',
          },
        }}
      >
        <DialogTitle
          id="manual-meal-editor-title"
          sx={{
            bgcolor: proposalId ? 'var(--atlas-persimmon-soft)' : 'var(--atlas-mineral-soft)',
            color: 'var(--atlas-ink)',
            borderBottom: '1px solid var(--atlas-border)',
            py: { xs: 1.5, sm: 2 },
          }}
        >
          <Stack direction="row" spacing={1} alignItems="center">
            {proposalId && <AutoAwesomeIcon sx={{ color: 'var(--atlas-persimmon-dark)' }} />}
            <Typography component="span" variant="h5">
              {proposalId ? 'Review meal estimate' : meal ? 'Edit meal' : 'Add meal'}
            </Typography>
          </Stack>
        </DialogTitle>
        <DialogContent
          dividers
          sx={{ bgcolor: 'var(--atlas-paper)', borderColor: 'transparent', px: { xs: 1.5, sm: 3 } }}
        >
          <Stack spacing={proposalId ? 1.25 : 2.25}>
            {error && <Alert severity="error">{error}</Alert>}
            <Alert severity="info" variant="outlined">
              {proposalContext
                ? 'Review the estimate, add catalog or personal foods if needed, then save the meal.'
                : 'Add catalog or personal foods, then review everything together before saving.'}
            </Alert>
            {proposalContext && (
              <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap">
                <Chip size="small" label="AI estimate" color="secondary" variant="outlined" />
                {proposalContext.provider_name && (
                  <Chip size="small" label={proposalContext.provider_name} variant="outlined" />
                )}
                {proposalContext.confidence_score != null && (
                  <Chip
                    size="small"
                    label={`${Math.round(Number(proposalContext.confidence_score) * 100)}% confidence`}
                    variant="outlined"
                  />
                )}
              </Stack>
            )}

            <Paper
              component="section"
              aria-labelledby="manual-meal-identity-heading"
              elevation={0}
              sx={{
                order: 1,
                p: { xs: 1.5, sm: 2 },
                border: '1px solid var(--atlas-border)',
              }}
            >
              <Typography id="manual-meal-identity-heading" component="h3" variant="h6">
                Meal details
              </Typography>
              <Stack spacing={1.5} sx={{ mt: 1.5 }}>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                  <TextField
                    label="Meal name"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    required
                    fullWidth
                  />
                  <TextField
                    label="Date"
                    type="date"
                    value={entryDate}
                    onChange={(event) => setEntryDate(event.target.value)}
                    InputLabelProps={{ shrink: true }}
                    required
                    sx={{ minWidth: { sm: 180 } }}
                  />
                </Stack>
                <TextField
                  label="Notes (optional)"
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  multiline
                  minRows={2}
                  helperText="Add preparation details or context you want saved with this meal."
                />
              </Stack>
            </Paper>

            <Paper
              component="section"
              aria-labelledby="food-search-heading"
              elevation={0}
              sx={{
                order: proposalId ? 4 : 2,
                p: { xs: 1.5, sm: 2 },
                bgcolor: 'var(--atlas-mineral-soft)',
                border: '1px solid rgba(71, 121, 138, 0.32)',
              }}
            >
              <Stack direction="row" justifyContent="space-between" alignItems="center" gap={1}>
                <Box>
                  <Typography id="food-search-heading" component="h3" variant="h6">
                    {proposalId ? 'Add another food' : 'Find and add foods'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Search the shared catalog and your personal foods.
                  </Typography>
                </Box>
                <Stack direction="row" spacing={0.5} alignItems="center">
                  {catalogPickerOpen && (
                    <Chip
                      label={`${availableFoods.length} results`}
                      size="small"
                      variant="outlined"
                    />
                  )}
                  <IconButton
                    size="small"
                    aria-label={`${catalogPickerOpen ? 'Collapse' : 'Expand'} add another food`}
                    aria-expanded={catalogPickerOpen}
                    onClick={() => setCatalogPickerOpen((current) => !current)}
                  >
                    {catalogPickerOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                  </IconButton>
                </Stack>
              </Stack>
              <Collapse in={catalogPickerOpen} unmountOnExit>
                <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
                  <TextField
                    inputRef={catalogSearchRef}
                    label="Search catalog"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault();
                        runSearch();
                      }
                    }}
                    fullWidth
                  />
                  <Button
                    variant="outlined"
                    onClick={runSearch}
                    disabled={searching}
                    startIcon={searching ? <CircularProgress size={18} /> : <SearchIcon />}
                    aria-label="search foods"
                    sx={{ minWidth: { xs: 52, sm: 116 }, px: { xs: 1.5, sm: 2.5 } }}
                  >
                    <Box component="span" sx={{ display: { xs: 'none', sm: 'inline' } }}>
                      Search
                    </Box>
                  </Button>
                </Stack>
                {searching ? (
                  <Stack spacing={1} sx={{ mt: 1.5 }} aria-label="Loading food results">
                    {[0, 1].map((value) => (
                      <Skeleton key={value} variant="rounded" height={92} />
                    ))}
                  </Stack>
                ) : availableFoods.length ? (
                  <>
                    <List
                      disablePadding
                      aria-label="Food search results"
                      sx={{ maxHeight: 360, mt: 1.5, overflow: 'auto' }}
                    >
                      {availableFoods.map((food) => {
                        const version = food.current_version || {};
                        const source =
                          provenanceLabels[version.provenance] ||
                          (food.scope === 'personal' ? 'Personal' : 'Catalog');
                        return (
                          <Paper
                            component="li"
                            key={food.id}
                            elevation={0}
                            sx={{
                              listStyle: 'none',
                              mb: 1,
                              p: 1.25,
                              bgcolor: 'var(--atlas-paper)',
                              border: '1px solid var(--atlas-border)',
                              borderLeft: `4px solid ${food.scope === 'personal' ? 'var(--atlas-persimmon)' : 'var(--atlas-forest)'}`,
                            }}
                          >
                            <Stack
                              direction={{ xs: 'column', sm: 'row' }}
                              justifyContent="space-between"
                              gap={1}
                            >
                              <Box sx={{ minWidth: 0 }}>
                                <Stack
                                  direction="row"
                                  spacing={0.75}
                                  useFlexGap
                                  flexWrap="wrap"
                                  sx={{ mb: 0.5 }}
                                >
                                  <Chip size="small" label={source} variant="outlined" />
                                  {version.confidence_score != null && (
                                    <Chip
                                      size="small"
                                      label={`${Math.round(Number(version.confidence_score) * 100)}% confidence`}
                                      variant="outlined"
                                    />
                                  )}
                                  {food.provider_name && (
                                    <Chip
                                      size="small"
                                      label={food.provider_name}
                                      variant="outlined"
                                    />
                                  )}
                                </Stack>
                                <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
                                  {food.name}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {version.serving_label ||
                                    `${formatAmount(version.serving_quantity)} ${version.serving_unit || 'serving'}`}
                                </Typography>
                              </Box>
                              <Stack direction="row" spacing={1} alignItems="center">
                                <Button onClick={() => addFood(food)} startIcon={<AddIcon />}>
                                  Add
                                </Button>
                                <IconButton
                                  size="small"
                                  aria-label={`More actions for ${food.name}`}
                                  aria-haspopup="menu"
                                  aria-expanded={
                                    catalogActionsFoodId === food.id &&
                                    Boolean(catalogActionsAnchorEl)
                                  }
                                  onClick={(event) => {
                                    setCatalogActionsAnchorEl(event.currentTarget);
                                    setCatalogActionsFoodId(food.id);
                                  }}
                                >
                                  <MoreVertIcon fontSize="small" />
                                </IconButton>
                              </Stack>
                            </Stack>
                            <Collapse in={catalogDetailFoodIds.has(food.id)} unmountOnExit>
                              <Paper
                                elevation={0}
                                sx={{ mt: 0.75, p: 0.75, border: '1px solid var(--atlas-border)' }}
                              >
                                <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap">
                                  <Chip size="small" label={source} variant="outlined" />
                                  {version.confidence_score != null && (
                                    <Chip
                                      size="small"
                                      label={`${Math.round(Number(version.confidence_score) * 100)}% confidence`}
                                      variant="outlined"
                                    />
                                  )}
                                  {food.provider_name && (
                                    <Chip
                                      size="small"
                                      label={food.provider_name}
                                      variant="outlined"
                                    />
                                  )}
                                </Stack>
                                {!!version.sources?.length ? (
                                  <Stack component="ul" spacing={0.25} sx={{ mb: 0, pl: 2.25 }}>
                                    {version.sources.map((estimateSource) => (
                                      <Typography
                                        component="li"
                                        variant="caption"
                                        key={estimateSource.url || estimateSource.title}
                                      >
                                        {estimateSource.url ? (
                                          <Link
                                            href={estimateSource.url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                          >
                                            {estimateSource.title || estimateSource.url}
                                          </Link>
                                        ) : (
                                          estimateSource.title
                                        )}
                                      </Typography>
                                    ))}
                                  </Stack>
                                ) : (
                                  <Typography variant="caption" color="text.secondary">
                                    No source links were provided for this estimate.
                                  </Typography>
                                )}
                              </Paper>
                            </Collapse>
                            <Box sx={{ mt: 1 }}>
                              <NutritionCards
                                values={nutrientValues(version.nutrients)}
                                ariaLabel={`${food.name} catalog nutrition`}
                                compact
                              />
                            </Box>
                          </Paper>
                        );
                      })}
                    </List>
                    <Menu
                      anchorEl={catalogActionsAnchorEl}
                      open={Boolean(catalogActionsAnchorEl && activeCatalogFood)}
                      onClose={closeCatalogActions}
                      MenuListProps={{
                        'aria-label': `Actions for ${activeCatalogFood?.name || 'catalog food'}`,
                      }}
                    >
                      <MenuItem
                        aria-label={`${catalogDetailFoodIds.has(catalogActionsFoodId) ? 'Hide' : 'Show'} estimate details for ${activeCatalogFood?.name || 'catalog food'}`}
                        onClick={() => {
                          toggleCatalogDetails(catalogActionsFoodId);
                          closeCatalogActions();
                        }}
                      >
                        <InfoOutlinedIcon fontSize="small" sx={{ mr: 1.25 }} />
                        {catalogDetailFoodIds.has(catalogActionsFoodId)
                          ? 'Hide details'
                          : 'Estimate details'}
                      </MenuItem>
                    </Menu>
                  </>
                ) : (
                  <Typography sx={{ mt: 1.5 }} color="text.secondary">
                    {foods.length
                      ? 'All matching foods are already in this meal.'
                      : 'No foods matched this search. Try another term or create a personal food below.'}
                  </Typography>
                )}
              </Collapse>
            </Paper>

            <Paper
              component="section"
              aria-labelledby="selected-foods-heading"
              elevation={0}
              sx={{
                order: 3,
                p: { xs: 1.5, sm: 2 },
                border: '1px solid var(--atlas-border-strong)',
              }}
            >
              <Stack direction="row" justifyContent="space-between" alignItems="center" gap={1}>
                <Box>
                  <Typography id="selected-foods-heading" component="h3" variant="h6">
                    Review meal items
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Adjust count, unit, nutrition, components, and estimate details using the same
                    controls as AI estimates.
                  </Typography>
                </Box>
                <Chip
                  size="small"
                  label={`${items.length} ${items.length === 1 ? 'item' : 'items'}`}
                  color={items.length ? 'success' : 'default'}
                  variant="outlined"
                />
              </Stack>
              {!items.length ? (
                <Box
                  sx={{
                    mt: 1.5,
                    p: 2.5,
                    textAlign: 'center',
                    bgcolor: 'var(--atlas-bone)',
                    border: '1px dashed var(--atlas-border-strong)',
                    borderRadius: 2,
                  }}
                >
                  <RestaurantMenuOutlinedIcon sx={{ color: 'var(--atlas-mineral-dark)' }} />
                  <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
                    No foods added yet
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Add a catalog or personal food to build the nutrition review.
                  </Typography>
                </Box>
              ) : (
                <Stack spacing={1.5} sx={{ mt: 1.5 }} aria-label="Selected meal items">
                  {items.map((item) => (
                    <MealItemEditorRow
                      key={item.key}
                      item={item}
                      onServings={changeServings}
                      onPortionChange={changePortion}
                      onNutrientChange={changeNutrient}
                      onRemove={removeItem}
                      renderNutrition={(foodItem, onChange) => (
                        <ItemNutritionCards item={foodItem} compact onNutrientChange={onChange} />
                      )}
                    />
                  ))}
                </Stack>
              )}
            </Paper>

            {!!items.length && (
              <Box sx={{ order: proposalId ? 2 : 4 }}>
                <MealNutritionSummary items={items} />
              </Box>
            )}

            {!proposalId && (
              <Box
                component="details"
                sx={{
                  order: 5,
                  p: { xs: 1.5, sm: 2 },
                  bgcolor: 'var(--atlas-persimmon-soft)',
                  border: '1px solid rgba(169, 68, 32, 0.28)',
                  borderRadius: 2,
                }}
              >
                <Typography
                  component="summary"
                  variant="h6"
                  sx={{
                    color: 'var(--atlas-persimmon-dark)',
                    cursor: 'pointer',
                    minHeight: 44,
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  Create a personal food
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  Use this when the catalog does not contain the food you need. Enter values for one
                  serving; unknown nutrients can stay blank.
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
                      gap: 1.25,
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
                  <Button
                    variant="outlined"
                    color="secondary"
                    onClick={createFood}
                    disabled={saving || creatingFood}
                    startIcon={creatingFood ? <CircularProgress size={18} /> : <AddIcon />}
                  >
                    {creatingFood ? 'Creating…' : 'Create and add food'}
                  </Button>
                </Stack>
              </Box>
            )}

            {proposalId && !meal && (
              <Paper
                component="section"
                aria-labelledby="adjust-meal-with-ai-heading"
                elevation={0}
                sx={{ order: 6, p: 1.25, border: '1px solid var(--atlas-border)' }}
              >
                <Stack spacing={0.75}>
                  <Stack direction="row" spacing={0.75} alignItems="center">
                    <AutoAwesomeIcon
                      fontSize="small"
                      sx={{ color: 'var(--atlas-persimmon-dark)' }}
                    />
                    <Typography
                      id="adjust-meal-with-ai-heading"
                      variant="subtitle2"
                      sx={{ fontWeight: 800 }}
                    >
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
            )}
          </Stack>
        </DialogContent>
        <DialogActions
          sx={{
            bgcolor: 'var(--atlas-paper)',
            borderTop: '1px solid var(--atlas-border)',
            px: { xs: 1.5, sm: 3 },
            py: 1.25,
          }}
        >
          <Button onClick={requestClose} disabled={saving || creatingFood || followUpBusy}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={save}
            disabled={saving || creatingFood || followUpBusy}
          >
            {saving ? 'Saving…' : meal ? 'Save changes' : 'Save meal'}
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={discardOpen}
        onClose={() => setDiscardOpen(false)}
        aria-labelledby="discard-manual-meal-title"
      >
        <DialogTitle id="discard-manual-meal-title">Discard manual meal changes?</DialogTitle>
        <DialogContent>
          <Typography>Your meal draft will be lost if you close the builder.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDiscardOpen(false)}>Keep editing</Button>
          <Button
            color="secondary"
            onClick={() => {
              setDiscardOpen(false);
              onClose();
            }}
          >
            Discard changes
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

export default function DiaryPage({ showSnackbar = () => {} }) {
  const [date, setDate] = useState(localDate);
  const [data, setData] = useState({ meals: [], totals: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [estimateOpen, setEstimateOpen] = useState(false);
  const [editor, setEditor] = useState({ open: false, meal: null, initialProposal: null });
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

  const dailyNutrientValues = useMemo(
    () =>
      Object.fromEntries(launchNutrients.map(({ key }) => [key, totalsByKey[key]?.amount ?? null])),
    [totalsByKey],
  );

  const mealCalorieContributions = useMemo(
    () =>
      data.meals.flatMap((meal) => {
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
      }),
    [data.meals],
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
                  role="group"
                  aria-label={`${nutrient.label} daily total`}
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
              <MacroCalorieSplit
                values={dailyNutrientValues}
                loading={loading}
                variant="dashboard"
              />
              <CalorieContributionChart
                contributions={mealCalorieContributions}
                title="Calories by meal"
                chartAriaLabel="Meal calorie chart"
                emptyText="Add a meal to see its calorie contribution."
                loading={loading}
                variant="dashboard"
                otherKey="other-meals"
                otherLabel={(count) => `Other meals (${count})`}
              />
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
                  onClick={() => setEditor({ open: true, meal: null, initialProposal: null })}
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
                    const mealMacroValues = {
                      calories,
                      ...Object.fromEntries(
                        macroCalorieFields.map(({ key }) => [key, mealNutrientAmount(meal, key)]),
                      ),
                    };
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
                              onClick={() => setEditor({ open: true, meal, initialProposal: null })}
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
                            mt: 2,
                            pt: 2,
                            borderTop: '1px solid var(--atlas-border)',
                          }}
                        >
                          <Box
                            data-testid={`meal-${meal.id}-nutrition-columns`}
                            sx={{
                              display: 'grid',
                              gridTemplateColumns: {
                                xs: '1fr',
                                md: 'minmax(0, 1.35fr) minmax(320px, 0.65fr)',
                              },
                              alignItems: 'start',
                              gap: { xs: 1.5, md: 2.5 },
                            }}
                          >
                            <Box sx={{ minWidth: 0 }}>
                              <Box
                                role="table"
                                aria-label={`${meal.name} food breakdown`}
                                sx={{
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
                                  {['Foods & servings', 'Calories', 'Confidence', 'Provenance'].map(
                                    (label) => (
                                      <Typography
                                        key={label}
                                        role="columnheader"
                                        variant="caption"
                                        sx={{ color: 'var(--atlas-ink-muted)', fontWeight: 800 }}
                                      >
                                        {label}
                                      </Typography>
                                    ),
                                  )}
                                </Box>
                                {meal.items.map((item, itemIndex) => {
                                  const itemCalories = mealItemNutrientAmount(item, 'calories');
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
                                        <Box sx={{ mt: 0.35 }}>
                                          <MacroCalorieBar
                                            name={item.food_name}
                                            values={nutrientValues(item.nutrients)}
                                            widthPercentage={
                                              itemCalories !== null && highestFoodCalories > 0
                                                ? (itemCalories / highestFoodCalories) * 100
                                                : 0
                                            }
                                            height={4}
                                            borderRadius={999}
                                            wholeNumbers
                                          />
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
                              <MacroCalorieSplit
                                values={mealMacroValues}
                                variant="meal-card"
                                chartAriaLabel={`${meal.name} Macro Balance`}
                              />
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
                        </Box>
                      </Paper>
                    );
                  })}
                </Stack>
              </>
            )}
          </Box>
        </Stack>

        <MealEstimateDialog
          date={date}
          open={estimateOpen}
          token={token}
          onClose={() => setEstimateOpen(false)}
          onEstimated={(proposal) => {
            setEstimateOpen(false);
            setEditor({ open: true, meal: null, initialProposal: proposal });
          }}
        />

        <MealEditor
          date={date}
          meal={editor.meal}
          open={editor.open}
          token={token}
          initialProposal={editor.initialProposal}
          onClose={() => setEditor({ open: false, meal: null, initialProposal: null })}
          onSaved={async (message) => {
            setEditor({ open: false, meal: null, initialProposal: null });
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
