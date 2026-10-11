import { Box } from '@mui/material';
import {
  formatNutritionAmount,
  formatWholeNutritionAmount,
  macroCalorieSegments,
} from './nutritionMath';

export default function MacroCalorieBar({
  name,
  values,
  widthPercentage = 100,
  height = 14,
  borderRadius = 7,
  wholeNumbers = false,
}) {
  const segments = macroCalorieSegments(values);
  const format = wholeNumbers ? formatWholeNutritionAmount : formatNutritionAmount;
  const ariaUnit = wholeNumbers ? 'kilocalories' : 'kcal';
  const stackLabel = segments.length
    ? `${name} macro calorie stack: ${segments
        .map((segment) => `${segment.label} ${format(segment.calories)} ${ariaUnit}`)
        .join(', ')}`
    : `${name} macro calorie stack unavailable`;

  return (
    <Box
      role="img"
      aria-label={stackLabel}
      sx={{
        height,
        minWidth: 0,
        width: '100%',
        bgcolor: 'var(--atlas-border)',
        borderRadius,
        overflow: 'hidden',
      }}
    >
      <Box
        sx={{
          height: '100%',
          width: `${Math.max(widthPercentage, Number(values.calories) > 0 ? 2 : 0)}%`,
          display: 'flex',
          bgcolor: segments.length ? 'transparent' : 'var(--calorie-color)',
          borderRadius,
          overflow: 'hidden',
        }}
      >
        {segments.map((segment) => (
          <Box key={segment.key} sx={{ width: `${segment.percentage}%`, bgcolor: segment.color }} />
        ))}
      </Box>
    </Box>
  );
}
