import { Box, Paper, Stack, Typography } from '@mui/material';

export default function AuthPageShell({ children, title }) {
  return (
    <Stack
      spacing={2}
      alignItems="center"
      maxWidth="sm"
      sx={{
        p: { xs: 3, sm: 5.5 },
        mx: 'auto',
        justifyContent: 'center',
        minHeight: '85vh',
      }}
    >
      <Typography variant="h3" sx={{ mt: 2, fontWeight: 'bold', color: 'white' }}>
        FullStackTemplate
      </Typography>
      <Paper
        elevation={3}
        sx={{
          p: { xs: 3, sm: 4 },
          pb: 2,
          width: '100%',
          background: 'var(--secondary-background-color)',
        }}
      >
        <Typography component="h1" variant="h5" sx={{ mb: 2, color: 'var(--secondary-color)' }}>
          {title}
        </Typography>
        <Box>{children}</Box>
      </Paper>
    </Stack>
  );
}
