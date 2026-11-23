import useSession, { useSessionGuard } from '../hooks/useSession';
import AddIcon from '@mui/icons-material/Add';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlineOutlined';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import RefreshIcon from '@mui/icons-material/Refresh';
import RestaurantMenuOutlinedIcon from '@mui/icons-material/RestaurantMenuOutlined';
import TodayOutlinedIcon from '@mui/icons-material/TodayOutlined';
import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { deleteMeal, fetchDailyDiary } from '../services/mealApiClient';
import { selectedPortion, servingAmountValue } from '../domain/mealItem';
import CalorieContributionChart from '../components/nutrition/CalorieContributionChart';
import MacroCalorieBar from '../components/nutrition/MacroCalorieBar';
import MacroCalorieSplit from '../components/nutrition/MacroCalorieSplit';
import {
  MACRO_CALORIE_FIELDS as macroCalorieFields,
  NUTRIENT_FIELDS as launchNutrients,
  foodEvidenceLabel,
} from '../components/nutrition/nutritionPresentation';
import {
  formatNutritionAmount as formatAmount,
  formatWholeNutritionAmount as formatWholeAmount,
} from '../utils/nutritionFormatting';
import { nutrientArrayToValues as nutrientValues } from '../domain/nutrition';
import MealEditorDialog from '../components/meal-editor/MealEditorDialog';

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

export default function DiaryPage({ showSnackbar = () => {} }) {
  const [date, setDate] = useState(localDate);
  const [data, setData] = useState({ meals: [], totals: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mealEditor, setMealEditor] = useState({ open: false, meal: null, launchMode: 'add' });
  const [pendingDelete, setPendingDelete] = useState(null);
  const dateInputRef = useRef(null);
  const diaryRequestIdRef = useRef(0);
  const { accessToken } = useSession();
  const isCurrentSession = useSessionGuard();

  const loadDiary = useCallback(async () => {
    if (!accessToken || !isCurrentSession()) return;
    const requestId = ++diaryRequestIdRef.current;
    setData({ meals: [], totals: [] });
    setLoading(true);
    setError('');
    try {
      const result = await fetchDailyDiary(date);
      if (requestId === diaryRequestIdRef.current) setData(result);
    } catch (error) {
      if (requestId === diaryRequestIdRef.current) {
        setError(error.message);
      }
    } finally {
      if (requestId === diaryRequestIdRef.current) setLoading(false);
    }
  }, [date, accessToken, isCurrentSession]);

  useEffect(() => {
    loadDiary();
    return () => {
      diaryRequestIdRef.current += 1;
    };
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
    if (!isCurrentSession()) return;
    try {
      await deleteMeal(pendingDelete.id);
      if (!isCurrentSession()) return;
      setPendingDelete(null);
      showSnackbar('success', 'Meal deleted.');
      await loadDiary();
    } catch (error) {
      if (isCurrentSession()) {
        setPendingDelete(null);
        setError(error.message);
      }
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
                  borderRadius: 'var(--atlas-radius-pill)',
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
                  <Box sx={{ position: 'relative', display: 'flex' }}>
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
                    <Box
                      component="input"
                      ref={dateInputRef}
                      aria-label="diary date"
                      type="date"
                      value={date}
                      onChange={(event) => {
                        if (event.target.value) setDate(event.target.value);
                      }}
                      tabIndex={-1}
                      sx={{
                        position: 'absolute',
                        inset: 0,
                        width: '100%',
                        height: '100%',
                        boxSizing: 'border-box',
                        p: 0,
                        border: 0,
                        opacity: 0,
                        pointerEvents: 'none',
                      }}
                    />
                  </Box>
                  <IconButton
                    aria-label="next day"
                    onClick={() => setDate((current) => shiftDate(current, 1))}
                    sx={{ width: 44, height: 44 }}
                  >
                    <ChevronRightIcon />
                  </IconButton>
                </Stack>
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
              borderRadius: 'var(--atlas-radius-prominent)',
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
                Daily Summary
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
                    borderRadius: 'var(--atlas-radius-surface)',
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
                    Meal Log
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
                  onClick={() => setMealEditor({ open: true, meal: null, launchMode: 'estimate' })}
                  sx={{ minHeight: 44 }}
                >
                  Map your Meal with AI
                </Button>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={() => setMealEditor({ open: true, meal: null, launchMode: 'add' })}
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
                  borderRadius: 'var(--atlas-radius-prominent)',
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
                          borderRadius: 'var(--atlas-radius-surface)',
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
                                setMealEditor({ open: true, meal, launchMode: 'edit' })
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
                                  borderRadius: 'var(--atlas-radius-compact)',
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
                                  {['Food & Servings', 'Calories', 'Confidence', 'Provenance'].map(
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
                                  const portion = selectedPortion(item);
                                  const isNaturalSize = portion.key.startsWith('size:');
                                  const count = isNaturalSize
                                    ? servingAmountValue(item)
                                    : item.servings;
                                  const itemContext = [
                                    item.provider_name,
                                    isNaturalSize ? portion.label : item.serving_label,
                                  ]
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
                                        alignItems: { sm: 'center' },
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
                                          {formatAmount(count)} × {item.food_name}
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
                                          {foodEvidenceLabel(item)}
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
                                    borderRadius: 'var(--atlas-radius-compact)',
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
                                      borderRadius: 'var(--atlas-radius-surface)',
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

        <MealEditorDialog
          date={date}
          meal={mealEditor.meal}
          open={mealEditor.open}
          launchMode={mealEditor.launchMode}
          onClose={() => setMealEditor((current) => ({ ...current, open: false }))}
          onSaved={async (message) => {
            setMealEditor((current) => ({ ...current, open: false }));
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
