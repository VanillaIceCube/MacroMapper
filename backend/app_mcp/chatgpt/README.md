# 🔌 MacroMapper ChatGPT connection

This package connects to the app-owned MCP server at
`https://macromapper.judeandrewalaba.com/mcp`. It uses existing MacroMapper
accounts, a predefined public OAuth client, and explicit consent.

## 🔗 Connect and choose permissions

The client ID is `macromapper-chatgpt`, with token authentication method `none`
and S256 PKCE. This package requests `macromapper:read` only and advertises read
access. It cannot perform writes or paid estimates with that grant.

To intentionally build a broader variant, add `macromapper:write` to
`baseScopes` in `mcp.json` for confirmed ordinary mutations. Paid estimates also
require `macromapper:estimate` and separate explicit confirmation. Review and
update the listing capabilities and descriptions to match that variant before
building, then obtain a new consent grant for its requested scopes. Existing
grants cannot silently gain new scopes.

Follow the [app MCP guide](../../macromapper_mcp/README.md#-consent-and-client-setup)
for client registration, the exact callback, consent, tool coverage, and
verification. Deployment does not register the client or install a plugin.
No existing installed plugin or registered app identity is assumed here.

## 🧭 Files

- `plugin.json`: MacroMapper listing metadata and presentation.
- `mcp.json`: HTTPS endpoint, public OAuth settings, and least-privilege scopes.
- `assets/`: a square PNG export of the existing frontend MacroMapper mark.
- `build_package.py`, `build_listing.py`: portable and existing-listing builders.


## 🧰 Build and validate packages

Run the offline regression suite from the repository root:

```powershell
python -m unittest discover -s backend/app_mcp/chatgpt -p "test_*.py" -v
```

To build a portable ZIP containing only `plugin.json`, `mcp.json`, and referenced
artwork, write the output outside the source directory:

```powershell
python backend/app_mcp/chatgpt/build_package.py --output "$env:TEMP/application-chatgpt.zip"
```

The portable archive contains no account-specific `.app.json`, source code,
test files, or exported account credentials. Building it does not install,
register, publish, or deploy the integration.

For an existing personal listing, download that plugin's export first and run:

```powershell
python backend/app_mcp/chatgpt/build_listing.py `
  --export "$env:USERPROFILE/Downloads/plugin.zip" `
  --output "$env:TEMP/application-listing.zip" `
  --version 1.0.1
```

Choose a version greater than the export's current version. The overlay verifies
the expected display name and preserves the exported plugin name, app mapping,
and other exported files. Upload through the existing plugin's update flow
when authorized. No registered app ID is stored or invented in this repository.
