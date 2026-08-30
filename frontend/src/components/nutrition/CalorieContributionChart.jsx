import { Box, Paper, Skeleton, Stack, Tooltip, Typography } from '@mui/material';
import {
  decorateCalorieContributions,
  formatNutritionAmount,
  formatWholeNutritionAmount,
  summarizeCalorieContributions,
} from './nutritionMath';
import MacroCalorieBar from './MacroCalorieBar';

function OtherTooltipContent({ items, format }) {
  if (!items || !items.length) return null;
  const sorted = [...items].sort((a, b) => (b.calories || 0) - (a.calories || 0));

  return (
    <Box sx={{ p: 0.5, maxWidth: 280, minWidth: 160 }}>
      <Stack spacing={0.5}>
        {sorted.map((groupedItem, index) => (
          <Stack
            key={groupedItem.key || index}
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            spacing={1.5}
            sx={{ minWidth: 0 }}
          >
            <Typography
              variant="caption"
              noWrap
              sx={{ minWidth: 0, flex: 1, fontWeight: 600 }}
              title={groupedItem.name}
            >
              {groupedItem.name}
            </Typography>
            <Typography
              variant="caption"
              sx={{ whiteSpace: 'nowrap', flex: '0 0 auto', opacity: 0.9 }}
            >
              {format(groupedItem.calories)} kcal
            </Typography>
          </Stack>
        ))}
      </Stack>
    </Box>
  );
}

export default function CalorieContributionChart({
  contributions,
  title,
  chartAriaLabel,
  emptyText,
  loading = false,
  variant = 'compact',
  otherKey,
  otherLabel,
}) {
  const dashboard = variant === 'dashboard';
  const rows = decorateCalorieContributions(
    summarizeCalorieContributions(contributions, { otherKey, otherLabel }),
  );
  const format = dashboard ? formatWholeNutritionAmount : formatNutritionAmount;
  const ariaUnit = dashboard ? 'kilocalories' : 'kcal';

  return (
    <Paper
      component="figure"
      aria-label={title}
      elevation={0}
      sx={{
        m: 0,
        p: dashboard ? { xs: 1.25, sm: 1.5 } : 1,
        border: '1px solid var(--atlas-border)',
        borderRadius: dashboard ? 1.5 : undefined,
        bgcolor: 'var(--atlas-paper)',
      }}
    >
      <Typography
        component="figcaption"
        variant="subtitle2"
        sx={{ fontWeight: 800, mb: dashboard ? 1 : 0.75 }}
      >
        {title}
      </Typography>
      {loading ? (
        <Stack spacing={0.75}>
          {[0, 1, 2].map((row) => (
            <Skeleton key={row} variant="rounded" height={dashboard ? 20 : 14} />
          ))}
        </Stack>
      ) : rows.length ? (
        <Stack spacing={dashboard ? 0.8 : 0.6} aria-label={chartAriaLabel}>
          {rows.map((item) => {
            const calorieSummary = `${format(item.calories)} kcal (${Math.round(item.percentage)}%)`;
            const isOther = Boolean(item.isOther || (otherKey && item.key === otherKey));
            const groupedItems =
              item.groupedItems ||
              (item.componentNames?.map((name) => ({ name, calories: null })) ?? []);
            const hasGroupedTooltip = isOther && groupedItems.length > 0;

            const nameBox = (
              <Box
                tabIndex={hasGroupedTooltip ? 0 : undefined}
                aria-label={hasGroupedTooltip ? item.name : undefined}
                sx={{
                  width: dashboard ? { xs: 104, sm: 180, lg: 240 } : 112,
                  flex: '0 0 auto',
                  height: dashboard ? '2rem' : 'auto',
                  display: 'flex',
                  alignItems: 'center',
                  cursor: hasGroupedTooltip ? 'help' : undefined,
                }}
              >
                <Typography
                  variant="caption"
                  noWrap={!dashboard}
                  title={item.name}
                  sx={
                    dashboard
                      ? {
                          display: '-webkit-box',
                          WebkitBoxOrient: 'vertical',
                          WebkitLineClamp: 2,
                          overflow: 'hidden',
                          lineHeight: 1.2,
                        }
                      : undefined
                  }
                >
                  {item.name}
                </Typography>
              </Box>
            );

            return (
              <Box
                key={item.key}
                aria-label={`${item.name} ${format(item.calories)} ${ariaUnit} (${Math.round(item.percentage)}${dashboard ? ' percent' : '%'})`}
                tabIndex={0}
              >
                <Stack direction="row" spacing={0.75} alignItems="center" sx={{ minWidth: 0 }}>
                  {hasGroupedTooltip ? (
                    <Tooltip
                      title={<OtherTooltipContent items={groupedItems} format={format} />}
                      arrow
                      placement="top"
                    >
                      {nameBox}
                    </Tooltip>
                  ) : (
                    nameBox
                  )}
                  <Box sx={{ minWidth: 0, flex: 1 }}>
                    <MacroCalorieBar
                      name={item.name}
                      values={item}
                      widthPercentage={item.relativeBarWidth}
                      height={dashboard ? 20 : 14}
                      borderRadius={dashboard ? 10 : 7}
                      wholeNumbers={dashboard}
                    />
                  </Box>
                  <Typography
                    variant="caption"
                    className={dashboard ? 'numeric-data' : undefined}
                    sx={{
                      width: dashboard ? { xs: 92, sm: 106 } : 92,
                      flex: '0 0 auto',
                      color: dashboard ? 'var(--atlas-ink-muted)' : undefined,
                      fontSize: dashboard ? { xs: '0.68rem', sm: '0.75rem' } : undefined,
                      textAlign: 'right',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {calorieSummary}
                  </Typography>
                </Stack>
              </Box>
            );
          })}
        </Stack>
      ) : emptyText ? (
        <Typography
          variant={dashboard ? 'body2' : 'caption'}
          sx={{ color: 'var(--atlas-ink-muted)' }}
        >
          {emptyText}
        </Typography>
      ) : null}
    </Paper>
  );
}
