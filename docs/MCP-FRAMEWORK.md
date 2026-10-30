# Optional MCP framework

`backend/mcp_framework` is the unchanged canonical package from FullStackTemplate
commit `5a9294d550ec946a51b34bb2438a6c04ecc13461`, tracked by
[template #259 / PR #260](https://github.com/VanillaIceCube/FullStackTemplate/issues/259).
`mcp-framework-source.json` pins the source and
`backend/mcp-framework-manifest.json` hashes every Python file. Verify with
`python scripts/check_mcp_framework.py`; never patch the vendor independently.
Update the canonical source and synchronize every consumer to one immutable pin.
The current hook permits an external issuer only with an explicitly supplied
verifier and requires HTTPS in production; transport Host/Origin trust remains
owned by the resource app.

MacroMapper uses the app-owned `app_mcp` registry and fixed central issuer rather
than the canonical sample/local OAuth provider. See [MacroMapper MCP](MCP.md) for
tools, schemas, permission/confirmation boundaries, identity linking, client setup,
private credentials, readiness and rollback. Source defaults remain off; the prepared enabled production policy is held for
shared issuer/YNAB acceptance and coordinated env-prod activation. Ordinary login,
REST JWTs, meal estimation and frontend behavior stay independent.

The shared ASGI lifecycle, exact `/mcp` transport, stateless JSON mode, 64 KiB
request bound and reviewed exact proxy/Host/Origin handling remain canonical.
An enabled resource exposes protected-resource metadata identifying the central
issuer; it does not expose local authorization/token/consent routes. Local
`register_mcp_client` and the scaffold frontend connection pages are not used.
Do not set `VITE_MCP_ENABLED=1` for this central-issuer profile.

CI separately verifies the canonical provider through
`app.framework_test_settings` / `app_mcp.framework_test_urls`, which are test-only
and never selected by production. This preserves shared lifecycle/OAuth tests
without publishing a second authorization server. Application tests cover the
actual enabled central-resource profile plus normal disabled-profile regressions.

No shared ingress/network, existing application, issuer database, key or production
instance is provisioned by package adoption. Infrastructure owns the gateway and
issuer; MacroMapper owns its existing-user links, food/meal permissions and
independent [release/recovery](../deploy/production/README.md).
