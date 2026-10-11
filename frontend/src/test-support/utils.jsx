import { render } from '@testing-library/react';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { MemoryRouter } from 'react-router';
import fieldAtlasTheme from '../theme';

// Shared test setup: apply Field Atlas and disable MUI ripples to avoid act warnings.
const testTheme = createTheme(fieldAtlasTheme, {
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
      <MemoryRouter initialEntries={routeEntries}>{ui}</MemoryRouter>
    </ThemeProvider>,
    renderOptions,
  );
}
