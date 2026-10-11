import fs from 'node:fs';
import path from 'node:path';
import { parse } from '@babel/parser';

const sourceRoot = path.resolve(process.cwd(), 'src');
const domainRoot = path.join(sourceRoot, 'domain');

function modulesIn(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) return modulesIn(filename);
    return filename.endsWith('.js') && !filename.endsWith('.test.js') ? [filename] : [];
  });
}

function importsIn(filename) {
  const ast = parse(fs.readFileSync(filename, 'utf8'), { sourceType: 'module' });
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
