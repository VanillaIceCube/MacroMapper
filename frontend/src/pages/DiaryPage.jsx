import AddIcon from '@mui/icons-material/Add';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlineOutlined';
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
import TuneIcon from '@mui/icons-material/Tune';
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
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  acceptMealProposal,
  adjustMeal,
  adjustMealProposal,
  createMeal,
  createMealProposal,
  deleteMeal,
  fetchDailyDiary,
  searchFoods,
  updateMealProposal,
  updateMeal,
} from '../services/mealApiClient';
import MealItemEditorRow from '../components/MealItemEditorRow';
import {
  catalogFoodToMealItem,
  mealItemToProposalItem,
  proposalItemToMealItem,
  savedMealItemToEditableMealItem,
  changeMealItemNutrient,
  changeMealItemPortion,
  changeMealItemServings,
  removeMealItemFromTree,
} from '../domain/mealItem';
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
import { randomMealEstimateExample } from '../mealEstimateExamples';

const provenanceLabels = {
  official: 'Official',
  community_estimate: 'Community Estimate',
  ai_estimate: 'AI Estimate',
  user_modified_estimate: 'User Adjusted',
  user_entered: 'User Entered',
};

const catalogPageSize = 20;
const initialCatalogRequest = {
  query: '',
  scope: 'all',
  originType: 'all',
  sort: 'recommended',
  provider: '',
  provenance: 'all',
};
const catalogScopeOptions = [
  { value: 'all', label: 'All' },
  { value: 'personal', label: 'My Foods' },
  { value: 'shared', label: 'Shared' },
];
const catalogOriginTypeOptions = [
  { value: 'generic', label: 'Common' },
  { value: 'branded', label: 'Branded' },
  { value: 'restaurant', label: 'Restaurant' },
];
const catalogSortOptions = [
  { value: 'recommended', label: 'Recommended' },
  { value: 'recent', label: 'Recently added' },
  { value: 'logged', label: 'Recently logged' },
  { value: 'name', label: 'Alphabetically' },
];
const mealBuilderSurfaceRadius = 1.5;

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

const mealDraftFingerprint = ({ name, notes, entryDate, items }) =>
  JSON.stringify({
    name,
    notes,
    entryDate,
    items,
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

function MapYourMealDialog({ date, meal, open, token, launchMode, onClose, onSaved }) {
  const [estimateDescription, setEstimateDescription] = useState('');
  const [estimatePlaceholder, setEstimatePlaceholder] = useState(randomMealEstimateExample);
  const [estimating, setEstimating] = useState(false);
  const [name, setName] = useState('');
  const [notes, setNotes] = useState('');
  const [entryDate, setEntryDate] = useState(date);
  const [items, setItems] = useState([]);
  const [proposalId, setProposalId] = useState(null);
  const [proposalContext, setProposalContext] = useState(null);
  const [catalogPickerOpen, setCatalogPickerOpen] = useState(true);
  const [adjustment, setAdjustment] = useState('');
  const [adjustmentBusy, setAdjustmentBusy] = useState(false);
  const [adjustmentFeedback, setAdjustmentFeedback] = useState(null);
  const [query, setQuery] = useState('');
  const [catalogScope, setCatalogScope] = useState('all');
  const [catalogOriginType, setCatalogOriginType] = useState('all');
  const [catalogSort, setCatalogSort] = useState('recommended');
  const [catalogFiltersOpen, setCatalogFiltersOpen] = useState(false);
  const [catalogProvider, setCatalogProvider] = useState('');
  const [catalogProvenance, setCatalogProvenance] = useState('all');
  const [appliedCatalogOriginType, setAppliedCatalogOriginType] = useState('all');
  const [appliedCatalogProvider, setAppliedCatalogProvider] = useState('');
  const [appliedCatalogProvenance, setAppliedCatalogProvenance] = useState('all');
  const [catalogFeedback, setCatalogFeedback] = useState('');
  const [catalogError, setCatalogError] = useState('');
  const [catalogRetry, setCatalogRetry] = useState(null);
  const [foods, setFoods] = useState([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [showingRecentFoods, setShowingRecentFoods] = useState(false);
  const [searching, setSearching] = useState(false);
  const [loadingMoreFoods, setLoadingMoreFoods] = useState(false);
  const [catalogHasMore, setCatalogHasMore] = useState(false);
  const [catalogNextOffset, setCatalogNextOffset] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [discardOpen, setDiscardOpen] = useState(false);
  const [catalogActionsAnchorEl, setCatalogActionsAnchorEl] = useState(null);
  const [catalogActionsFoodId, setCatalogActionsFoodId] = useState(null);
  const [catalogDetailFoodIds, setCatalogDetailFoodIds] = useState(() => new Set());
  const [baselineFingerprint, setBaselineFingerprint] = useState('');
  const catalogSearchRef = useRef(null);
  const catalogRequestIdRef = useRef(0);
  const appliedCatalogRequestRef = useRef(initialCatalogRequest);
  const selectedFoodIds = useMemo(
    () => new Set(items.map((item) => String(item.food_item))),
    [items],
  );
  const availableFoods = useMemo(
    () => foods.filter((food) => !selectedFoodIds.has(String(food.id))),
    [foods, selectedFoodIds],
  );
  const activeCatalogFood = availableFoods.find((food) => food.id === catalogActionsFoodId);
  const hasCatalogFilters =
    catalogScope !== 'all' ||
    catalogOriginType !== 'all' ||
    Boolean(catalogProvider.trim()) ||
    catalogProvenance !== 'all';
  const advancedCatalogFilterCount =
    Number(appliedCatalogOriginType !== 'all') +
    Number(Boolean(appliedCatalogProvider.trim())) +
    Number(appliedCatalogProvenance !== 'all');

  const loadRecentFoods = useCallback(
    async ({ append = false, offset = 0 } = {}, appliedRequest = initialCatalogRequest) => {
      const requestId = ++catalogRequestIdRef.current;
      if (append) {
        setLoadingMoreFoods(true);
      } else {
        setSearching(true);
        setLoadingMoreFoods(false);
        appliedCatalogRequestRef.current = appliedRequest;
        setAppliedCatalogOriginType(appliedRequest.originType);
        setAppliedCatalogProvider(appliedRequest.provider);
        setAppliedCatalogProvenance(appliedRequest.provenance);
        setHasSearched(false);
        setShowingRecentFoods(true);
        setFoods([]);
        setCatalogHasMore(false);
        setCatalogNextOffset(0);
      }
      setCatalogError('');
      setCatalogRetry(null);
      try {
        const response = await searchFoods('', token, {
          ordering: '-created_at,-id',
          limit: catalogPageSize + 1,
          offset,
        });
        if (requestId !== catalogRequestIdRef.current) return;
        if (response.ok) {
          const results = await response.json();
          if (requestId !== catalogRequestIdRef.current) return;
          const page = results.slice(0, catalogPageSize);
          setFoods((current) => {
            if (!append) return page;
            const loadedIds = new Set(current.map((food) => String(food.id)));
            return [...current, ...page.filter((food) => !loadedIds.has(String(food.id)))];
          });
          setCatalogHasMore(results.length > catalogPageSize);
          setCatalogNextOffset(offset + page.length);
        } else {
          const message = await responseError(response, 'Could not load recent catalog foods.');
          if (requestId !== catalogRequestIdRef.current) return;
          if (!append) setFoods([]);
          setCatalogError(message);
          setCatalogRetry({
            type: 'recent',
            appliedRequest,
            pageOptions: { append, offset },
          });
        }
      } catch (_error) {
        if (requestId !== catalogRequestIdRef.current) return;
        if (!append) setFoods([]);
        setCatalogError('Could not load recent catalog foods.');
        setCatalogRetry({
          type: 'recent',
          appliedRequest,
          pageOptions: { append, offset },
        });
      } finally {
        if (requestId === catalogRequestIdRef.current) {
          if (append) setLoadingMoreFoods(false);
          else setSearching(false);
        }
      }
    },
    [token],
  );

  const runSearch = useCallback(
    async (overrides = {}, { append = false, offset = 0 } = {}) => {
      const nextQuery = overrides.query ?? query;
      const nextScope = overrides.scope ?? catalogScope;
      const nextOriginType = overrides.originType ?? catalogOriginType;
      const nextSort = overrides.sort ?? catalogSort;
      const nextProvider = overrides.provider ?? catalogProvider;
      const nextProvenance = overrides.provenance ?? catalogProvenance;
      const appliedRequest = {
        query: nextQuery,
        scope: nextScope,
        originType: nextOriginType,
        sort: nextSort,
        provider: nextProvider,
        provenance: nextProvenance,
      };
      const normalizedQuery = nextQuery.trim();
      const hasFilters =
        nextScope !== 'all' ||
        nextOriginType !== 'all' ||
        Boolean(nextProvider.trim()) ||
        nextProvenance !== 'all';
      if (
        !normalizedQuery &&
        !hasFilters &&
        (nextSort === 'recommended' || nextSort === 'recent')
      ) {
        loadRecentFoods({ append, offset }, appliedRequest);
        return;
      }
      const requestId = ++catalogRequestIdRef.current;
      if (append) {
        setLoadingMoreFoods(true);
      } else {
        setSearching(true);
        setLoadingMoreFoods(false);
        setHasSearched(true);
        setShowingRecentFoods(false);
        setFoods([]);
        setCatalogHasMore(false);
        setCatalogNextOffset(0);
      }
      setCatalogFeedback('');
      setCatalogError('');
      setCatalogRetry(null);
      if (!append) {
        appliedCatalogRequestRef.current = appliedRequest;
        setAppliedCatalogOriginType(nextOriginType);
        setAppliedCatalogProvider(nextProvider);
        setAppliedCatalogProvenance(nextProvenance);
      }
      const options = {
        limit: catalogPageSize + 1,
        offset,
        ordering:
          nextSort === 'name'
            ? 'name,id'
            : nextSort === 'logged'
              ? '-has_logged,-last_logged_on,name,id'
              : nextSort === 'recent' || !normalizedQuery
                ? '-created_at,-id'
                : 'relevance,name,id',
      };
      if (nextScope !== 'all') options.scope = nextScope;
      if (nextOriginType !== 'all') options.originType = nextOriginType;
      if (nextProvider.trim()) options.provider = nextProvider.trim();
      if (nextProvenance !== 'all') options.provenance = nextProvenance;
      try {
        const response = await searchFoods(normalizedQuery, token, options);
        if (requestId !== catalogRequestIdRef.current) return;
        if (response.ok) {
          const results = await response.json();
          if (requestId !== catalogRequestIdRef.current) return;
          const page = results.slice(0, catalogPageSize);
          setFoods((current) => {
            if (!append) return page;
            const loadedIds = new Set(current.map((food) => String(food.id)));
            return [...current, ...page.filter((food) => !loadedIds.has(String(food.id)))];
          });
          setCatalogHasMore(results.length > catalogPageSize);
          setCatalogNextOffset(offset + page.length);
        } else {
          const message = await responseError(response, 'Could not search the food catalog.');
          if (requestId !== catalogRequestIdRef.current) return;
          setCatalogError(message);
          setCatalogRetry({
            type: 'search',
            overrides: appliedRequest,
            pageOptions: { append, offset },
          });
        }
      } catch (_error) {
        if (requestId !== catalogRequestIdRef.current) return;
        setCatalogError('Could not search the food catalog.');
        setCatalogRetry({
          type: 'search',
          overrides: appliedRequest,
          pageOptions: { append, offset },
        });
      } finally {
        if (requestId === catalogRequestIdRef.current) {
          if (append) setLoadingMoreFoods(false);
          else setSearching(false);
        }
      }
    },
    [
      catalogOriginType,
      catalogProvider,
      catalogProvenance,
      catalogScope,
      catalogSort,
      loadRecentFoods,
      query,
      token,
    ],
  );

  const runAppliedCatalogSearch = useCallback(
    (overrides = {}, pageOptions = {}) =>
      runSearch({ ...appliedCatalogRequestRef.current, ...overrides }, pageOptions),
    [runSearch],
  );

  const retryCatalogRequest = () => {
    if (!catalogRetry) return;
    if (catalogRetry.type === 'recent') {
      loadRecentFoods(catalogRetry.pageOptions, catalogRetry.appliedRequest);
      return;
    }
    runSearch(catalogRetry.overrides, catalogRetry.pageOptions);
  };

  const resetCatalogFilters = () => {
    setCatalogScope('all');
    setCatalogOriginType('all');
    setCatalogProvider('');
    setCatalogProvenance('all');
    setCatalogFeedback('');
    setCatalogError('');
    setCatalogRetry(null);
    runAppliedCatalogSearch({
      scope: 'all',
      originType: 'all',
      provider: '',
      provenance: 'all',
    });
  };

  const clearCatalogFilter = (filter) => {
    const overrides = {};
    if (filter === 'scope') {
      setCatalogScope('all');
      overrides.scope = 'all';
    }
    if (filter === 'originType') {
      setCatalogOriginType('all');
    }
    if (filter === 'provider') {
      setCatalogProvider('');
    }
    if (filter === 'provenance') {
      setCatalogProvenance('all');
    }
    if (filter === 'originType') overrides.originType = 'all';
    if (filter === 'provider') overrides.provider = '';
    if (filter === 'provenance') overrides.provenance = 'all';
    runAppliedCatalogSearch(overrides);
  };

  const loadMoreCatalogFoods = () => {
    if (!catalogHasMore || searching || loadingMoreFoods) return;
    const pageOptions = { append: true, offset: catalogNextOffset };
    if (showingRecentFoods) {
      loadRecentFoods(pageOptions, appliedCatalogRequestRef.current);
    } else {
      runAppliedCatalogSearch({}, pageOptions);
    }
  };

  useEffect(() => {
    if (!open) {
      catalogRequestIdRef.current += 1;
      return;
    }
    const initialName = meal?.name ?? '';
    const initialNotes = meal?.notes ?? '';
    const initialDate = meal?.entry_date ?? date;
    const initialItems = meal ? meal.items.map(savedMealItemToEditableMealItem) : [];
    setEstimateDescription('');
    setEstimating(false);
    setName(initialName);
    setNotes(initialNotes);
    setEntryDate(initialDate);
    setItems(initialItems);
    setProposalId(null);
    setProposalContext(null);
    setCatalogPickerOpen(launchMode !== 'estimate');
    setAdjustment('');
    setAdjustmentBusy(false);
    setAdjustmentFeedback(null);
    setBaselineFingerprint(
      mealDraftFingerprint({
        name: initialName,
        notes: initialNotes,
        entryDate: initialDate,
        items: initialItems,
      }),
    );
    setQuery('');
    setCatalogScope('all');
    setCatalogOriginType('all');
    setCatalogSort('recommended');
    setCatalogFiltersOpen(false);
    setCatalogProvider('');
    setCatalogProvenance('all');
    setAppliedCatalogOriginType('all');
    setAppliedCatalogProvider('');
    setAppliedCatalogProvenance('all');
    appliedCatalogRequestRef.current = initialCatalogRequest;
    setCatalogFeedback('');
    setCatalogError('');
    setCatalogRetry(null);
    setFoods([]);
    setHasSearched(false);
    setShowingRecentFoods(false);
    setSearching(false);
    setLoadingMoreFoods(false);
    setCatalogHasMore(false);
    setCatalogNextOffset(0);
    setError('');
    setDiscardOpen(false);
    setCatalogActionsAnchorEl(null);
    setCatalogActionsFoodId(null);
    setCatalogDetailFoodIds(new Set());
    if (launchMode === 'estimate' && !meal) {
      setEstimatePlaceholder(randomMealEstimateExample());
    }
    window.requestAnimationFrame(() => {
      if (!meal && launchMode === 'add') catalogSearchRef.current?.focus();
    });
    if (meal || launchMode !== 'estimate') loadRecentFoods();
  }, [date, launchMode, loadRecentFoods, meal, open]);

  const createEstimate = async () => {
    const request = estimateDescription.trim();
    if (!request) {
      setError('Describe the meal you want to estimate.');
      return;
    }
    setEstimating(true);
    setError('');
    const response = await createMealProposal({ description: request, entry_date: date }, token);
    if (!response.ok) {
      setError(await responseError(response, 'Could not estimate this meal.'));
      setEstimating(false);
      return;
    }

    const proposal = await response.json();
    const proposalName = proposal.name ?? '';
    const proposalNotes = proposal.notes ?? '';
    const proposalDate = proposal.entry_date ?? date;
    const proposalItems = proposal.items?.map(proposalItemToMealItem) ?? [];
    setName(proposalName);
    setNotes(proposalNotes);
    setEntryDate(proposalDate);
    setItems(proposalItems);
    setProposalId(proposal.id);
    setProposalContext({
      provider_name: proposal.provider_name,
      provider_model: proposal.provider_model,
      confidence_score: proposal.confidence_score,
    });
    setCatalogPickerOpen(true);
    setQuery('');
    setBaselineFingerprint(
      mealDraftFingerprint({
        name: proposalName,
        notes: proposalNotes,
        entryDate: proposalDate,
        items: proposalItems,
      }),
    );
    setEstimating(false);
    loadRecentFoods();
  };

  const addFood = (food) => {
    setItems((current) => {
      if (current.some((item) => String(item.food_item) === String(food.id))) return current;
      return [...current, catalogFoodToMealItem(food)];
    });
    setCatalogFeedback(`${food.name} added to Meal Items.`);
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

  const applyAdjustment = async () => {
    const request = adjustment.trim();
    if (!request) {
      setAdjustmentFeedback({
        severity: 'warning',
        message: 'Describe what you want to add, remove, or correct.',
      });
      return;
    }
    setAdjustmentBusy(true);
    setError('');
    setAdjustmentFeedback(null);
    try {
      const payload = {
        adjustment: request,
        entry_date: entryDate,
        name: name.trim(),
        notes: notes.trim(),
        items: items.map(mealItemToProposalItem),
      };
      const response = meal
        ? await adjustMeal(meal.id, payload, token)
        : await adjustMealProposal(proposalId, payload, token);
      if (response.ok) {
        const result = await response.json();
        const updatedProposal = result.proposal;
        if (!meal) {
          setProposalId(updatedProposal.id);
        }
        if (result.applied) {
          setName(updatedProposal.name);
          if (updatedProposal.notes !== undefined) setNotes(updatedProposal.notes || '');
          if (updatedProposal.entry_date) setEntryDate(updatedProposal.entry_date);
          setItems(updatedProposal.items.map(proposalItemToMealItem));
          setProposalContext({
            provider_name: updatedProposal.provider_name,
            provider_model: updatedProposal.provider_model,
            confidence_score: updatedProposal.confidence_score,
          });
          setAdjustment('');
          setAdjustmentFeedback({ severity: 'success', message: result.message });
        } else {
          setAdjustmentFeedback({ severity: 'warning', message: result.message });
        }
      } else {
        setAdjustmentFeedback({
          severity: 'error',
          message: await responseError(
            response,
            'Could not apply that adjustment. Your current meal is still here.',
          ),
        });
      }
    } catch (_error) {
      setAdjustmentFeedback({
        severity: 'error',
        message: 'Could not reach AI. Your current meal and adjustment are still here.',
      });
    } finally {
      setAdjustmentBusy(false);
    }
  };

  const currentFingerprint = mealDraftFingerprint({
    name,
    notes,
    entryDate,
    items,
  });
  const hasUnsavedChanges = Boolean(
    baselineFingerprint && currentFingerprint !== baselineFingerprint,
  );
  const requestClose = () => {
    if (hasUnsavedChanges) {
      setDiscardOpen(true);
    } else {
      onClose();
    }
  };

  const save = async () => {
    if (!entryDate || !items.length) {
      setError('Choose a date and add at least one food.');
      return;
    }
    if ((meal || proposalId) && !name.trim()) {
      setError('Enter a meal name before saving.');
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
    if (proposalId) {
      const updateResponse = await updateMealProposal(
        proposalId,
        {
          name: name.trim(),
          notes: notes.trim(),
          entry_date: entryDate,
          items: items.map(mealItemToProposalItem),
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
      items: items.map(mealItemToProposalItem),
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

  const isEstimateStep = launchMode === 'estimate' && !meal && !proposalId;
  const mealHeader = isEstimateStep
    ? {
        eyebrow: null,
        title: 'Map it with AI',
        description: 'Tell us what you ate and we’ll create a meal estimate for you to fine tune.',
      }
    : meal
      ? {
          title: 'Edit meal',
          description: 'Update the meal details, catalog foods, and quantities in one place.',
        }
      : proposalContext
        ? {
            eyebrow: 'Review estimate',
            title: 'Map Your Meal',
            description: 'Your estimate is ready. Adjust anything you need before saving.',
          }
        : {
            eyebrow: null,
            title: 'Map Your Meal',
            description:
              'Chart today’s journey with catalog foods, personal foods, or AI guidance.',
          };
  const MealHeaderIcon =
    isEstimateStep || proposalContext ? AutoAwesomeIcon : RestaurantMenuOutlinedIcon;

  return (
    <>
      <Dialog
        open={open}
        onClose={estimating || saving || adjustmentBusy ? undefined : requestClose}
        fullWidth
        maxWidth="md"
        aria-labelledby="map-your-meal-header-title"
        aria-describedby="map-your-meal-description"
        sx={{
          '& .MuiDialog-paper': {
            m: { xs: 0, sm: 2 },
            width: { xs: '100%', sm: 'calc(100% - 32px)' },
            height: { xs: '100%', sm: 'auto' },
            maxHeight: { xs: '100%', sm: 'calc(100% - 32px)' },
            borderRadius: { xs: 0, sm: mealBuilderSurfaceRadius },
            bgcolor: 'var(--atlas-paper)',
            border: '1px solid var(--atlas-border-strong)',
            boxShadow: '0 24px 64px rgba(23, 50, 77, 0.16)',
          },
        }}
      >
        <DialogTitle
          component="div"
          sx={{
            bgcolor: meal ? 'var(--atlas-mineral-soft)' : 'var(--atlas-persimmon-soft)',
            color: 'var(--atlas-ink)',
            borderBottom: '1px solid var(--atlas-border)',
            px: { xs: 2, sm: 3 },
            py: { xs: 2, sm: 2.5 },
          }}
        >
          <Stack
            direction="row"
            spacing={1.5}
            sx={{
              alignItems: 'center',
            }}
          >
            <MealHeaderIcon
              sx={{
                flex: '0 0 auto',
                fontSize: { xs: 48, sm: 52 },
                color: meal ? 'var(--atlas-mineral)' : 'var(--atlas-persimmon-dark)',
              }}
            />
            <Box sx={{ minWidth: 0 }}>
              {mealHeader.eyebrow && (
                <Typography
                  component="p"
                  variant="overline"
                  sx={{ color: 'var(--atlas-ink-muted)', fontWeight: 800, lineHeight: 1.2 }}
                >
                  {mealHeader.eyebrow}
                </Typography>
              )}
              <Typography
                id="map-your-meal-header-title"
                component="h2"
                variant="h5"
                sx={{ display: 'block', mt: mealHeader.eyebrow ? 0.25 : 0 }}
              >
                {mealHeader.title}
              </Typography>
              <Typography
                id="map-your-meal-description"
                component="p"
                variant="body2"
                sx={{ color: 'var(--atlas-ink-muted)', mt: 0.5, maxWidth: 620 }}
              >
                {mealHeader.description}
              </Typography>
            </Box>
          </Stack>
        </DialogTitle>
        <DialogContent
          sx={{
            bgcolor: 'var(--atlas-paper)',
            borderColor: 'transparent',
            px: { xs: 2, sm: 3 },
            pt: '0 !important',
            '& > .MuiStack-root': {
              mt: { xs: 2.5, sm: 3 },
            },
          }}
        >
          {isEstimateStep ? (
            <Stack spacing={2.5}>
              {error && <Alert severity="error">{error}</Alert>}
              <TextField
                label="Describe what you ate"
                value={estimateDescription}
                onChange={(event) => setEstimateDescription(event.target.value)}
                placeholder={estimatePlaceholder}
                multiline
                minRows={3}
                autoFocus
              />
              <Typography variant="body2" sx={{ color: 'var(--atlas-ink-muted)' }}>
                MacroMapper checks your visible food catalog first. Matched foods use their existing
                nutrition data, while unmatched foods are estimated by GPT with web sources and
                remain editable before saving.
              </Typography>
            </Stack>
          ) : (
            <Stack spacing={1.25}>
              {error && <Alert severity="error">{error}</Alert>}
              {proposalContext && (
                <Stack
                  direction="row"
                  spacing={0.75}
                  useFlexGap
                  sx={{
                    flexWrap: 'wrap',
                  }}
                >
                  {proposalContext.provider_name && (
                    <Chip size="small" label={proposalContext.provider_name} variant="outlined" />
                  )}
                  <Chip size="small" label="AI Estimate" color="secondary" variant="outlined" />
                  {proposalContext.confidence_score != null && (
                    <Chip
                      size="small"
                      label={`${Math.round(Number(proposalContext.confidence_score) * 100)}% Confidence`}
                      variant="outlined"
                    />
                  )}
                </Stack>
              )}

              <Paper
                component="section"
                aria-labelledby="meal-identity-heading"
                elevation={0}
                sx={{
                  order: 1,
                  p: { xs: 1.5, sm: 2 },
                  border: '1px solid var(--atlas-border)',
                }}
              >
                <Typography id="meal-identity-heading" component="h3" variant="h6">
                  Meal Details
                </Typography>
                <Stack spacing={1.5} sx={{ mt: 1.5 }}>
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                    <TextField
                      label="Meal name"
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      helperText={
                        meal || proposalId
                          ? 'A name is required when updating an existing meal or proposal.'
                          : 'Optional. Leave blank to generate a name when you save.'
                      }
                      required={Boolean(meal || proposalId)}
                      fullWidth
                    />
                    <TextField
                      label="Date"
                      type="date"
                      value={entryDate}
                      onChange={(event) => setEntryDate(event.target.value)}
                      slotProps={{ inputLabel: { shrink: true } }}
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
                  order: 5,
                  p: { xs: 1.5, sm: 2 },
                  bgcolor: 'var(--atlas-mineral-soft)',
                  border: '1px solid rgba(71, 121, 138, 0.32)',
                }}
              >
                <Stack
                  direction="row"
                  sx={{
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 1,
                  }}
                >
                  <Box>
                    <Typography id="food-search-heading" component="h3" variant="h6">
                      Add from the Catalog
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        color: 'text.secondary',
                      }}
                    >
                      Search through the shared and personal catalog.
                    </Typography>
                  </Box>
                  <Stack
                    direction="row"
                    spacing={0.5}
                    sx={{
                      alignItems: 'center',
                    }}
                  >
                    {catalogPickerOpen && (hasSearched || showingRecentFoods) && (
                      <Chip
                        label={
                          showingRecentFoods
                            ? `${availableFoods.length} recent`
                            : `${availableFoods.length} shown`
                        }
                        size="small"
                        variant="outlined"
                      />
                    )}
                    <IconButton
                      size="small"
                      aria-label={`${catalogPickerOpen ? 'Collapse' : 'Expand'} Add from the Catalog`}
                      aria-expanded={catalogPickerOpen}
                      onClick={() => setCatalogPickerOpen((current) => !current)}
                    >
                      {catalogPickerOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                    </IconButton>
                  </Stack>
                </Stack>
                <Collapse in={catalogPickerOpen} unmountOnExit>
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mt: 1.5 }}>
                    <TextField
                      inputRef={catalogSearchRef}
                      label="Search catalog"
                      value={query}
                      onChange={(event) => {
                        const nextQuery = event.target.value;
                        setQuery(nextQuery);
                        if (!nextQuery.trim()) {
                          runAppliedCatalogSearch({ query: '' });
                        }
                      }}
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
                      onClick={() => runSearch()}
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
                  <Stack
                    data-testid="catalog-filter-toolbar"
                    direction={{ xs: 'column', sm: 'row' }}
                    spacing={1}
                    sx={{ mt: 1, alignItems: { sm: 'center' } }}
                  >
                    <Box sx={{ minWidth: 0, flex: 1, overflowX: 'auto' }}>
                      <ToggleButtonGroup
                        exclusive
                        size="small"
                        value={catalogScope}
                        onChange={(_event, nextScope) => {
                          if (!nextScope) return;
                          setCatalogScope(nextScope);
                          runAppliedCatalogSearch({ scope: nextScope });
                        }}
                        aria-label="Catalog scope"
                        sx={{
                          whiteSpace: 'nowrap',
                          '& .MuiToggleButton-root': {
                            px: 1.25,
                            py: 0.75,
                            fontWeight: 750,
                            textTransform: 'none',
                          },
                        }}
                      >
                        {catalogScopeOptions.map((option) => (
                          <ToggleButton key={option.value} value={option.value}>
                            {option.label}
                          </ToggleButton>
                        ))}
                      </ToggleButtonGroup>
                    </Box>
                    <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
                      <Button
                        size="small"
                        variant={
                          catalogFiltersOpen || advancedCatalogFilterCount ? 'outlined' : 'text'
                        }
                        startIcon={<TuneIcon />}
                        aria-expanded={catalogFiltersOpen}
                        aria-controls="catalog-advanced-filters"
                        onClick={() => setCatalogFiltersOpen((current) => !current)}
                        sx={{ minHeight: 40, whiteSpace: 'nowrap' }}
                      >
                        Filters
                        {advancedCatalogFilterCount ? ` (${advancedCatalogFilterCount})` : ''}
                      </Button>
                      <TextField
                        select
                        size="small"
                        label="Sort"
                        value={catalogSort}
                        onChange={(event) => {
                          const nextSort = event.target.value;
                          setCatalogSort(nextSort);
                          runAppliedCatalogSearch({ sort: nextSort });
                        }}
                        sx={{ minWidth: 150 }}
                      >
                        {catalogSortOptions.map((option) => (
                          <MenuItem key={option.value} value={option.value}>
                            {option.label}
                          </MenuItem>
                        ))}
                      </TextField>
                    </Stack>
                  </Stack>
                  <Collapse in={catalogFiltersOpen} unmountOnExit>
                    <Paper
                      id="catalog-advanced-filters"
                      elevation={0}
                      sx={{ mt: 1, p: 1, border: '1px solid var(--atlas-border)' }}
                    >
                      <Stack
                        data-testid="catalog-advanced-filter-controls"
                        direction={{ xs: 'column', md: 'row' }}
                        spacing={1}
                      >
                        <TextField
                          select
                          size="small"
                          label="Food type"
                          value={catalogOriginType}
                          onChange={(event) => setCatalogOriginType(event.target.value)}
                          sx={{ minWidth: { md: 150 } }}
                        >
                          <MenuItem value="all">Any food type</MenuItem>
                          {catalogOriginTypeOptions.map((option) => (
                            <MenuItem key={option.value} value={option.value}>
                              {option.label}
                            </MenuItem>
                          ))}
                        </TextField>
                        <TextField
                          size="small"
                          label="Provider or brand"
                          value={catalogProvider}
                          onChange={(event) => setCatalogProvider(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                              event.preventDefault();
                              runSearch();
                            }
                          }}
                          sx={{ flex: 1, minWidth: { sm: 180 } }}
                        />
                        <TextField
                          select
                          size="small"
                          label="Provenance"
                          value={catalogProvenance}
                          onChange={(event) => setCatalogProvenance(event.target.value)}
                          sx={{ minWidth: { sm: 180 } }}
                        >
                          <MenuItem value="all">Any provenance</MenuItem>
                          {Object.entries(provenanceLabels).map(([value, label]) => (
                            <MenuItem key={value} value={value}>
                              {label}
                            </MenuItem>
                          ))}
                        </TextField>
                        <Button
                          size="small"
                          variant="contained"
                          onClick={() => runSearch()}
                          sx={{ minHeight: 40, whiteSpace: 'nowrap' }}
                        >
                          Apply filters
                        </Button>
                        <Button
                          size="small"
                          onClick={resetCatalogFilters}
                          disabled={!hasCatalogFilters && !advancedCatalogFilterCount}
                          sx={{ minHeight: 40, whiteSpace: 'nowrap' }}
                        >
                          Clear all
                        </Button>
                      </Stack>
                    </Paper>
                  </Collapse>
                  {advancedCatalogFilterCount > 0 && (
                    <Stack
                      direction="row"
                      spacing={0.75}
                      useFlexGap
                      sx={{ mt: 1, flexWrap: 'wrap', alignItems: 'center' }}
                      aria-label="Active catalog filters"
                    >
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        Active filters
                      </Typography>
                      {appliedCatalogOriginType !== 'all' && (
                        <Chip
                          size="small"
                          label={`Type: ${catalogOriginTypeOptions.find((option) => option.value === appliedCatalogOriginType)?.label}`}
                          onDelete={() => clearCatalogFilter('originType')}
                        />
                      )}
                      {appliedCatalogProvider.trim() && (
                        <Chip
                          size="small"
                          label={`Provider: ${appliedCatalogProvider.trim()}`}
                          onDelete={() => clearCatalogFilter('provider')}
                        />
                      )}
                      {appliedCatalogProvenance !== 'all' && (
                        <Chip
                          size="small"
                          label={provenanceLabels[appliedCatalogProvenance]}
                          onDelete={() => clearCatalogFilter('provenance')}
                        />
                      )}
                    </Stack>
                  )}
                  {catalogError && (
                    <Alert
                      severity="error"
                      sx={{ mt: 1 }}
                      action={
                        <Button
                          color="inherit"
                          size="small"
                          onClick={retryCatalogRequest}
                          disabled={searching || loadingMoreFoods}
                        >
                          Retry
                        </Button>
                      }
                    >
                      {catalogError}
                    </Alert>
                  )}
                  {catalogFeedback && (
                    <Alert severity="success" sx={{ mt: 1 }} onClose={() => setCatalogFeedback('')}>
                      {catalogFeedback}
                    </Alert>
                  )}
                  {searching ? (
                    <Stack spacing={1} sx={{ mt: 1.5 }} aria-label="Loading food results">
                      {[0, 1].map((value) => (
                        <Skeleton key={value} variant="rounded" height={92} />
                      ))}
                    </Stack>
                  ) : catalogError && !availableFoods.length ? null : availableFoods.length ||
                    catalogHasMore ? (
                    <>
                      <List
                        disablePadding
                        aria-label="Food search results"
                        sx={{
                          maxHeight: 360,
                          mt: 1.5,
                          pr: 1,
                          overflowX: 'hidden',
                          overflowY: 'auto',
                          scrollbarGutter: 'stable',
                          scrollbarWidth: 'thin',
                          scrollbarColor: 'var(--atlas-border) transparent',
                          '&::-webkit-scrollbar': {
                            width: 10,
                          },
                          '&::-webkit-scrollbar-track': {
                            bgcolor: 'transparent',
                          },
                          '&::-webkit-scrollbar-thumb': {
                            bgcolor: 'var(--atlas-border)',
                            border: '3px solid transparent',
                            borderRadius: 999,
                            backgroundClip: 'padding-box',
                          },
                        }}
                      >
                        {availableFoods.map((food) => {
                          const version = food.current_version || {};
                          const source =
                            provenanceLabels[version.provenance] ||
                            (food.scope === 'personal' ? 'Personal' : 'Catalog');
                          const scopeLabel =
                            food.scope === 'personal'
                              ? 'My Food'
                              : food.scope === 'shared'
                                ? 'Shared'
                                : 'Catalog';
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
                                direction="row"
                                sx={{
                                  justifyContent: 'space-between',
                                  alignItems: 'flex-start',
                                  gap: 1,
                                }}
                              >
                                <Box sx={{ minWidth: 0, flex: 1 }}>
                                  <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
                                    {food.name}
                                  </Typography>
                                  <Stack
                                    direction="row"
                                    spacing={0.5}
                                    useFlexGap
                                    sx={{
                                      alignItems: 'baseline',
                                      flexWrap: 'wrap',
                                      color: 'text.secondary',
                                    }}
                                  >
                                    {food.provider_name && (
                                      <Typography
                                        component="span"
                                        variant="caption"
                                        sx={{ color: 'text.primary', fontWeight: 700 }}
                                      >
                                        {food.provider_name}
                                      </Typography>
                                    )}
                                    {food.provider_name && (
                                      <Typography component="span" variant="caption" aria-hidden>
                                        ·
                                      </Typography>
                                    )}
                                    <Typography component="span" variant="caption">
                                      {version.serving_label ||
                                        `${formatAmount(version.serving_quantity)} ${version.serving_unit || 'serving'}`}
                                    </Typography>
                                    <Typography component="span" variant="caption" aria-hidden>
                                      ·
                                    </Typography>
                                    <Typography
                                      component="span"
                                      variant="caption"
                                      sx={{ color: 'text.primary', fontWeight: 700 }}
                                    >
                                      {scopeLabel}
                                    </Typography>
                                  </Stack>
                                </Box>
                                <Stack
                                  direction="row"
                                  spacing={1}
                                  sx={{
                                    alignItems: 'center',
                                    flexShrink: 0,
                                  }}
                                >
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
                              <Box sx={{ mt: 1 }}>
                                <NutritionCards
                                  values={nutrientValues(version.nutrients)}
                                  ariaLabel={`${food.name} catalog nutrition`}
                                  compact
                                />
                              </Box>
                              <Collapse in={catalogDetailFoodIds.has(food.id)} unmountOnExit>
                                <Paper
                                  role="region"
                                  aria-label={`${food.name} estimate details`}
                                  elevation={0}
                                  sx={{
                                    mt: 0.75,
                                    p: 0.75,
                                    border: '1px solid var(--atlas-border)',
                                  }}
                                >
                                  <Stack
                                    direction="row"
                                    spacing={0.75}
                                    useFlexGap
                                    sx={{
                                      flexWrap: 'wrap',
                                    }}
                                  >
                                    {food.provider_name && (
                                      <Chip
                                        size="small"
                                        label={food.provider_name}
                                        variant="outlined"
                                      />
                                    )}
                                    <Chip size="small" label={source} variant="outlined" />
                                    {version.confidence_score != null && (
                                      <Chip
                                        size="small"
                                        label={`${Math.round(Number(version.confidence_score) * 100)}% Confidence`}
                                        variant="outlined"
                                      />
                                    )}
                                  </Stack>
                                  {version.sources?.length ? (
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
                                    <Typography
                                      variant="caption"
                                      sx={{
                                        color: 'text.secondary',
                                      }}
                                    >
                                      No source links were provided for this estimate.
                                    </Typography>
                                  )}
                                </Paper>
                              </Collapse>
                            </Paper>
                          );
                        })}
                        {catalogHasMore && (
                          <Box
                            component="li"
                            sx={{
                              display: 'flex',
                              justifyContent: 'center',
                              listStyle: 'none',
                              py: 0.25,
                            }}
                          >
                            <Button
                              size="small"
                              variant="text"
                              onClick={loadMoreCatalogFoods}
                              disabled={loadingMoreFoods}
                              startIcon={
                                loadingMoreFoods ? <CircularProgress size={16} /> : undefined
                              }
                              endIcon={loadingMoreFoods ? undefined : <ExpandMoreIcon />}
                              sx={{ fontWeight: 800 }}
                            >
                              {loadingMoreFoods ? 'Loading…' : `Show ${catalogPageSize} more`}
                            </Button>
                          </Box>
                        )}
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
                    <Typography
                      sx={{
                        color: 'text.secondary',
                        mt: 1.5,
                      }}
                    >
                      {showingRecentFoods
                        ? 'No recent foods are available yet. Search the catalog or create a personal food.'
                        : !hasSearched
                          ? 'Search by food or provider to see matching foods.'
                          : foods.length
                            ? 'All matching foods are already in this meal.'
                            : 'No foods matched this search and filter combination. Clear a filter or try another term.'}
                    </Typography>
                  )}
                </Collapse>
              </Paper>

              <Paper
                component="section"
                aria-labelledby="meal-items-heading"
                elevation={0}
                sx={{
                  order: 3,
                  p: { xs: 1.5, sm: 2 },
                  border: '1px solid var(--atlas-border-strong)',
                }}
              >
                <Stack
                  direction="row"
                  sx={{
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 1,
                  }}
                >
                  <Box>
                    <Typography id="meal-items-heading" component="h3" variant="h6">
                      Meal Items
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        color: 'text.secondary',
                      }}
                    >
                      Adjust quantities, units, nutrition, and components, or review each item’s
                      estimate details and sources.
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
                      borderRadius: mealBuilderSurfaceRadius,
                    }}
                  >
                    <RestaurantMenuOutlinedIcon sx={{ color: 'var(--atlas-mineral-dark)' }} />
                    <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
                      No meal items yet
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        color: 'text.secondary',
                      }}
                    >
                      Choose a recent or searched catalog food below, or use AI Adjustments to get
                      started.
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
                        allowNutritionEditing
                        allowComponentEditing
                        renderNutrition={(foodItem, onChange) => (
                          <ItemNutritionCards item={foodItem} compact onNutrientChange={onChange} />
                        )}
                      />
                    ))}
                  </Stack>
                )}
              </Paper>

              <Box sx={{ order: 2 }}>
                <MealNutritionSummary items={items} />
              </Box>

              <Paper
                component="section"
                aria-labelledby="ai-adjustments-heading"
                elevation={0}
                sx={{ order: 6, p: 1.25, border: '1px solid var(--atlas-border)' }}
              >
                <Stack spacing={0.75}>
                  <Stack
                    direction="row"
                    spacing={0.75}
                    sx={{
                      alignItems: 'center',
                    }}
                  >
                    <AutoAwesomeIcon
                      fontSize="small"
                      sx={{ color: 'var(--atlas-persimmon-dark)' }}
                    />
                    <Typography
                      id="ai-adjustments-heading"
                      variant="subtitle2"
                      sx={{ fontWeight: 800 }}
                    >
                      AI Adjustments
                    </Typography>
                  </Stack>
                  <Stack
                    direction={{ xs: 'column', sm: 'row' }}
                    spacing={0.75}
                    sx={{
                      alignItems: { sm: 'flex-end' },
                    }}
                  >
                    <TextField
                      label="Describe an AI adjustment"
                      value={adjustment}
                      onChange={(event) => {
                        setAdjustment(event.target.value);
                        setAdjustmentFeedback(null);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                          event.preventDefault();
                          applyAdjustment();
                        }
                      }}
                      placeholder="Add a medium chocolate milkshake"
                      multiline
                      minRows={1}
                      maxRows={3}
                      size="small"
                      slotProps={{ htmlInput: { maxLength: 500 } }}
                      disabled={adjustmentBusy}
                      fullWidth
                    />
                    <Button
                      variant="outlined"
                      color="secondary"
                      startIcon={
                        adjustmentBusy ? (
                          <CircularProgress size={16} color="inherit" />
                        ) : (
                          <SendIcon />
                        )
                      }
                      onClick={applyAdjustment}
                      disabled={adjustmentBusy || !adjustment.trim()}
                      sx={{ whiteSpace: 'nowrap', width: { xs: '100%', sm: 'auto' } }}
                    >
                      {adjustmentBusy ? 'Adjusting…' : 'Apply adjustment'}
                    </Button>
                  </Stack>
                  {adjustmentFeedback && (
                    <Alert severity={adjustmentFeedback.severity} sx={{ py: 0 }}>
                      {adjustmentFeedback.message}
                    </Alert>
                  )}
                </Stack>
              </Paper>
            </Stack>
          )}
        </DialogContent>
        <DialogActions
          sx={{
            bgcolor: 'var(--atlas-paper)',
            borderTop: '1px solid var(--atlas-border)',
            px: { xs: 1.5, sm: 3 },
            py: 1.25,
          }}
        >
          {isEstimateStep ? (
            <>
              <Button onClick={requestClose} disabled={estimating}>
                Cancel
              </Button>
              <Button
                variant="contained"
                color="secondary"
                onClick={createEstimate}
                disabled={estimating}
              >
                {estimating ? 'Estimating…' : 'Create estimate'}
              </Button>
            </>
          ) : (
            <>
              <Button onClick={requestClose} disabled={saving || adjustmentBusy}>
                Cancel
              </Button>
              <Button variant="contained" onClick={save} disabled={saving || adjustmentBusy}>
                {saving ? 'Saving…' : meal ? 'Save changes' : 'Save meal'}
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>
      <Dialog
        open={discardOpen}
        onClose={() => setDiscardOpen(false)}
        aria-labelledby="discard-meal-title"
      >
        <DialogTitle id="discard-meal-title">Discard meal changes?</DialogTitle>
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
  const [mapYourMeal, setMapYourMeal] = useState({ open: false, meal: null, launchMode: 'add' });
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
            data-testid="diary-header"
            direction={{ xs: 'column', md: 'row' }}
            spacing={1.5}
            sx={{
              alignItems: 'flex-start',
              justifyContent: 'space-between',
            }}
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
                Meal Log
              </Typography>
              <Typography sx={{ mt: 0.75, color: 'var(--atlas-ink-muted)' }}>
                Find your way to better nutrition, one meal at a time.
              </Typography>
            </Box>
            <Stack
              component="nav"
              aria-label="diary date navigation"
              direction="row"
              spacing={0.75}
              sx={{
                alignItems: 'center',
                alignSelf: { xs: 'flex-start', md: 'flex-end' },
              }}
            >
              <Box data-testid="return-to-today-slot" sx={{ width: 44, height: 44, flexShrink: 0 }}>
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
              </Box>
              <Paper
                data-testid="diary-date-control"
                elevation={0}
                sx={{
                  position: 'relative',
                  flexShrink: 0,
                  p: 0.375,
                  bgcolor: 'var(--atlas-paper)',
                  color: 'var(--atlas-ink)',
                  border: '1px solid var(--atlas-border)',
                  borderRadius: 999,
                }}
              >
                <Stack direction="row" spacing={0.125} sx={{ alignItems: 'center' }}>
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
              spacing={0.5}
              sx={{
                justifyContent: 'space-between',
                mb: 1.75,
              }}
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
                    <Stack
                      direction="row"
                      spacing={0.5}
                      sx={{
                        alignItems: 'baseline',
                        mt: 0.5,
                      }}
                    >
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
              data-testid="meal-log-toolbar"
              direction={{ xs: 'column', md: 'row' }}
              spacing={1.5}
              sx={{
                justifyContent: 'space-between',
                alignItems: { md: 'flex-end' },
                mb: 1.5,
              }}
            >
              <Box>
                <Stack
                  direction="row"
                  spacing={1}
                  sx={{
                    alignItems: 'center',
                  }}
                >
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
              <Stack
                data-testid="meal-log-actions"
                direction={{ xs: 'column', sm: 'row' }}
                spacing={1}
              >
                <Button
                  variant="contained"
                  color="secondary"
                  startIcon={<AutoAwesomeIcon />}
                  onClick={() => setMapYourMeal({ open: true, meal: null, launchMode: 'estimate' })}
                  sx={{ minHeight: 44 }}
                >
                  Map your Meal with AI
                </Button>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={() => setMapYourMeal({ open: true, meal: null, launchMode: 'add' })}
                  sx={{ minHeight: 44 }}
                >
                  Chart your Course Manually
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
                          spacing={1.5}
                          sx={{
                            justifyContent: 'space-between',
                            alignItems: { sm: 'flex-start' },
                          }}
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
                              sx={{
                                flexWrap: 'wrap',
                                mt: 1,
                              }}
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
                                  label={`${Math.round(mealConfidence * 100)}% Confidence`}
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
                            spacing={0.25}
                            sx={{
                              alignItems: 'center',
                              justifyContent: 'flex-end',
                              width: { xs: '100%', sm: 'auto' },
                            }}
                          >
                            <IconButton
                              aria-label={`edit ${meal.name}`}
                              onClick={() =>
                                setMapYourMeal({ open: true, meal, launchMode: 'edit' })
                              }
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

        <MapYourMealDialog
          date={date}
          meal={mapYourMeal.meal}
          open={mapYourMeal.open}
          token={token}
          launchMode={mapYourMeal.launchMode}
          onClose={() => setMapYourMeal({ open: false, meal: null, launchMode: 'add' })}
          onSaved={async (message) => {
            setMapYourMeal({ open: false, meal: null, launchMode: 'add' });
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
