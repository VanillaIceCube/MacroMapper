import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import InsightsIcon from '@mui/icons-material/Insights';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { Box, Chip, Container, Paper, Stack, Typography } from '@mui/material';

const principles = [
  {
    icon: <LockOutlinedIcon aria-hidden="true" />,
    title: 'Private by default',
    description: 'Your account and tracking history belong to you.',
    color: 'var(--atlas-forest)',
    background: 'var(--atlas-forest-soft)',
  },
  {
    icon: <AutoAwesomeIcon aria-hidden="true" />,
    title: 'Review every estimate',
    description: 'GPT-assisted meal proposals stay editable and source-aware before you save them.',
    color: 'var(--atlas-persimmon-dark)',
    background: 'var(--atlas-persimmon-soft)',
  },
  {
    icon: <InsightsIcon aria-hidden="true" />,
    title: 'Understand the whole day',
    description: 'Nutrition, goals, activity, and trends share one factual daily view.',
    color: 'var(--atlas-mineral-dark)',
    background: 'var(--atlas-mineral-soft)',
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
    <Box className="atlas-contours" sx={{ minHeight: 'calc(100vh - 65px)' }}>
      <Container maxWidth="lg" sx={{ py: { xs: 4, sm: 7 } }}>
        <Stack spacing={{ xs: 3, sm: 4 }}>
          <Box sx={{ maxWidth: 850 }}>
            <Chip
              label="Private nutrition workspace"
              variant="outlined"
              sx={{
                mb: 2.5,
                color: 'var(--atlas-forest-dark)',
                bgcolor: 'var(--atlas-forest-soft)',
                borderColor: 'rgba(46, 107, 79, 0.32)',
              }}
            />
            <Typography
              component="h1"
              variant="h3"
              sx={{
                fontWeight: 600,
                fontSize: { xs: '2.5rem', sm: '3.75rem' },
                lineHeight: 1.04,
                overflowWrap: 'anywhere',
              }}
            >
              Welcome to MacroMapper{username ? `, ${username}` : ''}
            </Typography>
            <Typography
              component="p"
              variant="h6"
              sx={{
                mt: 2,
                maxWidth: 760,
                color: 'var(--atlas-ink-muted)',
                fontSize: { xs: '1.05rem', sm: '1.2rem' },
                lineHeight: 1.65,
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
                elevation={0}
                sx={{
                  p: { xs: 2.5, sm: 3 },
                  bgcolor: 'var(--atlas-paper)',
                  color: 'var(--atlas-ink)',
                  border: '1px solid var(--atlas-border)',
                  boxShadow: '0 14px 36px rgba(23, 50, 77, 0.06)',
                }}
              >
                <Box
                  sx={{
                    display: 'grid',
                    placeItems: 'center',
                    width: 48,
                    height: 48,
                    mb: 2,
                    color: principle.color,
                    bgcolor: principle.background,
                    borderRadius: '50%',
                  }}
                >
                  {principle.icon}
                </Box>
                <Typography component="h2" variant="h5">
                  {principle.title}
                </Typography>
                <Typography sx={{ mt: 1, color: 'var(--atlas-ink-muted)', lineHeight: 1.6 }}>
                  {principle.description}
                </Typography>
              </Paper>
            ))}
          </Box>

          <Paper
            elevation={0}
            sx={{
              p: { xs: 2.5, sm: 3.5 },
              bgcolor: 'var(--atlas-mineral-soft)',
              color: 'var(--atlas-ink)',
              border: '1px solid rgba(71, 121, 138, 0.28)',
            }}
          >
            <Typography component="h2" variant="h5">
              Your account is ready
            </Typography>
            <Typography
              sx={{ mt: 1, maxWidth: 880, color: 'var(--atlas-ink-muted)', lineHeight: 1.6 }}
            >
              Secure sign-in, password recovery, session renewal, and in-app notifications are
              active, and your private meal diary is ready. Activity, goal, GPT-estimation, and
              trend tracking will arrive through the published MacroMapper roadmap.
            </Typography>
          </Paper>
        </Stack>
      </Container>
    </Box>
  );
}
