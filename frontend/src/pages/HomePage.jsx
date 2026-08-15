import { Container, Paper, Typography } from '@mui/material';

export default function HomePage() {
  return (
    <Container maxWidth="md" sx={{ py: { xs: 3, sm: 6 } }}>
      <Paper
        elevation={3}
        sx={{
          p: { xs: 3, sm: 5 },
          backgroundColor: 'var(--secondary-background-color)',
          color: 'var(--secondary-color)',
          border: '2.5px solid var(--background-color)',
        }}
      >
        <Typography sx={{ color: 'var(--secondary-color)' }}>
          Lorem ipsum dolor sit amet, consectetur adipiscing elit. This protected page is ready for
          your application.
        </Typography>
      </Paper>
    </Container>
  );
}
