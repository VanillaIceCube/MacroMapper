import AddIcon from '@mui/icons-material/Add';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import SearchIcon from '@mui/icons-material/Search';
import TuneIcon from '@mui/icons-material/Tune';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
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
import { searchFoods } from '../../services/mealApiClient';
import { getResponseErrorMessage, safeReadJson } from '../../services/authSession';
import { nutrientArrayToValues as nutrientValues } from '../../domain/nutrition';
import { formatNutritionAmount as formatAmount } from '../../utils/nutritionFormatting';
import { NutritionCards } from '../nutrition/NutritionCards';
import { foodEvidenceLabel, foodProvenanceLabels } from '../nutrition/nutritionPresentation';

const catalogPageSize = 20;
const catalogFilterDefaults = {
  scope: 'all',
  originType: 'all',
  provider: '',
  provenance: 'all',
};
const defaultCatalogFilters = { ...catalogFilterDefaults, query: '', sort: 'recommended' };
const newestFoodsFirst = '-created_at,-id';
const catalogOrdering = {
  name: 'name,id',
  recent: newestFoodsFirst,
  logged: '-has_logged,-last_logged_on,name,id',
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

function hasCatalogFilters({ scope, originType, provider, provenance }) {
  return (
    scope !== 'all' || originType !== 'all' || Boolean(provider.trim()) || provenance !== 'all'
  );
}

function showsRecentFoods(filters) {
  return (
    !filters.query.trim() &&
    !hasCatalogFilters(filters) &&
    (filters.sort === 'recommended' || filters.sort === 'recent')
  );
}

export default function FoodCatalogPicker({
  open,
  token,
  mealItems,
  focusSearchOnOpen,
  onAddFood,
}) {
  const [catalogPickerOpen, setCatalogPickerOpen] = useState(true);
  const [draftFilters, setDraftFilters] = useState(defaultCatalogFilters);
  const [appliedFilters, setAppliedFilters] = useState(null);
  const [catalogFiltersOpen, setCatalogFiltersOpen] = useState(false);
  const [catalogFeedback, setCatalogFeedback] = useState('');
  const [catalogError, setCatalogError] = useState(null);
  const [foods, setFoods] = useState([]);
  const [catalogLoading, setCatalogLoading] = useState(null);
  const [nextPageOffset, setNextPageOffset] = useState(null);
  const [catalogActionsAnchorEl, setCatalogActionsAnchorEl] = useState(null);
  const [catalogActionsFoodId, setCatalogActionsFoodId] = useState(null);
  const [catalogDetailFoodIds, setCatalogDetailFoodIds] = useState(() => new Set());
  const catalogSearchRef = useRef(null);
  const catalogRequestIdRef = useRef(0);
  const selectedFoodIds = useMemo(
    () => new Set(mealItems.map((item) => String(item.food_item))),
    [mealItems],
  );
  const availableFoods = useMemo(
    () => foods.filter((food) => !selectedFoodIds.has(String(food.id))),
    [foods, selectedFoodIds],
  );
  const activeCatalogFood = availableFoods.find((food) => food.id === catalogActionsFoodId);
  const filtersInUse = appliedFilters ?? defaultCatalogFilters;
  const {
    originType: appliedOriginType,
    provider: appliedProvider,
    provenance: appliedProvenance,
  } = filtersInUse;
  const showingRecentFoods = appliedFilters !== null && showsRecentFoods(appliedFilters);
  const searching = catalogLoading === 'search';
  const loadingMoreFoods = catalogLoading === 'more';
  const catalogHasMore = nextPageOffset !== null;
  const advancedCatalogFilterCount =
    Number(appliedOriginType !== 'all') +
    Number(Boolean(appliedProvider.trim())) +
    Number(appliedProvenance !== 'all');

  const loadCatalogPage = useCallback(
    async (filters, offset = 0) => {
      const requestId = ++catalogRequestIdRef.current;
      const isLatestRequest = () => requestId === catalogRequestIdRef.current;
      const append = offset > 0;
      const recent = showsRecentFoods(filters);
      const query = filters.query.trim();
      const provider = filters.provider.trim();
      const fallbackError = recent
        ? 'Could not load recent catalog foods.'
        : 'Could not search the food catalog.';

      setCatalogLoading(append ? 'more' : 'search');
      if (!append) setAppliedFilters(filters);
      if (!recent) setCatalogFeedback('');
      setCatalogError(null);

      const showLoadError = (message) => {
        if (!isLatestRequest()) return;
        if (!append) {
          setFoods([]);
          setNextPageOffset(null);
        }
        setCatalogError({ message, filters, offset });
      };

      const options = {
        limit: catalogPageSize + 1,
        offset,
        ordering: catalogOrdering[filters.sort] ?? (query ? 'relevance,name,id' : newestFoodsFirst),
      };
      if (filters.scope !== 'all') options.scope = filters.scope;
      if (filters.originType !== 'all') options.originType = filters.originType;
      if (provider) options.provider = provider;
      if (filters.provenance !== 'all') options.provenance = filters.provenance;

      try {
        const response = await searchFoods(query, token, options);
        if (!isLatestRequest()) return;
        if (!response.ok) {
          showLoadError(await getResponseErrorMessage(response, fallbackError));
          return;
        }

        const results = (await safeReadJson(response)) || [];
        if (!isLatestRequest()) return;
        const page = results.slice(0, catalogPageSize);
        setFoods((current) => {
          if (!append) return page;
          const loadedIds = new Set(current.map((food) => String(food.id)));
          return [...current, ...page.filter((food) => !loadedIds.has(String(food.id)))];
        });
        setNextPageOffset(results.length > catalogPageSize ? offset + page.length : null);
      } catch (_error) {
        showLoadError(fallbackError);
      } finally {
        if (isLatestRequest()) setCatalogLoading(null);
      }
    },
    [token],
  );

  const updateDraftFilter = (name, value) => {
    setDraftFilters((current) => ({ ...current, [name]: value }));
  };

  // Scope, sort, and clear actions apply only their own changes. Search and
  // Apply filters submit all draft fields together.
  const applyFilterChanges = (changes) => {
    setDraftFilters((current) => ({ ...current, ...changes }));
    loadCatalogPage({ ...filtersInUse, ...changes });
  };

  const resetCatalogFilters = () => {
    setCatalogFeedback('');
    applyFilterChanges(catalogFilterDefaults);
  };

  const clearCatalogFilter = (name) => {
    applyFilterChanges({ [name]: catalogFilterDefaults[name] });
  };

  useEffect(() => {
    if (!open) return undefined;
    setCatalogPickerOpen(true);
    setDraftFilters(defaultCatalogFilters);
    setCatalogFiltersOpen(false);
    setCatalogFeedback('');
    setFoods([]);
    setNextPageOffset(null);
    setCatalogActionsAnchorEl(null);
    setCatalogActionsFoodId(null);
    setCatalogDetailFoodIds(new Set());
    loadCatalogPage(defaultCatalogFilters);

    const focusFrame = focusSearchOnOpen
      ? window.requestAnimationFrame(() => catalogSearchRef.current?.focus())
      : null;
    return () => {
      catalogRequestIdRef.current += 1;
      if (focusFrame !== null) window.cancelAnimationFrame(focusFrame);
    };
  }, [open, loadCatalogPage, focusSearchOnOpen]);

  const addFood = (food) => {
    onAddFood(food);
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

  return (
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
          {catalogPickerOpen && appliedFilters && (
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
            value={draftFilters.query}
            onChange={(event) => {
              const nextQuery = event.target.value;
              updateDraftFilter('query', nextQuery);
              if (!nextQuery.trim()) {
                loadCatalogPage({ ...filtersInUse, query: '' });
              }
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                loadCatalogPage(draftFilters);
              }
            }}
            fullWidth
          />
          <Button
            variant="outlined"
            onClick={() => loadCatalogPage(draftFilters)}
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
              value={draftFilters.scope}
              onChange={(_event, nextScope) => {
                if (!nextScope) return;
                applyFilterChanges({ scope: nextScope });
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
              variant={catalogFiltersOpen || advancedCatalogFilterCount ? 'outlined' : 'text'}
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
              value={draftFilters.sort}
              onChange={(event) => applyFilterChanges({ sort: event.target.value })}
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
                value={draftFilters.originType}
                onChange={(event) => updateDraftFilter('originType', event.target.value)}
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
                value={draftFilters.provider}
                onChange={(event) => updateDraftFilter('provider', event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    loadCatalogPage(draftFilters);
                  }
                }}
                sx={{ flex: 1, minWidth: { sm: 180 } }}
              />
              <TextField
                select
                size="small"
                label="Provenance"
                value={draftFilters.provenance}
                onChange={(event) => updateDraftFilter('provenance', event.target.value)}
                sx={{ minWidth: { sm: 180 } }}
              >
                <MenuItem value="all">Any provenance</MenuItem>
                {Object.entries(foodProvenanceLabels).map(([value, label]) => (
                  <MenuItem key={value} value={value}>
                    {label}
                  </MenuItem>
                ))}
              </TextField>
              <Button
                size="small"
                variant="contained"
                onClick={() => loadCatalogPage(draftFilters)}
                sx={{ minHeight: 40, whiteSpace: 'nowrap' }}
              >
                Apply filters
              </Button>
              <Button
                size="small"
                onClick={resetCatalogFilters}
                disabled={!hasCatalogFilters(draftFilters) && !advancedCatalogFilterCount}
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
            {appliedOriginType !== 'all' && (
              <Chip
                size="small"
                label={`Type: ${catalogOriginTypeOptions.find((option) => option.value === appliedOriginType)?.label}`}
                onDelete={() => clearCatalogFilter('originType')}
              />
            )}
            {appliedProvider.trim() && (
              <Chip
                size="small"
                label={`Provider: ${appliedProvider.trim()}`}
                onDelete={() => clearCatalogFilter('provider')}
              />
            )}
            {appliedProvenance !== 'all' && (
              <Chip
                size="small"
                label={foodProvenanceLabels[appliedProvenance]}
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
                onClick={() => loadCatalogPage(catalogError.filters, catalogError.offset)}
                disabled={searching || loadingMoreFoods}
              >
                Retry
              </Button>
            }
          >
            {catalogError.message}
          </Alert>
        )}
        {catalogFeedback && (
          <Alert severity="success" sx={{ mt: 1 }} onClose={() => setCatalogFeedback('')}>
            {catalogFeedback}
          </Alert>
        )}
        {searching && !availableFoods.length ? (
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
              aria-busy={searching}
              sx={{
                maxHeight: 360,
                mt: 1.5,
                pr: 1,
                overflowX: 'hidden',
                overflowY: 'auto',
                opacity: searching ? 0.55 : 1,
                pointerEvents: searching ? 'none' : 'auto',
                transition: 'opacity 120ms ease',
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
                  borderRadius: 'var(--atlas-radius-pill)',
                  backgroundClip: 'padding-box',
                },
              }}
            >
              {availableFoods.map((food) => {
                const version = food.current_version || {};
                const source =
                  foodEvidenceLabel(version) ||
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
                        <Button
                          onClick={() => addFood(food)}
                          disabled={searching}
                          startIcon={<AddIcon />}
                        >
                          Add
                        </Button>
                        <IconButton
                          size="small"
                          disabled={searching}
                          aria-label={`More actions for ${food.name}`}
                          aria-haspopup="menu"
                          aria-expanded={
                            catalogActionsFoodId === food.id && Boolean(catalogActionsAnchorEl)
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
                            <Chip size="small" label={food.provider_name} variant="outlined" />
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
                    onClick={() => loadCatalogPage(filtersInUse, nextPageOffset)}
                    disabled={searching || loadingMoreFoods}
                    startIcon={loadingMoreFoods ? <CircularProgress size={16} /> : undefined}
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
              : !appliedFilters
                ? 'Search by food or provider to see matching foods.'
                : foods.length
                  ? 'All matching foods are already in this meal.'
                  : 'No foods matched this search and filter combination. Clear a filter or try another term.'}
          </Typography>
        )}
      </Collapse>
    </Paper>
  );
}
