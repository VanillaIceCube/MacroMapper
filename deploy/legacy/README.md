# Historical bridge — recovery evidence only

These are the PR #239 bridge artifacts formerly shipped in app releases.
The shared-ingress implementation supersedes their source ownership. The new
app pipeline ships only `deploy/production`, never these files.

Their relative paths are historical and are not an installation recipe here.
Do not execute/install these templates for a new app release. Preserve the
already-installed live bridge and operator-captured effective configuration
until the separately approved gateway cutover and reversal are verified.
Archiving source here does not remove or change any live file.

The prior bridge test suite is replaced by the app-only transaction tests in
`deploy/tests/test_production.py`; actual gateway routing and endpoint reversal
are tested in the infrastructure repository. PR #241 retains historical test
evidence; those old counts are not claimed for this implementation.
