import useSession, { useSessionGuard } from '../../hooks/authentication/useSession';
import AddIcon from '@mui/icons-material/Add';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
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
import { deleteMeal, fetchDailyDiary } from '../../services/meals/mealApiClient';
import CalorieContributionChart from '../../components/nutrition/CalorieContributionChart';
import MacroCalorieSplit from '../../components/nutrition/MacroCalorieSplit';
import { NUTRIENT_FIELDS as launchNutrients } from '../../components/nutrition/nutritionPresentation';
import { formatNutritionAmount as formatAmount } from '../../utils/nutritionFormatting';
import DiaryMealCard from '../../components/diary/DiaryMealCard';
import MealEditorDialog from '../../components/meal-editor/MealEditorDialog';

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

export default function DiaryPage({ showSnackbar = () => {} }) {
  const [date, setDate] = useState(localDate);
  const [data, setData] = useState({ meals: [], totals: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mealEditor, setMealEditor] = useState({ open: false, meal: null, launchMode: 'add' });
  const [pendingDelete, setPendingDelete] = useState(null);
  const dateInputRef = useRef(null);
  const diaryRequestIdRef = useRef(0);
  const isSignedIn = Boolean(useSession().accessToken);
  const isCurrentSession = useSessionGuard();

  const loadDiary = useCallback(async () => {
    if (!isSignedIn || !isCurrentSession()) return;
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
  }, [date, isSignedIn, isCurrentSession]);

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

  const mealsWithNutrition = useMemo(
    () =>
      data.meals.map((meal) => ({
        meal,
        nutrients: Object.fromEntries(
          launchNutrients.map(({ key }) => [key, mealNutrientAmount(meal, key)]),
        ),
      })),
    [data.meals],
  );
  const mealCalorieContributions = mealsWithNutrition
    .filter(({ nutrients }) => nutrients.calories !== null)
    .map(({ meal, nutrients }) => ({
      ...nutrients,
      key: meal.id,
      name: meal.name,
      calories: Math.max(nutrients.calories, 0),
    }));

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
              <Typography sx={{ mt: 0.75, color: 'var(--muted-text)' }}>
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
                  bgcolor: 'var(--surface-background)',
                  color: 'var(--surface-text)',
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
                        color: 'var(--surface-text)',
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
              bgcolor: 'var(--surface-background)',
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
              <Typography variant="body2" sx={{ color: 'var(--muted-text)' }}>
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
                    bgcolor: 'var(--surface-background)',
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
                      <Typography variant="caption" noWrap sx={{ color: 'var(--muted-text)' }}>
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
                        sx={{ bgcolor: 'var(--atlas-mineral-soft)', color: 'var(--surface-text)' }}
                      />
                    </Stack>
                  )}
                </Stack>
                <Typography variant="body2" sx={{ mt: 0.25, color: 'var(--muted-text)' }}>
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
                  bgcolor: 'var(--surface-background)',
                  color: 'var(--surface-text)',
                  border: '1px dashed var(--atlas-border-strong)',
                  borderRadius: 'var(--atlas-radius-prominent)',
                }}
              >
                <RestaurantMenuOutlinedIcon
                  sx={{ fontSize: 42, color: 'var(--atlas-forest)', mb: 1 }}
                />
                <Typography variant="h6">Nothing logged yet</Typography>
                <Typography sx={{ mt: 0.5, color: 'var(--muted-text)' }}>
                  Estimate a meal or add foods manually to start this day’s log.
                </Typography>
              </Paper>
            ) : (
              <Stack spacing={1.25} aria-label="meal log">
                {mealsWithNutrition.map(({ meal, nutrients }, index) => (
                  <DiaryMealCard
                    key={meal.id}
                    meal={meal}
                    mealNumber={index + 1}
                    nutrients={nutrients}
                    dailyCalories={Number(totalsByKey.calories?.amount)}
                    onEdit={(selectedMeal) =>
                      setMealEditor({ open: true, meal: selectedMeal, launchMode: 'edit' })
                    }
                    onDelete={setPendingDelete}
                  />
                ))}
              </Stack>
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
              bgcolor: 'var(--surface-background)',
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
