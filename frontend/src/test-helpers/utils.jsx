import { render } from '@testing-library/react';
import CssBaseline from '@mui/material/CssBaseline';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { MemoryRouter } from 'react-router';
import appTheme from '../theme';

// Shared test setup: apply Field Atlas and disable MUI ripples to avoid act warnings.
const testTheme = createTheme(appTheme, {
  components: {
    MuiButtonBase: {
      defaultProps: {
        disableRipple: true,
      },
    },
  },
});

export function renderWithProviders(ui, { routeEntries = ['/'], ...renderOptions } = {}) {
  return render(
    <ThemeProvider theme={testTheme}>
      <CssBaseline />
      <MemoryRouter initialEntries={routeEntries}>{ui}</MemoryRouter>
    </ThemeProvider>,
    renderOptions,
  );
}
