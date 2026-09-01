import { Box, Paper, Stack, Typography } from '@mui/material';

export default function AuthPageShell({ children, title }) {
  return (
    <Stack
      className="atlas-contours"
      spacing={2}
      sx={{
        alignItems: 'center',
        px: { xs: 2, sm: 4 },
        py: { xs: 4, sm: 6 },
        justifyContent: 'center',
        minHeight: '100vh',
      }}
    >
      <Stack spacing={1} sx={{ alignItems: 'center' }}>
        <Box component="img" src="/macromapper-mark.png" alt="" sx={{ width: 64, height: 64 }} />
        <Typography variant="h3" sx={{ fontWeight: 650, color: 'var(--atlas-ink)' }}>
          MacroMapper
        </Typography>
        <Typography
          variant="overline"
          sx={{ color: 'var(--atlas-forest-dark)', textAlign: 'center' }}
        >
          Nutrition mapped clearly
        </Typography>
      </Stack>
      <Paper
        elevation={0}
        sx={{
          p: { xs: 3, sm: 4 },
          pb: { xs: 3, sm: 4 },
          width: '100%',
          maxWidth: 520,
          background: 'var(--atlas-paper)',
          border: '1px solid var(--atlas-border-strong)',
          boxShadow: '0 24px 70px rgba(23, 50, 77, 0.1)',
        }}
      >
        <Typography component="h1" variant="h4" sx={{ mb: 1, color: 'var(--atlas-ink)' }}>
          {title}
        </Typography>
        <Typography sx={{ mb: 3, color: 'var(--atlas-ink-muted)' }}>
          Your private nutrition workspace is one step away.
        </Typography>
        <Box>{children}</Box>
      </Paper>
    </Stack>
  );
}
