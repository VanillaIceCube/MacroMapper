import { Box, Container, Paper, Typography } from '@mui/material';

export default function HomePage() {
  return (
    <Container maxWidth="md">
      <Box sx={{ minHeight: 'calc(100vh - 64px)', display: 'grid', placeItems: 'center', py: 4 }}>
        <Paper
          elevation={3}
          sx={{
            width: '100%',
            p: { xs: 4, sm: 7 },
            textAlign: 'center',
            background: 'var(--secondary-background-color)',
          }}
        >
          <Typography component="h1" variant="h2" sx={{ color: 'var(--secondary-color)' }}>
            Hello World
          </Typography>
        </Paper>
      </Box>
    </Container>
  );
}
