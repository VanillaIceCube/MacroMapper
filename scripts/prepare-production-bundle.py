"""Fail closed for the retired bridge bundle; preserve installed live files."""
raise SystemExit(
    "Retired bridge bundle. Use deploy/production/build_bundle.py after approved ingress cutover."
)
