import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlineOutlined';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import { Box, Chip, IconButton, Paper, Stack, Typography } from '@mui/material';
import { selectedPortion, servingAmountValue } from '../domain/meal-item';
import { nutrientArrayToValues as nutrientValues } from '../domain/nutrition';
import {
  formatNutritionAmount as formatAmount,
  formatWholeNutritionAmount as formatWholeAmount,
} from '../utils/nutritionFormatting';
import MacroCalorieBar from './nutrition/MacroCalorieBar';
import MacroCalorieSplit from './nutrition/MacroCalorieSplit';
import { foodEvidenceLabel } from './nutrition/nutritionPresentation';

const mealContextText = (notes) => notes.replace(/^Estimated from:\s*/i, '').trim() || notes;

const mealItemNutrientAmount = (item, nutrientKey) => {
  const amount = Number(item.nutrients.find((value) => value.key === nutrientKey)?.amount);
  return Number.isFinite(amount) ? amount : null;
};

export default function DiaryMealCard({
  meal,
  mealNumber,
  nutrients,
  dailyCalories,
  onEdit,
  onDelete,
}) {
  const dailyShare =
    nutrients.calories !== null && Number.isFinite(dailyCalories) && dailyCalories > 0
      ? Math.round((nutrients.calories / dailyCalories) * 100)
      : null;
  const mealConfidence = Number(meal.confidence_score);
  const hasMealConfidence = meal.confidence_score !== null && Number.isFinite(mealConfidence);
  const highestFoodCalories = Math.max(
    ...meal.items.map((item) => mealItemNutrientAmount(item, 'calories') ?? 0),
  );

  return (
    <Paper
      component="article"
      elevation={0}
      sx={{
        p: 2,
        bgcolor: 'var(--surface-background)',
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
            Meal {String(mealNumber).padStart(2, '0')}
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
                color: 'var(--surface-text)',
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
            onClick={() => onEdit(meal)}
            sx={{ width: 44, height: 44, color: 'var(--atlas-forest-dark)' }}
          >
            <EditOutlinedIcon />
          </IconButton>
          <IconButton
            aria-label={`delete ${meal.name}`}
            onClick={() => onDelete(meal)}
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
                  bgcolor: 'var(--page-background)',
                  borderBottom: '1px solid var(--atlas-border)',
                }}
              >
                {['Food & Servings', 'Calories', 'Confidence', 'Provenance'].map((label) => (
                  <Typography
                    key={label}
                    role="columnheader"
                    variant="caption"
                    sx={{ color: 'var(--muted-text)', fontWeight: 800 }}
                  >
                    {label}
                  </Typography>
                ))}
              </Box>
              {meal.items.map((item, itemIndex) => {
                const itemCalories = mealItemNutrientAmount(item, 'calories');
                const confidence = Number(item.confidence_score);
                const hasConfidence = item.confidence_score !== null && Number.isFinite(confidence);
                const portion = selectedPortion(item);
                const isNaturalSize = portion.key.startsWith('size:');
                const count = isNaturalSize ? servingAmountValue(item) : item.servings;
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
                      <Typography variant="body2" sx={{ fontWeight: 800, lineHeight: 1.25 }}>
                        {formatAmount(count)} × {item.food_name}
                      </Typography>
                      {itemContext && (
                        <Typography
                          variant="caption"
                          sx={{
                            display: 'block',
                            mt: 0.2,
                            color: 'var(--muted-text)',
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
                          color: 'var(--muted-text)',
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
                          color: 'var(--muted-text)',
                        }}
                      >
                        Confidence
                      </Typography>
                      <Typography variant="body2" className="numeric-data" sx={{ fontWeight: 750 }}>
                        {hasConfidence ? `${Math.round(confidence * 100)}%` : 'Not scored'}
                      </Typography>
                    </Box>
                    <Box role="cell" sx={{ minWidth: 0 }}>
                      <Typography
                        variant="caption"
                        sx={{
                          display: { sm: 'none' },
                          color: 'var(--muted-text)',
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
                  bgcolor: 'var(--page-background)',
                  borderLeft: '3px solid var(--atlas-mineral)',
                  borderRadius: 'var(--atlas-radius-compact)',
                }}
              >
                <Typography
                  variant="caption"
                  sx={{
                    display: 'block',
                    color: 'var(--muted-text)',
                    fontWeight: 800,
                  }}
                >
                  Context
                </Typography>
                <Typography
                  variant="body2"
                  sx={{
                    mt: 0.15,
                    color: 'var(--muted-text)',
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
              values={nutrients}
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
                    bgcolor: 'var(--surface-background)',
                    border: '1px solid var(--atlas-border-strong)',
                    borderTop: `2px solid ${color}`,
                    borderRadius: 'var(--atlas-radius-surface)',
                  }}
                >
                  <Typography variant="caption" sx={{ color, fontWeight: 800 }}>
                    {label}
                  </Typography>
                  <Typography className="numeric-data" sx={{ fontWeight: 800 }}>
                    {formatAmount(nutrients[key])} {unit}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>
        </Box>
      </Box>
    </Paper>
  );
}
