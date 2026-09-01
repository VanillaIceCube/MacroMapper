import fs from 'node:fs';
import path from 'node:path';
import { parse } from '@babel/parser';

const muiSystemComponents = new Set([
  'Box',
  'Stack',
  'Typography',
  'Link',
  'Grid',
  'Grid2',
  'DialogContentText',
  'TimelineContent',
  'TimelineOppositeContent',
]);

const removedSystemProps = new Set([
  'border',
  'borderTop',
  'borderRight',
  'borderBottom',
  'borderLeft',
  'borderColor',
  'borderTopColor',
  'borderRightColor',
  'borderBottomColor',
  'borderLeftColor',
  'outline',
  'outlineColor',
  'borderRadius',
  'color',
  'bgcolor',
  'backgroundColor',
  'p',
  'pt',
  'pr',
  'pb',
  'pl',
  'px',
  'py',
  'padding',
  'paddingTop',
  'paddingRight',
  'paddingBottom',
  'paddingLeft',
  'paddingX',
  'paddingY',
  'paddingInline',
  'paddingInlineStart',
  'paddingInlineEnd',
  'paddingBlock',
  'paddingBlockStart',
  'paddingBlockEnd',
  'm',
  'mt',
  'mr',
  'mb',
  'ml',
  'mx',
  'my',
  'margin',
  'marginTop',
  'marginRight',
  'marginBottom',
  'marginLeft',
  'marginX',
  'marginY',
  'marginInline',
  'marginInlineStart',
  'marginInlineEnd',
  'marginBlock',
  'marginBlockStart',
  'marginBlockEnd',
  'displayPrint',
  'display',
  'overflow',
  'textOverflow',
  'visibility',
  'whiteSpace',
  'flexBasis',
  'flexDirection',
  'flexWrap',
  'justifyContent',
  'alignItems',
  'alignContent',
  'order',
  'flex',
  'flexGrow',
  'flexShrink',
  'alignSelf',
  'justifyItems',
  'justifySelf',
  'gap',
  'rowGap',
  'columnGap',
  'gridColumn',
  'gridRow',
  'gridAutoFlow',
  'gridAutoColumns',
  'gridAutoRows',
  'gridTemplateColumns',
  'gridTemplateRows',
  'gridTemplateAreas',
  'gridArea',
  'position',
  'zIndex',
  'top',
  'right',
  'bottom',
  'left',
  'boxShadow',
  'width',
  'maxWidth',
  'minWidth',
  'height',
  'maxHeight',
  'minHeight',
  'boxSizing',
  'font',
  'fontFamily',
  'fontSize',
  'fontStyle',
  'fontWeight',
  'letterSpacing',
  'textTransform',
  'lineHeight',
  'textAlign',
  'typography',
]);

const typographyComponents = new Set([
  'Typography',
  'DialogContentText',
  'TimelineContent',
  'TimelineOppositeContent',
]);

function visitAst(node, visitor) {
  if (!node || typeof node !== 'object') return;
  if (Array.isArray(node)) {
    node.forEach((child) => visitAst(child, visitor));
    return;
  }

  visitor(node);
  Object.entries(node).forEach(([key, child]) => {
    if (!['loc', 'start', 'end'].includes(key)) visitAst(child, visitor);
  });
}

function staticAttributeValue(attribute) {
  if (attribute.value?.type === 'StringLiteral') return attribute.value.value;
  if (attribute.value?.type === 'JSXExpressionContainer') {
    const expression = attribute.value.expression;
    if (expression?.type === 'StringLiteral') return expression.value;
  }
  return undefined;
}

function isRemovedColorProp(component, attribute) {
  const value = staticAttributeValue(attribute);
  if (typeof value !== 'string') return false;
  const isSystemColor =
    value === 'divider' ||
    value === 'inherit' ||
    value.includes('.') ||
    value.startsWith('#') ||
    /\(.*\)/.test(value);

  if (typographyComponents.has(component)) return isSystemColor;
  if (component === 'Link') return isSystemColor && value !== 'inherit';
  return true;
}

function removedMuiSystemPropOffenders(source, relativePath) {
  const ast = parse(source, { sourceType: 'module', plugins: ['jsx'] });
  const importedComponents = new Map();
  const offenders = [];

  visitAst(ast.program, (node) => {
    if (node.type !== 'ImportDeclaration' || !node.source.value.startsWith('@mui')) return;

    node.specifiers.forEach((specifier) => {
      if (
        specifier.type === 'ImportSpecifier' &&
        muiSystemComponents.has(specifier.imported.name)
      ) {
        importedComponents.set(specifier.local.name, specifier.imported.name);
      }
      if (specifier.type === 'ImportDefaultSpecifier') {
        const importedName = node.source.value.split('/').at(-1);
        if (muiSystemComponents.has(importedName)) {
          importedComponents.set(specifier.local.name, importedName);
        }
      }
    });
  });

  visitAst(ast.program, (node) => {
    if (node.type !== 'JSXOpeningElement' || node.name.type !== 'JSXIdentifier') return;
    const component = importedComponents.get(node.name.name);
    if (!component) return;

    node.attributes.forEach((attribute) => {
      if (attribute.type !== 'JSXAttribute' || attribute.name.type !== 'JSXIdentifier') return;
      const prop = attribute.name.name;
      if (!removedSystemProps.has(prop)) return;
      if (prop === 'color' && !isRemovedColorProp(component, attribute)) return;
      offenders.push(`${relativePath}:${node.loc.start.line}:${node.name.name}.${prop}`);
    });
  });

  return offenders;
}

describe('MacroMapper theme styles', () => {
  const sourceRoot = path.resolve(process.cwd(), 'src');
  const appCss = fs.readFileSync(path.join(sourceRoot, 'App.css'), 'utf8');
  const themeSource = fs.readFileSync(path.join(sourceRoot, 'theme.js'), 'utf8');
  const readSource = (relativePath) => fs.readFileSync(path.join(sourceRoot, relativePath), 'utf8');
  const jsxFiles = fs
    .readdirSync(sourceRoot, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.jsx'))
    .map((entry) => path.join(entry.parentPath, entry.name));

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
    const nutritionDefinitions = readSource('components/nutrition/nutritionDefinitions.js');

    expect(diarySource).toContain('var(--calorie-color)');
    expect(nutritionDefinitions).toContain('var(--protein-color)');
    expect(nutritionDefinitions).toContain('var(--carbohydrate-color)');
    expect(nutritionDefinitions).toContain('var(--fat-color)');
    expect(diarySource).toContain('className="numeric-data"');
    expect(diarySource).not.toContain('var(--secondary-background-color)');
    expect(diarySource).not.toContain('var(--secondary-color)');
  });

  test('provides focus and reduced-motion safeguards', () => {
    expect(appCss).toContain('.auth-link:focus-visible');
    expect(appCss).toContain('@media (prefers-reduced-motion: reduce)');
  });

  test('keeps removed Material UI 9 system props inside sx', () => {
    const offenders = jsxFiles.flatMap((filePath) => {
      const source = fs.readFileSync(filePath, 'utf8');
      const relativePath = path.relative(sourceRoot, filePath);
      return removedMuiSystemPropOffenders(source, relativePath);
    });

    expect(offenders).toEqual([]);
  });

  test('detects the complete removed prop set only on imported MUI system components', () => {
    const source = `
      import { Box as LayoutBox, Skeleton, Typography as Text } from '@mui/material';
      export default function Example() {
        return <><LayoutBox mt={1} display="flex" /><Skeleton width={20} /><Text color="text.secondary" /><Text color="primary" /></>;
      }
    `;
    const offenderProps = removedMuiSystemPropOffenders(source, 'fixture.jsx').map((offender) =>
      offender.split(':').at(-1),
    );

    expect(offenderProps).toEqual(['LayoutBox.mt', 'LayoutBox.display', 'Text.color']);
  });

  test('uses Material UI slotProps instead of removed TextField prop APIs', () => {
    const removedTextFieldProp =
      /\b(?:FormHelperTextProps|InputLabelProps|InputProps|SelectProps|inputProps)\s*=/g;
    const offenders = jsxFiles.flatMap((filePath) => {
      const relativePath = path.relative(sourceRoot, filePath);
      return [...fs.readFileSync(filePath, 'utf8').matchAll(removedTextFieldProp)].map(
        (match) => `${relativePath}:${match[0].replace(/\s*=.*/, '')}`,
      );
    });

    expect(offenders).toEqual([]);
  });
});
