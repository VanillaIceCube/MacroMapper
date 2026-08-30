import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { Box, Chip, Collapse, IconButton, Paper, Stack, Typography } from '@mui/material';
import { useState } from 'react';
import CalorieContributionChart from './CalorieContributionChart';
import MacroCalorieSplit from './MacroCalorieSplit';
import { NutritionCards } from './NutritionCards';
import {
  formatNutritionAmount,
  itemCalorieContributions,
  mealNutrientValues,
} from './nutritionMath';

export default function MealNutritionSummary({ items }) {
  const [open, setOpen] = useState(true);
  const values = mealNutrientValues(items);
  const contributions = itemCalorieContributions(items);

  return (
    <Paper
      component="section"
      aria-label="Meal macro breakdown"
      elevation={0}
      sx={{ p: 1.25, border: '1px solid var(--atlas-border-strong)', bgcolor: 'var(--atlas-bone)' }}
    >
      <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
            Meal nutrition summary
          </Typography>
          <Typography variant="body2" sx={{ color: 'var(--atlas-ink-muted)' }}>
            Full-meal totals from the components below.
          </Typography>
        </Box>
        <Stack direction="row" spacing={0.5} alignItems="center">
          {!open && (
            <Chip
              size="small"
              label={`${formatNutritionAmount(values.calories)} kcal`}
              sx={{ fontWeight: 800, bgcolor: 'var(--atlas-paper)' }}
            />
          )}
          <IconButton
            size="small"
            aria-label={`${open ? 'Collapse' : 'Expand'} meal nutrition summary`}
            aria-expanded={open}
            onClick={() => setOpen((current) => !current)}
          >
            {open ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
        </Stack>
      </Stack>
      <Collapse in={open} unmountOnExit>
        <Box sx={{ mt: 1 }}>
          <NutritionCards values={values} ariaLabel="Full meal nutrition values" />
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'minmax(210px, 0.8fr) minmax(0, 1.2fr)' },
              gap: 0.75,
              mt: 0.75,
            }}
          >
            <MacroCalorieSplit values={values} />
            <CalorieContributionChart
              contributions={contributions}
              title="Calories by Component"
              chartAriaLabel="Component calorie chart"
              emptyText="Component calories are unavailable."
              otherKey="other-components"
            />
          </Box>
        </Box>
      </Collapse>
    </Paper>
  );
}
