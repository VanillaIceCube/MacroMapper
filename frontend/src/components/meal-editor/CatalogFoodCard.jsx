import AddIcon from '@mui/icons-material/Add';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import {
  Box,
  Button,
  Chip,
  Collapse,
  IconButton,
  Link,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import { nutrientArrayToValues as nutrientValues } from '../../domain/nutrition';
import { formatNutritionAmount as formatAmount } from '../../utils/nutritionFormatting';
import { NutritionCards } from '../nutrition/NutritionCards';
import { foodEvidenceLabel } from '../nutrition/nutritionPresentation';

export default function CatalogFoodCard({
  food,
  disabled,
  actionsOpen,
  detailsOpen,
  onAddFood,
  onOpenActions,
}) {
  const version = food.current_version || {};
  const source = foodEvidenceLabel(version) || (food.scope === 'personal' ? 'Personal' : 'Catalog');
  const scopeLabel =
    food.scope === 'personal' ? 'My Food' : food.scope === 'shared' ? 'Shared' : 'Catalog';
  return (
    <Paper
      component="li"
      elevation={0}
      sx={{
        listStyle: 'none',
        mb: 1,
        p: 1.25,
        bgcolor: 'var(--surface-background)',
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
          <Button onClick={() => onAddFood(food)} disabled={disabled} startIcon={<AddIcon />}>
            Add
          </Button>
          <IconButton
            size="small"
            disabled={disabled}
            aria-label={`More actions for ${food.name}`}
            aria-haspopup="menu"
            aria-expanded={actionsOpen}
            onClick={(event) => onOpenActions(food.id, event.currentTarget)}
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
      <Collapse in={detailsOpen} unmountOnExit>
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
                    <Link href={estimateSource.url} target="_blank" rel="noopener noreferrer">
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
}
