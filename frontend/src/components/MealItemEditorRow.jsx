import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlineOutlined';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import {
  Box,
  Button,
  Chip,
  Collapse,
  IconButton,
  Link,
  Menu,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import {
  displayedPortionOptions,
  portionOptionLabel,
  selectedPortion,
  servingAmountValue,
} from './mealItemPortions';

const sourceLabels = {
  official_verified: { label: 'Official / verified', color: 'success' },
  catalog_estimate: { label: 'Catalog estimate', color: 'info' },
  community_estimate: { label: 'Community estimate', color: 'info' },
  ai_estimate: { label: 'AI estimate', color: 'warning' },
  user_modified_estimate: { label: 'AI estimate — adjusted by you', color: 'warning' },
  user_entered: { label: 'User entered', color: 'default' },
};

export default function MealItemEditorRow({
  item,
  depth = 0,
  onServings,
  onPortionChange,
  onNutrientChange,
  onRemove,
  renderNutrition,
  allowNutritionEditing = true,
  allowComponentEditing = true,
}) {
  const [componentsOpen, setComponentsOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [nutritionEditing, setNutritionEditing] = useState(false);
  const [actionsAnchorEl, setActionsAnchorEl] = useState(null);
  const source = sourceLabels[item.source_kind] || sourceLabels.ai_estimate;
  const isComponent = depth > 0;
  const canEditItem = !isComponent || allowComponentEditing;
  const options = displayedPortionOptions(item);
  const activePortion = selectedPortion(item);
  const hasDetails =
    item.confidence_score != null || item.provider_name || Boolean(item.sources?.length);
  const hasActions = hasDetails || canEditItem;
  const accentColor =
    item.source_kind === 'ai_estimate' || item.source_kind === 'user_modified_estimate'
      ? 'var(--atlas-persimmon)'
      : item.source_kind === 'official_verified'
        ? 'var(--atlas-forest)'
        : 'var(--atlas-mineral)';

  return (
    <Paper
      elevation={0}
      sx={{
        ml: depth > 1 ? { xs: 1, sm: 2 } : 0,
        my: isComponent ? 0.25 : 0.35,
        bgcolor: isComponent ? 'var(--atlas-bone)' : 'var(--atlas-paper)',
        border: isComponent
          ? '1px solid var(--atlas-border-strong)'
          : '1px solid var(--atlas-border)',
        borderLeft: `4px solid ${accentColor}`,
        overflow: 'hidden',
      }}
    >
      <Box sx={{ p: 0.6 }}>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: 'minmax(0, 1fr) auto',
              sm: 'minmax(110px, 0.65fr) minmax(280px, 1.7fr) 80px',
              md: '150px minmax(270px, 1fr) auto 80px',
            },
            gridTemplateAreas: {
              xs: '"identity actions" "nutrition nutrition" "controls controls"',
              sm: '"identity nutrition actions" "controls controls controls"',
              md: '"identity nutrition controls actions"',
            },
            columnGap: 0.75,
            rowGap: { xs: 0, sm: 0.5 },
            alignItems: 'center',
          }}
        >
          <Box sx={{ gridArea: 'identity', minWidth: 0, pl: 0.25 }}>
            <Typography
              variant="body2"
              title={item.name}
              sx={{
                color: 'var(--atlas-ink)',
                fontSize: '0.84rem',
                fontWeight: 800,
                lineHeight: 1.15,
                overflowWrap: 'anywhere',
              }}
            >
              {item.name}
            </Typography>
          </Box>
          <Box sx={{ minWidth: 0, gridArea: 'nutrition' }}>
            {renderNutrition(
              item,
              nutritionEditing
                ? (nutrient, value) => onNutrientChange(item.key, nutrient, value)
                : undefined,
            )}
          </Box>
          <Box
            sx={{
              gridArea: 'controls',
              mt: { xs: 1.1, sm: 0 },
              display: 'grid',
              width: '100%',
              gridTemplateColumns: {
                xs: '72px minmax(0, 1fr)',
                sm: '72px 112px',
              },
              gridTemplateAreas: '"quantity portion"',
              alignItems: 'center',
              justifyContent: { sm: 'end' },
              columnGap: 0.75,
            }}
          >
            <TextField
              label="Count"
              type="number"
              size="small"
              value={servingAmountValue(item)}
              onChange={(event) => onServings(item.key, event.target.value, item)}
              disabled={!canEditItem}
              inputProps={{ min: 0, step: 1 }}
              sx={{ gridArea: 'quantity', minWidth: 0, width: '100%' }}
            />
            <TextField
              select
              label="Unit"
              size="small"
              value={activePortion.key}
              onChange={(event) => onPortionChange(item.key, event.target.value)}
              disabled={!canEditItem || options.length < 2}
              sx={{ gridArea: 'portion', minWidth: 0, width: '100%' }}
            >
              {options.map((option) => (
                <MenuItem key={option.key} value={option.key}>
                  {portionOptionLabel(option)}
                </MenuItem>
              ))}
            </TextField>
          </Box>
          <Stack
            direction="row"
            spacing={0}
            alignItems="center"
            justifyContent="flex-end"
            sx={{ gridArea: 'actions', flexShrink: 0 }}
          >
            {!!item.components?.length && (
              <Button
                size="small"
                color="inherit"
                endIcon={componentsOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                aria-label={`${componentsOpen ? 'Collapse' : 'Expand'} components for ${item.name}`}
                aria-expanded={componentsOpen}
                onClick={() => setComponentsOpen((current) => !current)}
                title={`${componentsOpen ? 'Hide' : 'Show'} components`}
                sx={{
                  minWidth: 0,
                  minHeight: 24,
                  px: 0.35,
                  py: 0,
                  color: 'var(--atlas-ink-muted)',
                  fontWeight: 800,
                  '& .MuiButton-endIcon': { ml: 0.2 },
                }}
              >
                {item.components.length}
              </Button>
            )}
            {hasActions && (
              <>
                <IconButton
                  size="small"
                  aria-label={`More actions for ${item.name}`}
                  aria-haspopup="menu"
                  aria-expanded={Boolean(actionsAnchorEl)}
                  onClick={(event) => setActionsAnchorEl(event.currentTarget)}
                  sx={{ p: 0.2 }}
                >
                  <MoreVertIcon fontSize="small" />
                </IconButton>
                <Menu
                  anchorEl={actionsAnchorEl}
                  open={Boolean(actionsAnchorEl)}
                  onClose={() => setActionsAnchorEl(null)}
                  MenuListProps={{ 'aria-label': `Actions for ${item.name}` }}
                >
                  {hasDetails && (
                    <MenuItem
                      aria-label={`${detailsOpen ? 'Hide' : 'Show'} estimate details for ${item.name}`}
                      onClick={() => {
                        setDetailsOpen((current) => !current);
                        setActionsAnchorEl(null);
                      }}
                    >
                      <InfoOutlinedIcon fontSize="small" sx={{ mr: 1.25 }} />
                      {detailsOpen ? 'Hide details' : 'Estimate details'}
                    </MenuItem>
                  )}
                  {allowNutritionEditing && canEditItem && (
                    <MenuItem
                      aria-label={`${nutritionEditing ? 'Finish editing' : 'Edit'} nutrition for ${item.name}`}
                      selected={nutritionEditing}
                      onClick={() => {
                        setNutritionEditing((current) => !current);
                        setActionsAnchorEl(null);
                      }}
                    >
                      <EditOutlinedIcon fontSize="small" sx={{ mr: 1.25 }} />
                      {nutritionEditing ? 'Finish editing' : 'Edit nutrition'}
                    </MenuItem>
                  )}
                  {canEditItem && (
                    <MenuItem
                      aria-label={`remove ${item.name}`}
                      onClick={() => {
                        setActionsAnchorEl(null);
                        onRemove(item.key);
                      }}
                      sx={{ color: 'error.main' }}
                    >
                      <DeleteOutlineIcon fontSize="small" sx={{ mr: 1.25 }} />
                      Remove
                    </MenuItem>
                  )}
                </Menu>
              </>
            )}
          </Stack>
        </Box>
        {hasDetails && (
          <Collapse in={detailsOpen} unmountOnExit>
            <Paper elevation={0} sx={{ mt: 0.5, p: 0.75, border: '1px solid var(--atlas-border)' }}>
              <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mt: 0.25 }}>
                <Chip size="small" label={source.label} color={source.color} variant="outlined" />
                {item.confidence_score != null && (
                  <Chip
                    size="small"
                    label={`${Math.round(Number(item.confidence_score) * 100)}% confidence`}
                    variant="outlined"
                  />
                )}
                {item.provider_name && (
                  <Chip size="small" label={item.provider_name} variant="outlined" />
                )}
              </Stack>
              {!!item.sources?.length && (
                <Stack component="ul" spacing={0.25} sx={{ my: 0.5, pl: 2.25 }}>
                  {item.sources.map((entry) => (
                    <Typography component="li" variant="caption" key={entry.url}>
                      <Link href={entry.url} target="_blank" rel="noopener noreferrer">
                        {entry.title}
                      </Link>
                      {entry.is_official ? ' · official source' : ''}
                    </Typography>
                  ))}
                </Stack>
              )}
            </Paper>
          </Collapse>
        )}
        {!!item.components?.length && (
          <Collapse in={componentsOpen} unmountOnExit>
            <Stack spacing={0.75} sx={{ mt: 0.85 }}>
              {item.components.map((component) => (
                <MealItemEditorRow
                  key={component.key}
                  item={component}
                  depth={depth + 1}
                  onServings={onServings}
                  onPortionChange={onPortionChange}
                  onNutrientChange={onNutrientChange}
                  onRemove={onRemove}
                  renderNutrition={renderNutrition}
                  allowNutritionEditing={allowNutritionEditing}
                  allowComponentEditing={allowComponentEditing}
                />
              ))}
            </Stack>
          </Collapse>
        )}
      </Box>
    </Paper>
  );
}
