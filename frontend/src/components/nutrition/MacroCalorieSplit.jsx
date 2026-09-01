import { Box, Paper, Skeleton, Stack, Typography } from '@mui/material';
import {
  formatWholeNutritionAmount,
  macroCalorieSegments,
  macroDonutBackground,
} from './nutritionMath';

export default function MacroCalorieSplit({
  values,
  loading = false,
  variant = 'compact',
  title = 'Macro Balance',
  chartAriaLabel,
}) {
  const dashboard = variant === 'dashboard';
  const mealCard = variant === 'meal-card';
  const segments = macroCalorieSegments(values);
  const macros = segments;

  return (
    <Paper
      component="figure"
      aria-label={chartAriaLabel || title}
      elevation={0}
      sx={{
        m: 0,
        p: 1,
        border: '1px solid var(--atlas-border)',
        borderRadius: 1.5,
        bgcolor: 'var(--atlas-paper)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Typography component="figcaption" variant="subtitle2" sx={{ fontWeight: 800, mb: 0.75 }}>
        {title}
      </Typography>
      {loading ? (
        <Stack
          direction="row"
          spacing={1.5}
          sx={{
            alignItems: 'center',
            justifyContent: 'center',
            flex: 1,
          }}
        >
          <Skeleton
            variant="circular"
            width={dashboard ? 152 : 112}
            height={dashboard ? 152 : 112}
          />
          <Stack spacing={0.5} sx={{ width: 120 }}>
            {[0, 1, 2].map((row) => (
              <Skeleton key={row} />
            ))}
          </Stack>
        </Stack>
      ) : (
        <Stack
          direction="row"
          spacing={dashboard ? 1 : mealCard ? { xs: 1.5, sm: 2 } : 1.5}
          sx={{
            alignItems: 'center',
            justifyContent: dashboard ? 'space-evenly' : 'center',
            width: '100%',
            maxWidth: dashboard || mealCard ? undefined : 380,
            mx: 'auto',
            flex: 1,
          }}
        >
          <Box
            role="img"
            aria-label={
              macros.length
                ? `${chartAriaLabel || 'Macro Balance'}: ${macros
                    .map((macro) => `${macro.label} ${Math.round(macro.percentage)} percent`)
                    .join(', ')}`
                : `${chartAriaLabel || 'Macro Balance'} unavailable`
            }
            sx={{
              position: 'relative',
              width: dashboard
                ? 'clamp(136px, 48%, 190px)'
                : mealCard
                  ? { xs: 120, sm: 140 }
                  : 'clamp(104px, 38%, 144px)',
              aspectRatio: '1 / 1',
              flex: '0 0 auto',
              borderRadius: '50%',
              background: macroDonutBackground(segments),
              display: 'grid',
              placeItems: 'center',
              '&::after': {
                content: '""',
                position: 'absolute',
                inset: dashboard || mealCard ? '21%' : '15%',
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
                {formatWholeNutritionAmount(values.calories)}
              </Typography>
              <Typography variant="caption" sx={{ color: 'var(--atlas-ink-muted)' }}>
                kcal
              </Typography>
            </Box>
          </Box>
          <Stack spacing={0.5} sx={{ minWidth: 0, flex: '0 0 auto' }}>
            {macros.map((macro) => (
              <Box
                key={macro.key}
                sx={{
                  display: 'grid',
                  gridTemplateColumns: '8px 48px auto',
                  columnGap: 0.75,
                  alignItems: 'center',
                }}
              >
                <Box
                  aria-hidden="true"
                  sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: macro.color }}
                />
                <Typography variant="caption">{macro.displayLabel}</Typography>
                <Typography
                  variant="caption"
                  className="numeric-data"
                  sx={{ fontWeight: 800, textAlign: 'right', whiteSpace: 'nowrap' }}
                >
                  {formatWholeNutritionAmount(macro.grams)} g ({Math.round(macro.percentage)}%)
                </Typography>
              </Box>
            ))}
          </Stack>
        </Stack>
      )}
    </Paper>
  );
}
