import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import RestaurantMenuOutlinedIcon from '@mui/icons-material/RestaurantMenuOutlined';
import SendIcon from '@mui/icons-material/Send';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useEffect, useState } from 'react';
import {
  acceptMealProposal,
  adjustMeal,
  adjustMealProposal,
  createMeal,
  createMealProposal,
  updateMeal,
  updateMealProposal,
} from '../../services/mealApiClient';
import { getResponseErrorMessage, safeReadJson } from '../../services/authSession';
import {
  catalogFoodToMealItem,
  changeMealItemNutrient,
  changeMealItemPortion,
  changeMealItemServings,
  mealItemToProposalItem,
  proposalItemToMealItem,
  removeMealItemFromTree,
  savedMealItemToEditableMealItem,
} from '../../domain/mealItem';
import { randomMealEstimateExample } from '../../mealEstimateExamples';
import MealItemEditorRow from '../MealItemEditorRow';
import MealNutritionSummary from '../nutrition/MealNutritionSummary';
import { ItemNutritionCards } from '../nutrition/NutritionCards';
import FoodCatalogPicker from './FoodCatalogPicker';

const mealBuilderSurfaceRadius = 'var(--atlas-radius-prominent)';

const mealDraftFingerprint = ({ name, notes, entryDate, items }) =>
  JSON.stringify({
    name,
    notes,
    entryDate,
    items,
  });

export default function MealEditorDialog({
  date,
  meal,
  open,
  token,
  launchMode,
  onClose,
  onSaved,
}) {
  const [estimateDescription, setEstimateDescription] = useState('');
  const [estimatePlaceholder, setEstimatePlaceholder] = useState(randomMealEstimateExample);
  const [estimating, setEstimating] = useState(false);
  const [name, setName] = useState('');
  const [notes, setNotes] = useState('');
  const [entryDate, setEntryDate] = useState(date);
  const [items, setItems] = useState([]);
  const [proposalId, setProposalId] = useState(null);
  const [proposalContext, setProposalContext] = useState(null);
  const [adjustment, setAdjustment] = useState('');
  const [adjustmentBusy, setAdjustmentBusy] = useState(false);
  const [adjustmentFeedback, setAdjustmentFeedback] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [discardOpen, setDiscardOpen] = useState(false);
  const [baselineFingerprint, setBaselineFingerprint] = useState('');

  useEffect(() => {
    if (!open) return;
    const initialName = meal?.name ?? '';
    const initialNotes = meal?.notes ?? '';
    const initialDate = meal?.entry_date ?? date;
    const initialItems = meal ? meal.items.map(savedMealItemToEditableMealItem) : [];
    setEstimateDescription('');
    setEstimating(false);
    setName(initialName);
    setNotes(initialNotes);
    setEntryDate(initialDate);
    setItems(initialItems);
    setProposalId(null);
    setProposalContext(null);
    setAdjustment('');
    setAdjustmentBusy(false);
    setAdjustmentFeedback(null);
    setBaselineFingerprint(
      mealDraftFingerprint({
        name: initialName,
        notes: initialNotes,
        entryDate: initialDate,
        items: initialItems,
      }),
    );
    setError('');
    setDiscardOpen(false);
    if (launchMode === 'estimate' && !meal) {
      setEstimatePlaceholder(randomMealEstimateExample());
    }
  }, [date, launchMode, meal, open, token]);

  const createEstimate = async () => {
    const request = estimateDescription.trim();
    if (!request) {
      setError('Describe the meal you want to estimate.');
      return;
    }
    setEstimating(true);
    setError('');
    try {
      const response = await createMealProposal({ description: request, entry_date: date }, token);
      if (!response.ok) {
        setError(await getResponseErrorMessage(response, 'Could not estimate this meal.'));
        return;
      }

      const proposal = await safeReadJson(response);
      if (!proposal) {
        setError('Could not parse estimation response.');
        return;
      }
      const proposalName = proposal.name ?? '';
      const proposalNotes = proposal.notes ?? '';
      const proposalDate = proposal.entry_date ?? date;
      const proposalItems = proposal.items?.map(proposalItemToMealItem) ?? [];
      setName(proposalName);
      setNotes(proposalNotes);
      setEntryDate(proposalDate);
      setItems(proposalItems);
      setProposalId(proposal.id);
      setProposalContext({
        provider_name: proposal.provider_name,
        provider_model: proposal.provider_model,
        confidence_score: proposal.confidence_score,
      });
      setBaselineFingerprint(
        mealDraftFingerprint({
          name: proposalName,
          notes: proposalNotes,
          entryDate: proposalDate,
          items: proposalItems,
        }),
      );
    } catch (_error) {
      setError(
        'Could not reach the server. Your meal description is still here. Please try again.',
      );
    } finally {
      setEstimating(false);
    }
  };

  const addFood = (food) => {
    setItems((current) => {
      if (current.some((item) => String(item.food_item) === String(food.id))) return current;
      return [...current, catalogFoodToMealItem(food)];
    });
  };

  const changeServings = (key, amount, item) => {
    setItems((current) => changeMealItemServings(current, key, amount, item));
  };

  const changePortion = (key, selectedPortionKey) => {
    setItems((current) => changeMealItemPortion(current, key, selectedPortionKey));
  };

  const changeNutrient = (key, nutrient, totalValue) => {
    setItems((current) => changeMealItemNutrient(current, key, nutrient, totalValue));
  };

  const removeItem = (key) => {
    setItems((current) => removeMealItemFromTree(current, key));
  };

  const applyAdjustment = async () => {
    const request = adjustment.trim();
    if (!request) {
      setAdjustmentFeedback({
        severity: 'warning',
        message: 'Describe what you want to add, remove, or correct.',
      });
      return;
    }
    setAdjustmentBusy(true);
    setError('');
    setAdjustmentFeedback(null);
    try {
      const payload = {
        adjustment: request,
        entry_date: entryDate,
        name: name.trim(),
        notes: notes.trim(),
        items: items.map(mealItemToProposalItem),
      };
      const response = meal
        ? await adjustMeal(meal.id, payload, token)
        : await adjustMealProposal(proposalId, payload, token);
      if (response.ok) {
        const result = await safeReadJson(response);
        if (!result) {
          setAdjustmentFeedback({
            severity: 'error',
            message: 'Could not parse adjustment response.',
          });
          return;
        }
        const updatedProposal = result.proposal;
        if (!meal) {
          setProposalId(updatedProposal.id);
        }
        if (result.applied) {
          setName(updatedProposal.name);
          if (updatedProposal.notes !== undefined) setNotes(updatedProposal.notes || '');
          if (updatedProposal.entry_date) setEntryDate(updatedProposal.entry_date);
          setItems(updatedProposal.items.map(proposalItemToMealItem));
          setProposalContext({
            provider_name: updatedProposal.provider_name,
            provider_model: updatedProposal.provider_model,
            confidence_score: updatedProposal.confidence_score,
          });
          setAdjustment('');
          setAdjustmentFeedback({ severity: 'success', message: result.message });
        } else {
          setAdjustmentFeedback({ severity: 'warning', message: result.message });
        }
      } else {
        setAdjustmentFeedback({
          severity: 'error',
          message: await getResponseErrorMessage(
            response,
            'Could not apply that adjustment. Your current meal is still here.',
          ),
        });
      }
    } catch (_error) {
      setAdjustmentFeedback({
        severity: 'error',
        message: 'Could not reach AI. Your current meal and adjustment are still here.',
      });
    } finally {
      setAdjustmentBusy(false);
    }
  };

  const currentFingerprint = mealDraftFingerprint({
    name,
    notes,
    entryDate,
    items,
  });
  const hasUnsavedChanges = Boolean(
    baselineFingerprint && currentFingerprint !== baselineFingerprint,
  );
  const requestClose = () => {
    if (hasUnsavedChanges) {
      setDiscardOpen(true);
    } else {
      onClose();
    }
  };

  const save = async () => {
    if (!entryDate || !items.length) {
      setError('Choose a date and add at least one food.');
      return;
    }
    if ((meal || proposalId) && !name.trim()) {
      setError('Enter a meal name before saving.');
      return;
    }
    if (
      items.some((item) => !Number.isFinite(Number(item.servings)) || Number(item.servings) <= 0)
    ) {
      setError('Each meal item needs a quantity greater than zero.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      if (proposalId) {
        const updateResponse = await updateMealProposal(
          proposalId,
          {
            name: name.trim(),
            notes: notes.trim(),
            entry_date: entryDate,
            items: items.map(mealItemToProposalItem),
          },
          token,
        );
        if (!updateResponse.ok) {
          setError(
            await getResponseErrorMessage(updateResponse, 'Could not save your meal draft.'),
          );
          return;
        }
        const acceptResponse = await acceptMealProposal(proposalId, token);
        if (acceptResponse.ok) {
          onSaved('Meal added.');
        } else {
          setError(
            await getResponseErrorMessage(acceptResponse, 'Could not add this meal to your diary.'),
          );
        }
        return;
      }
      const payload = {
        entry_date: entryDate,
        name: name.trim(),
        notes: notes.trim(),
        items: items.map(mealItemToProposalItem),
      };
      const response = meal
        ? await updateMeal(meal.id, payload, token)
        : await createMeal(payload, token);
      if (response.ok) {
        onSaved(meal ? 'Meal updated.' : 'Meal added.');
      } else {
        setError(await getResponseErrorMessage(response, 'Could not save this meal.'));
      }
    } catch (_error) {
      setError('Could not save this meal. Your draft is still here. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const isEstimateStep = launchMode === 'estimate' && !meal && !proposalId;
  const mealHeader = isEstimateStep
    ? {
        eyebrow: null,
        title: 'Map it with AI',
        description: 'Tell us what you ate and we’ll create a meal estimate for you to fine tune.',
      }
    : meal
      ? {
          title: 'Edit meal',
          description: 'Update the meal details, catalog foods, and quantities in one place.',
        }
      : proposalContext
        ? {
            eyebrow: 'Review estimate',
            title: 'Map Your Meal',
            description: 'Your estimate is ready. Adjust anything you need before saving.',
          }
        : {
            eyebrow: null,
            title: 'Map Your Meal',
            description:
              'Chart today’s journey with catalog foods, personal foods, or AI guidance.',
          };
  const MealHeaderIcon =
    isEstimateStep || proposalContext ? AutoAwesomeIcon : RestaurantMenuOutlinedIcon;

  return (
    <>
      <Dialog
        open={open}
        onClose={estimating || saving || adjustmentBusy ? undefined : requestClose}
        fullWidth
        maxWidth="md"
        aria-labelledby="map-your-meal-header-title"
        aria-describedby="map-your-meal-description"
        sx={{
          '& .MuiDialog-paper': {
            m: { xs: 0, sm: 2 },
            width: { xs: '100%', sm: 'calc(100% - 32px)' },
            height: { xs: '100%', sm: 'auto' },
            maxHeight: { xs: '100%', sm: 'calc(100% - 32px)' },
            borderRadius: { xs: 0, sm: mealBuilderSurfaceRadius },
            bgcolor: 'var(--atlas-paper)',
            border: '1px solid var(--atlas-border-strong)',
            boxShadow: '0 24px 64px rgba(23, 50, 77, 0.16)',
          },
        }}
      >
        <DialogTitle
          component="div"
          sx={{
            bgcolor: meal ? 'var(--atlas-mineral-soft)' : 'var(--atlas-persimmon-soft)',
            color: 'var(--atlas-ink)',
            borderBottom: '1px solid var(--atlas-border)',
            px: { xs: 2, sm: 3 },
            py: { xs: 2, sm: 2.5 },
          }}
        >
          <Stack
            direction="row"
            spacing={1.5}
            sx={{
              alignItems: 'center',
            }}
          >
            <MealHeaderIcon
              sx={{
                flex: '0 0 auto',
                fontSize: { xs: 48, sm: 52 },
                color: meal ? 'var(--atlas-mineral)' : 'var(--atlas-persimmon-dark)',
              }}
            />
            <Box sx={{ minWidth: 0 }}>
              {mealHeader.eyebrow && (
                <Typography
                  component="p"
                  variant="overline"
                  sx={{ color: 'var(--atlas-ink-muted)', fontWeight: 800, lineHeight: 1.2 }}
                >
                  {mealHeader.eyebrow}
                </Typography>
              )}
              <Typography
                id="map-your-meal-header-title"
                component="h2"
                variant="h5"
                sx={{ display: 'block', mt: mealHeader.eyebrow ? 0.25 : 0 }}
              >
                {mealHeader.title}
              </Typography>
              <Typography
                id="map-your-meal-description"
                component="p"
                variant="body2"
                sx={{ color: 'var(--atlas-ink-muted)', mt: 0.5, maxWidth: 620 }}
              >
                {mealHeader.description}
              </Typography>
            </Box>
          </Stack>
        </DialogTitle>
        <DialogContent
          sx={{
            bgcolor: 'var(--atlas-paper)',
            borderColor: 'transparent',
            px: { xs: 2, sm: 3 },
            pt: '0 !important',
            '& > .MuiStack-root': {
              mt: { xs: 2.5, sm: 3 },
            },
          }}
        >
          {isEstimateStep ? (
            <Stack spacing={2.5}>
              {error && <Alert severity="error">{error}</Alert>}
              <TextField
                label="Describe what you ate"
                value={estimateDescription}
                onChange={(event) => setEstimateDescription(event.target.value)}
                placeholder={estimatePlaceholder}
                multiline
                minRows={3}
                autoFocus
              />
              <Typography variant="body2" sx={{ color: 'var(--atlas-ink-muted)' }}>
                MacroMapper checks your visible food catalog first. Matched foods use their existing
                nutrition data, while unmatched foods are estimated by GPT with web sources and
                remain editable before saving.
              </Typography>
              {estimating && (
                <Typography role="status" variant="body2" sx={{ color: 'var(--atlas-ink-muted)' }}>
                  Estimation can take up to two minutes. Keep this dialog open while we check
                  sources.
                </Typography>
              )}
            </Stack>
          ) : (
            <Stack spacing={1.25}>
              {error && <Alert severity="error">{error}</Alert>}
              {proposalContext && (
                <Stack
                  direction="row"
                  spacing={0.75}
                  useFlexGap
                  sx={{
                    flexWrap: 'wrap',
                  }}
                >
                  {proposalContext.provider_name && (
                    <Chip size="small" label={proposalContext.provider_name} variant="outlined" />
                  )}
                  <Chip size="small" label="AI Estimate" color="secondary" variant="outlined" />
                  {proposalContext.confidence_score != null && (
                    <Chip
                      size="small"
                      label={`${Math.round(Number(proposalContext.confidence_score) * 100)}% Confidence`}
                      variant="outlined"
                    />
                  )}
                </Stack>
              )}

              <Paper
                component="section"
                aria-labelledby="meal-identity-heading"
                elevation={0}
                sx={{
                  order: 1,
                  p: { xs: 1.5, sm: 2 },
                  border: '1px solid var(--atlas-border)',
                }}
              >
                <Typography id="meal-identity-heading" component="h3" variant="h6">
                  Meal Details
                </Typography>
                <Stack spacing={1.5} sx={{ mt: 1.5 }}>
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                    <TextField
                      label="Meal name"
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      helperText={
                        meal || proposalId
                          ? 'A name is required when updating an existing meal or proposal.'
                          : 'Optional. Leave blank to generate a name when you save.'
                      }
                      required={Boolean(meal || proposalId)}
                      fullWidth
                    />
                    <TextField
                      label="Date"
                      type="date"
                      value={entryDate}
                      onChange={(event) => setEntryDate(event.target.value)}
                      slotProps={{ inputLabel: { shrink: true } }}
                      required
                      sx={{ minWidth: { sm: 180 } }}
                    />
                  </Stack>
                  <TextField
                    label="Notes (optional)"
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                    multiline
                    minRows={2}
                    helperText="Add preparation details or context you want saved with this meal."
                  />
                </Stack>
              </Paper>

              <FoodCatalogPicker
                open={open}
                token={token}
                mealItems={items}
                focusSearchOnOpen={!meal && launchMode === 'add'}
                onAddFood={addFood}
              />

              <Paper
                component="section"
                aria-labelledby="meal-items-heading"
                elevation={0}
                sx={{
                  order: 3,
                  p: { xs: 1.5, sm: 2 },
                  border: '1px solid var(--atlas-border-strong)',
                }}
              >
                <Stack
                  direction="row"
                  sx={{
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 1,
                  }}
                >
                  <Box>
                    <Typography id="meal-items-heading" component="h3" variant="h6">
                      Meal Items
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        color: 'text.secondary',
                      }}
                    >
                      Adjust quantities, units, nutrition, and components, or review each item’s
                      estimate details and sources.
                    </Typography>
                  </Box>
                  <Chip
                    size="small"
                    label={`${items.length} ${items.length === 1 ? 'item' : 'items'}`}
                    color={items.length ? 'success' : 'default'}
                    variant="outlined"
                  />
                </Stack>
                {!items.length ? (
                  <Box
                    sx={{
                      mt: 1.5,
                      p: 2.5,
                      textAlign: 'center',
                      bgcolor: 'var(--atlas-bone)',
                      border: '1px dashed var(--atlas-border-strong)',
                      borderRadius: 'var(--atlas-radius-surface)',
                    }}
                  >
                    <RestaurantMenuOutlinedIcon sx={{ color: 'var(--atlas-mineral-dark)' }} />
                    <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
                      No meal items yet
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        color: 'text.secondary',
                      }}
                    >
                      Choose a recent or searched catalog food below, or use AI Adjustments to get
                      started.
                    </Typography>
                  </Box>
                ) : (
                  <Stack spacing={1.5} sx={{ mt: 1.5 }} aria-label="Selected meal items">
                    {items.map((item) => (
                      <MealItemEditorRow
                        key={item.key}
                        item={item}
                        onServings={changeServings}
                        onPortionChange={changePortion}
                        onNutrientChange={changeNutrient}
                        onRemove={removeItem}
                        allowNutritionEditing
                        allowComponentEditing
                        renderNutrition={(foodItem, onChange) => (
                          <ItemNutritionCards item={foodItem} compact onNutrientChange={onChange} />
                        )}
                      />
                    ))}
                  </Stack>
                )}
              </Paper>

              <Box sx={{ order: 2 }}>
                <MealNutritionSummary items={items} />
              </Box>

              <Paper
                component="section"
                aria-labelledby="ai-adjustments-heading"
                elevation={0}
                sx={{ order: 6, p: 1.25, border: '1px solid var(--atlas-border)' }}
              >
                <Stack spacing={0.75}>
                  <Stack
                    direction="row"
                    spacing={0.75}
                    sx={{
                      alignItems: 'center',
                    }}
                  >
                    <AutoAwesomeIcon
                      fontSize="small"
                      sx={{ color: 'var(--atlas-persimmon-dark)' }}
                    />
                    <Typography
                      id="ai-adjustments-heading"
                      variant="subtitle2"
                      sx={{ fontWeight: 800 }}
                    >
                      AI Adjustments
                    </Typography>
                  </Stack>
                  <Stack
                    direction={{ xs: 'column', sm: 'row' }}
                    spacing={0.75}
                    sx={{
                      alignItems: { sm: 'flex-end' },
                    }}
                  >
                    <TextField
                      label="Describe an AI adjustment"
                      value={adjustment}
                      onChange={(event) => {
                        setAdjustment(event.target.value);
                        setAdjustmentFeedback(null);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                          event.preventDefault();
                          applyAdjustment();
                        }
                      }}
                      placeholder="Add a medium chocolate milkshake"
                      multiline
                      minRows={1}
                      maxRows={3}
                      size="small"
                      slotProps={{ htmlInput: { maxLength: 500 } }}
                      disabled={adjustmentBusy}
                      fullWidth
                    />
                    <Button
                      variant="outlined"
                      color="secondary"
                      startIcon={
                        adjustmentBusy ? (
                          <CircularProgress size={16} color="inherit" />
                        ) : (
                          <SendIcon />
                        )
                      }
                      onClick={applyAdjustment}
                      disabled={adjustmentBusy || !adjustment.trim()}
                      sx={{ whiteSpace: 'nowrap', width: { xs: '100%', sm: 'auto' } }}
                    >
                      {adjustmentBusy ? 'Adjusting…' : 'Apply adjustment'}
                    </Button>
                  </Stack>
                  {adjustmentFeedback && (
                    <Alert severity={adjustmentFeedback.severity} sx={{ py: 0 }}>
                      {adjustmentFeedback.message}
                    </Alert>
                  )}
                </Stack>
              </Paper>
            </Stack>
          )}
        </DialogContent>
        <DialogActions
          sx={{
            bgcolor: 'var(--atlas-paper)',
            borderTop: '1px solid var(--atlas-border)',
            px: { xs: 1.5, sm: 3 },
            py: 1.25,
          }}
        >
          {isEstimateStep ? (
            <>
              <Button onClick={requestClose} disabled={estimating}>
                Cancel
              </Button>
              <Button
                variant="contained"
                color="secondary"
                onClick={createEstimate}
                disabled={estimating}
              >
                {estimating ? 'Estimating…' : 'Create estimate'}
              </Button>
            </>
          ) : (
            <>
              <Button onClick={requestClose} disabled={saving || adjustmentBusy}>
                Cancel
              </Button>
              <Button variant="contained" onClick={save} disabled={saving || adjustmentBusy}>
                {saving ? 'Saving…' : meal ? 'Save changes' : 'Save meal'}
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>
      <Dialog
        open={discardOpen}
        onClose={() => setDiscardOpen(false)}
        aria-labelledby="discard-meal-title"
      >
        <DialogTitle id="discard-meal-title">Discard meal changes?</DialogTitle>
        <DialogContent>
          <Typography>Your meal draft will be lost if you close the builder.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDiscardOpen(false)}>Keep editing</Button>
          <Button
            color="secondary"
            onClick={() => {
              setDiscardOpen(false);
              onClose();
            }}
          >
            Discard changes
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
