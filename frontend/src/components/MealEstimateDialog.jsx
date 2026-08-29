import AddIcon from '@mui/icons-material/Add';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SearchIcon from '@mui/icons-material/Search';
import SendIcon from '@mui/icons-material/Send';
import {
  Alert,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useEffect, useState } from 'react';
import MealItemEditorRow from './MealItemEditorRow';
import { catalogFoodToProposalItem } from './mealItemAdapters';
import {
  changeMealItemNutrient,
  changeMealItemPortion,
  changeMealItemServings,
  removeMealItemFromTree,
} from './mealItemTree';
import MealNutritionSummary from './nutrition/MealNutritionSummary';
import { ItemNutritionCards } from './nutrition/NutritionCards';
import {
  acceptMealProposal,
  createMealProposal,
  followUpMealProposal,
  searchFoods,
  updateMealProposal,
} from '../services/mealApiClient';

async function responseError(response, fallback) {
  try {
    const body = await response.json();
    if (typeof body.detail === 'string') return body.detail;
    const first = Object.values(body)[0];
    if (Array.isArray(first)) return first[0];
    if (typeof first === 'string') return first;
  } catch (_error) {
    // Use the stable fallback below.
  }
  return fallback;
}

export default function MealEstimateDialog({ date, open, token, onClose, onSaved }) {
  const [description, setDescription] = useState('');
  const [proposal, setProposal] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [foods, setFoods] = useState([]);
  const [searching, setSearching] = useState(false);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [followUp, setFollowUp] = useState('');
  const [followUpBusy, setFollowUpBusy] = useState(false);
  const [followUpFeedback, setFollowUpFeedback] = useState(null);

  useEffect(() => {
    if (!open) return;
    setDescription('');
    setProposal(null);
    setError('');
    setQuery('');
    setFoods([]);
    setCatalogOpen(false);
    setFollowUp('');
    setFollowUpBusy(false);
    setFollowUpFeedback(null);
  }, [open]);

  const estimate = async () => {
    if (!description.trim()) {
      setError('Describe the meal you want to estimate.');
      return;
    }
    setBusy(true);
    setError('');
    const response = await createMealProposal(
      { description: description.trim(), entry_date: date },
      token,
    );
    if (response.ok) {
      setProposal(await response.json());
    } else {
      setError(await responseError(response, 'Could not estimate this meal.'));
    }
    setBusy(false);
  };

  const runSearch = async () => {
    setSearching(true);
    setError('');
    const response = await searchFoods(query, token);
    if (response.ok) {
      setFoods(await response.json());
    } else {
      setError(await responseError(response, 'Could not search the food catalog.'));
    }
    setSearching(false);
  };

  const save = async () => {
    if (!proposal.name.trim() || !proposal.items.length) {
      setError('Name the meal and keep at least one food before saving.');
      return;
    }
    setBusy(true);
    setError('');
    const updateResponse = await updateMealProposal(
      proposal.id,
      { name: proposal.name.trim(), items: proposal.items },
      token,
    );
    if (!updateResponse.ok) {
      setError(await responseError(updateResponse, 'Could not save your proposal edits.'));
      setBusy(false);
      return;
    }
    const acceptResponse = await acceptMealProposal(proposal.id, token);
    if (acceptResponse.ok) {
      onSaved('Estimated meal added to your diary.');
    } else {
      setError(await responseError(acceptResponse, 'Could not add this estimate to your diary.'));
    }
    setBusy(false);
  };

  const changeServings = (key, amount, item) => {
    setProposal((current) => ({
      ...current,
      items: changeMealItemServings(current.items, key, amount, item),
    }));
  };

  const changePortion = (key, selectedPortionKey) => {
    setProposal((current) => ({
      ...current,
      items: changeMealItemPortion(current.items, key, selectedPortionKey),
    }));
  };

  const changeNutrient = (key, nutrient, totalValue) => {
    setProposal((current) => ({
      ...current,
      items: changeMealItemNutrient(current.items, key, nutrient, totalValue),
    }));
  };

  const removeItem = (key) => {
    setProposal((current) => ({
      ...current,
      items: removeMealItemFromTree(current.items, key),
    }));
  };

  const applyFollowUp = async () => {
    const request = followUp.trim();
    if (!request) {
      setFollowUpFeedback({
        severity: 'warning',
        message: 'Describe what you want to add, remove, or correct.',
      });
      return;
    }
    if (!proposal.name.trim() || !proposal.items.length) {
      setFollowUpFeedback({
        severity: 'warning',
        message: 'Name the meal and keep at least one food before asking for a change.',
      });
      return;
    }

    setFollowUpBusy(true);
    setError('');
    setFollowUpFeedback(null);
    try {
      const response = await followUpMealProposal(
        proposal.id,
        {
          follow_up: request,
          name: proposal.name.trim(),
          items: proposal.items,
        },
        token,
      );
      if (response.ok) {
        const result = await response.json();
        if (result.applied) {
          setProposal(result.proposal);
          setFollowUp('');
          setFollowUpFeedback({ severity: 'success', message: result.message });
        } else {
          setFollowUpFeedback({ severity: 'warning', message: result.message });
        }
      } else {
        setFollowUpFeedback({
          severity: 'error',
          message: await responseError(
            response,
            'Could not apply that change. Your current draft is still here.',
          ),
        });
      }
    } catch (_error) {
      setFollowUpFeedback({
        severity: 'error',
        message: 'Could not reach AI. Try again—your current draft and request are still here.',
      });
    } finally {
      setFollowUpBusy(false);
    }
  };

  const dialogBusy = busy || followUpBusy;

  return (
    <Dialog
      open={open}
      onClose={dialogBusy ? undefined : onClose}
      fullWidth
      maxWidth="md"
      sx={{
        '& .MuiDialog-paper': {
          bgcolor: 'var(--atlas-paper)',
          border: '1px solid var(--atlas-border-strong)',
        },
      }}
    >
      <DialogTitle sx={{ bgcolor: 'var(--atlas-persimmon-soft)' }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <AutoAwesomeIcon sx={{ color: 'var(--atlas-persimmon-dark)' }} />
          <span>{proposal ? 'Review meal estimate' : 'Estimate a meal'}</span>
        </Stack>
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={proposal ? 1.25 : 2.5}>
          {error && <Alert severity="error">{error}</Alert>}
          <Alert severity="info" variant="outlined">
            Nutrition values are estimates and may vary. Review and adjust each item before saving.
          </Alert>
          {!proposal ? (
            <>
              <TextField
                label="Describe what you ate"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Double-Double from In-N-Out, no cheese"
                multiline
                minRows={3}
                autoFocus
              />
              <Typography variant="body2" sx={{ color: 'var(--atlas-ink-muted)' }}>
                MacroMapper searches your visible food catalog first. When there is no suitable
                match, GPT prepares a sourced, editable proposal.
              </Typography>
            </>
          ) : (
            <>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                <TextField
                  label="Meal name"
                  value={proposal.name}
                  onChange={(event) =>
                    setProposal((current) => ({ ...current, name: event.target.value }))
                  }
                  fullWidth
                />
                <TextField label="Date" value={date} disabled sx={{ minWidth: 170 }} />
              </Stack>
              <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                <Chip label={`Generated by ${proposal.provider_name}`} variant="outlined" />
                {proposal.provider_model && (
                  <Chip label={`Model ${proposal.provider_model}`} variant="outlined" />
                )}
                {proposal.confidence_score != null && (
                  <Chip
                    label={`${Math.round(Number(proposal.confidence_score) * 100)}% overall confidence`}
                    variant="outlined"
                  />
                )}
              </Stack>
              <MealNutritionSummary items={proposal.items} />
              <Stack spacing={1.5}>
                {proposal.items.map((item) => (
                  <MealItemEditorRow
                    key={item.key}
                    item={item}
                    onServings={changeServings}
                    onPortionChange={changePortion}
                    onNutrientChange={changeNutrient}
                    onRemove={removeItem}
                    renderNutrition={(foodItem, onChange) => (
                      <ItemNutritionCards item={foodItem} compact onNutrientChange={onChange} />
                    )}
                  />
                ))}
              </Stack>
              <Divider />
              <Paper elevation={0} sx={{ p: 1, border: '1px solid var(--atlas-border)' }}>
                <Stack
                  direction="row"
                  alignItems="center"
                  justifyContent="space-between"
                  spacing={1}
                >
                  <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
                    Add another food
                  </Typography>
                  <IconButton
                    size="small"
                    aria-label={`${catalogOpen ? 'Collapse' : 'Expand'} add another food`}
                    aria-expanded={catalogOpen}
                    onClick={() => setCatalogOpen((current) => !current)}
                  >
                    {catalogOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                  </IconButton>
                </Stack>
                <Collapse in={catalogOpen} unmountOnExit>
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    <TextField
                      label="Search catalog"
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      onKeyDown={(event) => event.key === 'Enter' && runSearch()}
                      fullWidth
                    />
                    <Button
                      aria-label="search proposal foods"
                      variant="outlined"
                      onClick={runSearch}
                    >
                      <SearchIcon />
                    </Button>
                  </Stack>
                  {searching ? (
                    <CircularProgress size={24} sx={{ mt: 2 }} />
                  ) : (
                    <List sx={{ maxHeight: 200, overflow: 'auto' }}>
                      {foods.map((food) => (
                        <ListItem
                          key={food.id}
                          secondaryAction={
                            <Button
                              startIcon={<AddIcon />}
                              onClick={() => {
                                setProposal((current) => ({
                                  ...current,
                                  items: [...current.items, catalogFoodToProposalItem(food)],
                                }));
                                setFoods((current) =>
                                  current.filter((item) => item.id !== food.id),
                                );
                              }}
                            >
                              Add
                            </Button>
                          }
                        >
                          <ListItemText
                            primary={food.name}
                            secondary={food.provider_name || food.scope}
                          />
                        </ListItem>
                      ))}
                    </List>
                  )}
                </Collapse>
              </Paper>
              <Paper elevation={0} sx={{ p: 1.25, border: '1px solid var(--atlas-border)' }}>
                <Stack spacing={0.75}>
                  <Stack direction="row" spacing={0.75} alignItems="center">
                    <AutoAwesomeIcon
                      fontSize="small"
                      sx={{ color: 'var(--atlas-persimmon-dark)' }}
                    />
                    <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
                      Adjust with AI
                    </Typography>
                  </Stack>
                  <Stack
                    direction={{ xs: 'column', sm: 'row' }}
                    spacing={0.75}
                    alignItems={{ sm: 'flex-end' }}
                  >
                    <TextField
                      label="Ask AI to make changes"
                      value={followUp}
                      onChange={(event) => {
                        setFollowUp(event.target.value);
                        setFollowUpFeedback(null);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                          event.preventDefault();
                          applyFollowUp();
                        }
                      }}
                      placeholder="I also had a medium chocolate milkshake"
                      multiline
                      minRows={1}
                      maxRows={3}
                      size="small"
                      inputProps={{ maxLength: 500 }}
                      disabled={followUpBusy}
                      fullWidth
                    />
                    <Button
                      variant="outlined"
                      color="secondary"
                      startIcon={
                        followUpBusy ? <CircularProgress size={16} color="inherit" /> : <SendIcon />
                      }
                      onClick={applyFollowUp}
                      disabled={followUpBusy || !followUp.trim()}
                      sx={{ whiteSpace: 'nowrap', width: { xs: '100%', sm: 'auto' } }}
                    >
                      {followUpBusy ? 'Applying…' : 'Apply'}
                    </Button>
                  </Stack>
                  {followUpFeedback && (
                    <Alert severity={followUpFeedback.severity} sx={{ py: 0 }}>
                      {followUpFeedback.message}
                    </Alert>
                  )}
                </Stack>
              </Paper>
            </>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={dialogBusy}>
          Cancel
        </Button>
        {!proposal ? (
          <Button variant="contained" color="secondary" onClick={estimate} disabled={dialogBusy}>
            {busy ? 'Estimating…' : 'Create estimate'}
          </Button>
        ) : (
          <Button variant="contained" onClick={save} disabled={dialogBusy}>
            {busy ? 'Saving…' : 'Save to diary'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
