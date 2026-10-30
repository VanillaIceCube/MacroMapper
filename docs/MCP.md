# 🔌 MacroMapper MCP status

MacroMapper MCP is deferred in [#284](https://github.com/VanillaIceCube/MacroMapper/issues/284).
The central-issuer meal/nutrition implementation from PR #328 was merged into main
but never deployed. It has been removed, including identity links, confirmation
models, central introspection credential plumbing, enabled production policy and its
special rollout/recovery tooling. No production database rollback is required.

## 🧭 Application ownership

MacroMapper retains the existing [optional MCP/OAuth framework](MCP-FRAMEWORK.md)
with production `DJANGO_MCP_ENABLED=0` and frontend connection routes off.
There is no production MCP registry, advertised connector or shared issuer.
A future implementation belongs to MacroMapper: OAuth client registration,
consent, credentials, scopes, revocation, existing-user ownership and domain tools.
Infrastructure provides ordinary Nginx routing to the application's backend.
Do not provision a standalone shared MCP authorization service or depend on YNAB.

Future meal writes still need explicit scopes, validation and intentional
confirmation. Ordinary website login, REST JWTs, meal history and AI estimation
remain independent. Do not advertise MacroMapper MCP until its app-owned
implementation and real-client acceptance are complete.

## 📦 Release and recovery

The existing production release already has MCP disabled. This source correction
requires no MacroMapper production operation, credential provisioning or database
migration. Preserve current images, data and recovery evidence. Keep newer main
changes out of production until separately reviewed and authorized. Use the
[normal app-only release guide](../deploy/production/README.md) for future releases;
shared gateway cleanup belongs to the Infrastructure operator.
