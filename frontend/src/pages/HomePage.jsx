import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import InsightsIcon from '@mui/icons-material/Insights';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { Box, Chip, Container, Paper, Stack, Typography } from '@mui/material';

const principles = [
  {
    icon: <LockOutlinedIcon aria-hidden="true" />,
    title: 'Private by default',
    description: 'Your account and tracking history belong to you.',
  },
  {
    icon: <AutoAwesomeIcon aria-hidden="true" />,
    title: 'Review every estimate',
    description: 'GPT-assisted meal proposals stay editable and source-aware before you save them.',
  },
  {
    icon: <InsightsIcon aria-hidden="true" />,
    title: 'Understand the whole day',
    description: 'Nutrition, goals, activity, and trends share one factual daily view.',
  },
];

function getUsername() {
  try {
    return sessionStorage.getItem('username') || '';
  } catch (_error) {
    return '';
  }
}

export default function HomePage() {
  const username = getUsername();

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, sm: 5 } }}>
      <Stack spacing={3}>
        <Box>
          <Chip
            label="Private nutrition workspace"
            sx={{ mb: 2, bgcolor: 'var(--primary-color)', fontWeight: 'bold' }}
          />
          <Typography
            component="h1"
            variant="h3"
            sx={{
              fontWeight: 800,
              fontSize: { xs: '2.25rem', sm: '3rem' },
              overflowWrap: 'anywhere',
            }}
          >
            Welcome to MacroMapper{username ? `, ${username}` : ''}
          </Typography>
          <Typography
            component="p"
            variant="h6"
            sx={{
              mt: 1,
              maxWidth: 760,
              color: 'var(--text-color)',
              fontSize: { xs: '1.05rem', sm: '1.25rem' },
            }}
          >
            Map what you eat, understand where the numbers came from, and keep the final say over
            every entry.
          </Typography>
        </Box>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' },
            gap: 2,
          }}
        >
          {principles.map((principle) => (
            <Paper
              key={principle.title}
              elevation={3}
              sx={{
                p: 3,
                bgcolor: 'var(--secondary-background-color)',
                color: 'var(--secondary-color)',
                border: '2.5px solid var(--background-color)',
              }}
            >
              <Box sx={{ color: 'var(--secondary-color)', mb: 1 }}>{principle.icon}</Box>
              <Typography component="h2" variant="h6" sx={{ fontWeight: 800 }}>
                {principle.title}
              </Typography>
              <Typography sx={{ mt: 1 }}>{principle.description}</Typography>
            </Paper>
          ))}
        </Box>

        <Paper
          elevation={0}
          sx={{
            p: { xs: 2.5, sm: 3 },
            bgcolor: 'transparent',
            color: 'var(--text-color)',
            border: '1px solid rgba(255, 255, 255, 0.35)',
          }}
        >
          <Typography component="h2" variant="h6" sx={{ fontWeight: 800 }}>
            Your account is ready
          </Typography>
          <Typography sx={{ mt: 1 }}>
            Secure sign-in, password recovery, session renewal, in-app notifications, and your
            private meal diary are active. Activity, goal, GPT-estimation, and trend tracking will
            arrive through the published MacroMapper roadmap.
          </Typography>
        </Paper>
      </Stack>
    </Container>
  );
}
