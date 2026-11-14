# TypeScript 7 compatibility — 2026-11-05

Outcome: blocked upstream; retain `typescript: ~6.0.3` for issue #224.
Registry metadata on this date reports TypeScript 7.0.2, React ESLint plugin
5.28.8, typescript-eslint parser/utilities 8.72.1 and ts-api-utils 2.5.0.
The parser and utilities explicitly require `typescript >=4.8.4 <6.1.0`.
The wider `>=4.8.4` ts-api-utils peer declaration does not establish TypeScript
7 compiler-API compatibility or override the narrower parser support window.
The React plugin family still depends on the typescript-eslint utilities.

No dependency override, incompatible installation or repeated known-bad upgrade
was performed. Resume only after released support covers TypeScript 7 and the
whole lint stack passes clean install, strict lint, formatting, tests and build.

Evidence: npm registry `npm view <package>@latest version peerDependencies dependencies --json`
for the packages above, plus the upstream [support policy](https://typescripteslint.com/users/dependency-versions/)
and [compiler API compatibility issue](https://github.com/typescript-eslint/ts-api-utils/issues/1051).
No production change is implied by this disposition.
