import fs from 'node:fs';
import path from 'node:path';

describe('MacroMapper theme styles', () => {
  const sourceRoot = path.resolve(process.cwd(), 'src');
  const appCss = fs.readFileSync(path.join(sourceRoot, 'App.css'), 'utf8');
  const themeSource = fs.readFileSync(path.join(sourceRoot, 'theme.js'), 'utf8');
  const readSource = (relativePath) => fs.readFileSync(path.join(sourceRoot, relativePath), 'utf8');

  test('defines the Field Atlas core and semantic tokens centrally', () => {
    expect(appCss).toContain('--atlas-bone: #f6f1e7');
    expect(appCss).toContain('--atlas-ink: #17324d');
    expect(appCss).toContain('--atlas-forest: #2e6b4f');
    expect(appCss).toContain('--atlas-persimmon: #e46b3c');
    expect(appCss).toContain('--atlas-mineral: #a9cad4');
    expect(appCss).toContain('--calorie-color: var(--atlas-ink)');
    expect(appCss).toContain('--protein-color: var(--atlas-forest)');
    expect(appCss).toContain('--carbohydrate-color: var(--atlas-mineral-dark)');
    expect(appCss).toContain('--fat-color: var(--atlas-persimmon)');
    expect(appCss).toContain('--activity-color: #356b7f');
  });

  test('configures the Material UI theme with Field Atlas typography and palette', () => {
    expect(themeSource).toContain("bone: '#F6F1E7'");
    expect(themeSource).toContain("ink: '#17324D'");
    expect(themeSource).toContain("forest: '#2E6B4F'");
    expect(themeSource).toContain("persimmon: '#E46B3C'");
    expect(themeSource).toContain("mineral: '#A9CAD4'");
    expect(themeSource).toContain('"Newsreader"');
    expect(themeSource).toContain('"Inter"');
    expect(themeSource).toContain("textTransform: 'none'");
  });

  test('uses Forest for focused form controls', () => {
    expect(appCss).toContain('.MuiInputLabel-root.Mui-focused');
    expect(appCss).toContain('.MuiOutlinedInput-root.Mui-focused .MuiOutlinedInput-notchedOutline');
    expect(appCss).toContain('color: var(--atlas-forest-dark) !important');
    expect(appCss).toContain('border-color: var(--atlas-forest) !important');
  });

  test.each([
    'components/AppHeader.jsx',
    'components/AppNavigationDrawer.jsx',
    'components/AuthPageShell.jsx',
    'pages/HomePage.jsx',
    'pages/DiaryPage.jsx',
  ])('%s uses shared Field Atlas surfaces', (relativePath) => {
    const source = readSource(relativePath);

    expect(source).toMatch(/var\(--atlas-(paper|bone|mineral-soft)\)/);
    expect(source).toContain('var(--atlas-ink)');
  });

  test.each([
    'pages/authentication/ForgotPassword.jsx',
    'pages/authentication/Login.jsx',
    'pages/authentication/Register.jsx',
    'pages/authentication/ResetPassword.jsx',
  ])('%s uses shared Field Atlas form and link treatments', (relativePath) => {
    const source = readSource(relativePath);

    expect(source).toContain('variant="contained"');
    expect(source).toContain('var(--atlas-ink-muted)');
  });

  test('uses an explicit non-color navigation state treatment', () => {
    const drawerSource = readSource('components/AppNavigationDrawer.jsx');

    expect(drawerSource).toContain('var(--atlas-forest-soft)');
    expect(drawerSource).toContain("'1px solid rgba(46, 107, 79, 0.2)'");
  });

  test('uses semantic nutrition colors and numeric typography in the meal diary', () => {
    const diarySource = readSource('pages/DiaryPage.jsx');

    expect(diarySource).toContain('var(--calorie-color)');
    expect(diarySource).toContain('var(--protein-color)');
    expect(diarySource).toContain('var(--carbohydrate-color)');
    expect(diarySource).toContain('var(--fat-color)');
    expect(diarySource).toContain('className="numeric-data"');
    expect(diarySource).not.toContain('var(--secondary-background-color)');
    expect(diarySource).not.toContain('var(--secondary-color)');
  });

  test('provides focus and reduced-motion safeguards', () => {
    expect(appCss).toContain('.auth-link:focus-visible');
    expect(appCss).toContain('@media (prefers-reduced-motion: reduce)');
  });
});
