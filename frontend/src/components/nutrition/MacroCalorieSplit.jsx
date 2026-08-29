import { Box, Paper, Skeleton, Stack, Typography } from '@mui/material';
import { MACRO_CALORIE_FIELDS } from './nutritionDefinitions';
import {
  formatNutritionAmount,
  formatWholeNutritionAmount,
  macroCalorieSegments,
  macroDonutBackground,
} from './nutritionMath';

export default function MacroCalorieSplit({
  values,
  loading = false,
  variant = 'compact',
  title = 'Macro calorie split',
}) {
  const dashboard = variant === 'dashboard';
  const segments = macroCalorieSegments(values);
  const segmentByKey = Object.fromEntries(segments.map((segment) => [segment.key, segment]));
  const macros = MACRO_CALORIE_FIELDS.map((field) => ({
    ...field,
    grams: Math.max(Number(values[field.key]) || 0, 0),
    percentage: segmentByKey[field.key]?.percentage || 0,
  }));
  const format = dashboard ? formatWholeNutritionAmount : formatNutritionAmount;

  return (
    <Paper
      component={dashboard ? 'figure' : 'div'}
      aria-label={dashboard ? title : undefined}
      elevation={0}
      sx={{
        m: 0,
        p: dashboard ? { xs: 1.25, sm: 1.5 } : 1,
        border: '1px solid var(--atlas-border)',
        borderRadius: dashboard ? 1.5 : undefined,
        bgcolor: 'var(--atlas-paper)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Typography
        component={dashboard ? 'figcaption' : 'div'}
        variant="subtitle2"
        sx={{ fontWeight: 800, mb: 0.75 }}
      >
        {title}
      </Typography>
      {loading ? (
        <Stack
          direction="row"
          spacing={1.5}
          alignItems="center"
          justifyContent="center"
          sx={{ flex: 1 }}
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
          spacing={dashboard ? 1 : 1.5}
          alignItems="center"
          justifyContent={dashboard ? 'space-evenly' : 'center'}
          sx={{ width: '100%', maxWidth: dashboard ? undefined : 380, mx: 'auto', flex: 1 }}
        >
          <Box
            role="img"
            aria-label={`Macro calorie split: ${macros
              .map(
                (macro) =>
                  `${macro.label} ${Math.round(macro.percentage)}${dashboard ? ' percent' : '%'}`,
              )
              .join(', ')}`}
            sx={{
              position: 'relative',
              width: dashboard ? 'clamp(136px, 48%, 190px)' : 'clamp(104px, 38%, 144px)',
              aspectRatio: '1 / 1',
              flex: '0 0 auto',
              borderRadius: '50%',
              background: macroDonutBackground(segments),
              display: 'grid',
              placeItems: 'center',
              '&::after': {
                content: '""',
                position: 'absolute',
                inset: dashboard ? '21%' : '15%',
                borderRadius: '50%',
                bgcolor: 'var(--atlas-paper)',
              },
            }}
          >
            <Box sx={{ position: 'relative', zIndex: 1, textAlign: 'center' }}>
              <Typography
                variant="subtitle1"
                className={dashboard ? 'numeric-data' : undefined}
                sx={{ fontWeight: 800, lineHeight: 1.1 }}
              >
                {format(values.calories)}
              </Typography>
              <Typography variant="caption" sx={{ color: 'var(--atlas-ink-muted)' }}>
                kcal
              </Typography>
            </Box>
          </Box>
          <Stack spacing={0.5} sx={{ minWidth: 0, flex: dashboard ? '0 0 auto' : '0 1 auto' }}>
            {macros.map((macro) => (
              <Stack key={macro.key} direction="row" alignItems="center" spacing={0.75}>
                <Box
                  aria-hidden="true"
                  sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: macro.color }}
                />
                <Typography variant="caption" sx={{ flex: '0 0 48px' }}>
                  {macro.displayLabel}
                </Typography>
                <Typography
                  variant="caption"
                  className={dashboard ? 'numeric-data' : undefined}
                  sx={{ fontWeight: 800, whiteSpace: 'nowrap' }}
                >
                  {format(macro.grams)} g ({Math.round(macro.percentage)}%)
                </Typography>
              </Stack>
            ))}
          </Stack>
        </Stack>
      )}
    </Paper>
  );
}
