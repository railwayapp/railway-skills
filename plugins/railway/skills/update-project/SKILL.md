---
name: update-project
description: Update Railway project settings. Use when user wants to change project name, enable/disable PR deploys, make project public/private, or modify project configuration.
allowed-tools: Bash(railway:*)
---

# Update Railway Project

Modify project settings using the Railway GraphQL API.

## Prerequisites

First get the project ID by running:
```bash
railway status --json
```
Extract the `id` field from the response.

## Making the API Call

Use the railway-api.sh helper with query and variables:
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'mutation updateProject($id: String!, $input: ProjectUpdateInput!) {
    projectUpdate(id: $id, input: $input) { name }
  }' \
  '{"id": "PROJECT_ID", "input": {"name": "new-name"}}'
```

## Available Fields (ProjectUpdateInput)

| Field | Type | Example |
|-------|------|---------|
| `name` | String | `"my-new-name"` |
| `description` | String | `"Project description"` |
| `isPublic` | Boolean | `true` or `false` |
| `prDeploys` | Boolean | `true` or `false` |
| `botPrEnvironments` | Boolean | `true` or `false` |

## Examples

All examples use the same mutation with different variables:

```graphql
mutation updateProject($id: String!, $input: ProjectUpdateInput!) {
  projectUpdate(id: $id, input: $input) { name prDeploys isPublic botPrEnvironments }
}
```

**Change project name:**
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh '<mutation>' '{"id": "uuid", "input": {"name": "new-name"}}'
```

**Enable PR deploys:**
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh '<mutation>' '{"id": "uuid", "input": {"prDeploys": true}}'
```

**Enable bot PR environments (Dependabot, Renovate):**
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh '<mutation>' '{"id": "uuid", "input": {"botPrEnvironments": true}}'
```

**Make project public:**
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh '<mutation>' '{"id": "uuid", "input": {"isPublic": true}}'
```

**Multiple fields at once:**
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh '<mutation>' '{"id": "uuid", "input": {"name": "new-name", "prDeploys": true}}'
```

## Error Handling

If the API returns an error, check:
- Project ID is correct (from `railway status --json`)
- User is authenticated (`railway whoami`)
- User has permission to modify the project
