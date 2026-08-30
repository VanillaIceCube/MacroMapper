import '@testing-library/jest-dom';

vi.mock('@mui/material', async () => {
  const React = await import('react');
  const actual = await vi.importActual('@mui/material');
  return {
    ...actual,
    Menu: ({ open, children }) =>
      open ? React.createElement(actual.MenuList, { 'data-testid': 'menu' }, children) : null,
    TextField: ({ inputRef, InputProps, inputProps, ...props }) =>
      React.createElement(actual.TextField, {
        ...props,
        autoFocus: false,
        inputRef,
        InputProps,
        inputProps,
      }),
  };
});
