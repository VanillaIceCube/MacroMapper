# 🔌 MacroMapper plugins

This folder is the entry point for client-facing plugin documentation and
packages. Application tools, OAuth, and permissions live in the backend.

## 🧭 Current integration

MacroMapper implements application-owned MCP tools and OAuth. Its connection
and permission guide lives beside the backend implementation.

- [Backend MCP integration](../backend/README.md#-mcp-integration).
- [Shared MCP framework](../backend/mcp_framework/README.md).
- [MacroMapper tools, scopes, and client setup](../backend/macromapper_mcp/README.md).

## 📦 Package layout

Application-specific packages use `plugins/<application-slug>/`. That folder
owns the client manifest, listing metadata, artwork, packaging helpers, and
connection instructions when a package is maintained. Backend deployment and
client listing updates are separate operations.

This repository currently has no checked-in client listing package.
