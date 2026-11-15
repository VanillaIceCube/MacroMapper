# 🧰 MacroMapper compatibility scripts

This folder retains two retired entry points solely as fail-closed compatibility
stubs. Neither performs deployment or prepares a production bundle.

| Stub | Purpose |
| --- | --- |
| [deploy-production.sh](deploy-production.sh) | Reject the retired production deployment path. |
| [prepare-production-bundle.py](prepare-production-bundle.py) | Reject the retired production bundle bridge. |

Legacy `env-prod` history and external/operator callers may still invoke them.
Remove these stubs only after the host operator inventories callers, migrates or
disables every legacy caller, verifies release and recovery, confirms retained
rollback procedures do not invoke them, and records the evidence in the deployment
issue. Follow the [production guide](../deploy/production/README.md#boundary-and-activation-order).

Active tooling lives with its owners: [CI tools](../.github/README.md#-verification),
[browser helpers](../frontend/README.md#-browser-tests), [MCP verification](../backend/app_mcp/README.md#-verification),
[local certificates](../deploy/README.md).
