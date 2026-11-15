import fs from 'node:fs';
import path from 'node:path';
import { parse } from '@babel/parser';
import * as mealItem from '../domain/mealItem';
import * as nutrition from '../domain/nutrition';

const sourceRoot = path.resolve(process.cwd(), 'src');
const domainRoot = path.join(sourceRoot, 'domain');

function modulesIn(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) return modulesIn(filename);
    return /\.jsx?$/.test(filename) && !/\.test\.jsx?$/.test(filename) ? [filename] : [];
  });
}

function importsIn(filename) {
  const ast = parse(fs.readFileSync(filename, 'utf8'), {
    sourceType: 'module',
    plugins: ['jsx'],
  });
  return ast.program.body.flatMap((node) => (node.source ? [node.source.value] : []));
}

function resolveImport(filename, specifier) {
  const target = path.resolve(path.dirname(filename), specifier);
  const resolved = [target, `${target}.js`, path.join(target, 'index.js')].find(
    (candidate) => fs.existsSync(candidate) && fs.statSync(candidate).isFile(),
  );
  if (!resolved) throw new Error(`Missing import: ${filename} -> ${specifier}`);
  return resolved;
}

describe('frontend domain boundaries', () => {
  test('components and pages use public domain entry points', () => {
    for (const directory of ['components', 'pages']) {
      for (const filename of modulesIn(path.join(sourceRoot, directory))) {
        for (const specifier of importsIn(filename)) {
          expect(specifier).not.toMatch(/domain\/(?:mealItem|nutrition)\/(?!index(?:\.js)?$)/);
        }
      }
    }
  });

  test.each([
    ['mealItem', mealItem],
    ['nutrition', nutrition],
  ])('%s entry point exposes all exports without name collisions', (name, namespace) => {
    const directory = path.join(domainRoot, name);
    const names = [];
    for (const filename of modulesIn(directory).filter(
      (file) => path.basename(file) !== 'index.js',
    )) {
      const ast = parse(fs.readFileSync(filename, 'utf8'), { sourceType: 'module' });
      for (const node of ast.program.body) {
        if (node.type !== 'ExportNamedDeclaration') continue;
        if (node.declaration?.type === 'VariableDeclaration') {
          names.push(...node.declaration.declarations.map((declaration) => declaration.id.name));
        } else if (node.declaration) {
          names.push(node.declaration.id.name);
        } else {
          names.push(...node.specifiers.map((specifier) => specifier.exported.name));
        }
      }
    }
    expect(new Set(names).size).toBe(names.length);
    expect(Object.keys(namespace).sort()).toEqual(names.sort());
  });

  test('domain dependencies remain independent of UI modules and presentation metadata', () => {
    const inspected = new Set();
    function inspect(filename) {
      if (inspected.has(filename)) return;
      inspected.add(filename);
      const relative = path.relative(sourceRoot, filename).split(path.sep);
      expect(['domain', 'utils']).toContain(relative[0]);
      const source = fs.readFileSync(filename, 'utf8');
      expect(source).not.toContain('var(--');
      for (const specifier of importsIn(filename)) {
        expect(specifier).not.toMatch(/^(react(?:-dom)?(?:\/|$)|@mui\/)/);
        expect(specifier.startsWith('.')).toBe(true);
        inspect(resolveImport(filename, specifier));
      }
    }
    modulesIn(domainRoot).forEach(inspect);
  });

  test('domain dependencies contain no cycles', () => {
    const completed = new Set();
    function visit(filename, active = []) {
      if (active.includes(filename)) {
        throw new Error(`Circular dependency: ${[...active, filename].join(' -> ')}`);
      }
      if (completed.has(filename)) return;
      for (const specifier of importsIn(filename).filter((value) => value.startsWith('.'))) {
        visit(resolveImport(filename, specifier), [...active, filename]);
      }
      completed.add(filename);
    }
    modulesIn(domainRoot).forEach((filename) => visit(filename));
  });
});
