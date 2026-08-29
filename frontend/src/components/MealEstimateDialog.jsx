import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useEffect, useState } from 'react';
import { createMealProposal } from '../services/mealApiClient';

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

export default function MealEstimateDialog({ date, open, token, onClose, onEstimated }) {
  const [description, setDescription] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setDescription('');
    setBusy(false);
    setError('');
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
      onEstimated(await response.json());
    } else {
      setError(await responseError(response, 'Could not estimate this meal.'));
    }
    setBusy(false);
  };

  return (
    <Dialog
      open={open}
      onClose={busy ? undefined : onClose}
      fullWidth
      maxWidth="md"
      aria-labelledby="estimate-meal-prompt-title"
      sx={{
        '& .MuiDialog-paper': {
          bgcolor: 'var(--atlas-paper)',
          border: '1px solid var(--atlas-border-strong)',
        },
      }}
    >
      <DialogTitle id="estimate-meal-prompt-title" sx={{ bgcolor: 'var(--atlas-persimmon-soft)' }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <AutoAwesomeIcon sx={{ color: 'var(--atlas-persimmon-dark)' }} />
          <span>Estimate a meal</span>
        </Stack>
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2.5}>
          {error && <Alert severity="error">{error}</Alert>}
          <Alert severity="info" variant="outlined">
            Nutrition values are estimates and may vary. Review and adjust each item before saving.
          </Alert>
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
            MacroMapper searches your visible food catalog first. When there is no suitable match,
            GPT prepares a sourced, editable proposal.
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>
          Cancel
        </Button>
        <Button variant="contained" color="secondary" onClick={estimate} disabled={busy}>
          {busy ? 'Estimating…' : 'Create estimate'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
