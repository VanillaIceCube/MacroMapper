import { Box, InputAdornment, Paper, Stack, TextField, Typography } from '@mui/material';
import { PRIMARY_NUTRIENT_FIELDS } from './nutritionDefinitions';
import { formatNutritionAmount, itemNutrientTotal } from './nutritionMath';

export function NutritionCards({
  values,
  ariaLabel,
  compact = false,
  itemName,
  onNutrientChange,
  editableNutrientKeys,
}) {
  return (
    <Box
      aria-label={ariaLabel}
      sx={{
        display: 'grid',
        width: '100%',
        gridTemplateColumns: {
          xs: 'repeat(2, minmax(0, 1fr))',
          sm: 'repeat(4, minmax(0, 1fr))',
        },
        gap: compact ? 0.5 : 0.75,
      }}
    >
      {PRIMARY_NUTRIENT_FIELDS.map(({ key, label, unit, note, color }) => {
        const isEditable =
          onNutrientChange && (!editableNutrientKeys || editableNutrientKeys.includes(key));
        return (
          <Paper
            key={key}
            elevation={0}
            sx={{
              minWidth: 0,
              minHeight: compact ? 58 : undefined,
              height: '100%',
              p: compact ? 0.75 : 1,
              border: '1px solid var(--atlas-border)',
              borderTop: `${compact ? 2 : 3}px solid ${color}`,
              bgcolor: 'var(--atlas-paper)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
            }}
          >
            <Typography
              variant={compact ? 'caption' : 'overline'}
              sx={{ color: 'var(--atlas-ink-muted)', lineHeight: 1.1, fontWeight: 700 }}
            >
              {label}
            </Typography>
            {isEditable ? (
              <TextField
                type="number"
                variant="standard"
                size="small"
                fullWidth
                value={values[key] ?? ''}
                onChange={(event) => onNutrientChange(key, event.target.value)}
                slotProps={{
                  htmlInput: {
                    min: 0,
                    step: 'any',
                    'aria-label': `${label} for ${itemName}`,
                  },
                  input: {
                    endAdornment: (
                      <InputAdornment position="end">
                        <Typography variant="caption">{unit}</Typography>
                      </InputAdornment>
                    ),
                  },
                }}
                sx={{
                  '& .MuiInputBase-input': {
                    py: 0.25,
                    fontSize: '1rem',
                    fontWeight: 700,
                    lineHeight: 1.15,
                  },
                }}
              />
            ) : (
              <Stack
                direction="row"
                spacing={0.4}
                sx={{
                  alignItems: 'baseline',
                  minWidth: 0,
                }}
              >
                <Typography variant={compact ? 'subtitle1' : 'h6'} noWrap sx={{ lineHeight: 1.15 }}>
                  {formatNutritionAmount(values[key])}
                </Typography>
                <Typography variant="caption" noWrap sx={{ color: 'var(--atlas-ink-muted)' }}>
                  {unit}
                </Typography>
              </Stack>
            )}
            {!compact && (
              <Typography
                variant="caption"
                sx={{ color: 'var(--atlas-ink-muted)', display: 'block', mt: 0.15 }}
              >
                {note}
              </Typography>
            )}
          </Paper>
        );
      })}
    </Box>
  );
}

export function ItemNutritionCards({ item, compact = false, onNutrientChange }) {
  const values = Object.fromEntries(
    PRIMARY_NUTRIENT_FIELDS.map(({ key }) => [key, itemNutrientTotal(item, key)]),
  );
  return (
    <NutritionCards
      values={values}
      ariaLabel={`${item.name} macro values`}
      compact={compact}
      itemName={item.name}
      onNutrientChange={onNutrientChange}
      editableNutrientKeys={item.components?.length ? ['calories'] : undefined}
    />
  );
}
