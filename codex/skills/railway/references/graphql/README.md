# GraphQL Helper (Railway)

Use GraphQL only when the Railway CLI does not expose the operation you need or
for bulk queries that are awkward in the CLI. Default to CLI whenever possible.

Helper:

```bash
~/.codex/skills/railway/lib/railway-api.sh '<query>' '<variables-json>'
```

Notes:

- Reads the token from `~/.railway/config.json`; never print the token.
- Requires `jq` (install with `brew install jq`).
