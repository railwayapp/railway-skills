---
name: update-project
description: Update Railway project settings. Use when user wants to change project name, enable/disable PR deploys, make project public/private, or modify project configuration.
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

Use the railway-api.sh helper to make GraphQL requests:
```bash
/path/to/skills/lib/railway-api.sh 'mutation { projectUpdate(id: "PROJECT_ID", input: { FIELD: VALUE }) { FIELD } }'
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

**Change project name:**
```bash
railway-api.sh 'mutation { projectUpdate(id: "uuid", input: { name: "new-name" }) { name } }'
```

**Enable PR deploys:**
```bash
railway-api.sh 'mutation { projectUpdate(id: "uuid", input: { prDeploys: true }) { prDeploys } }'
```

**Enable bot PR environments (Dependabot, Renovate):**
```bash
railway-api.sh 'mutation { projectUpdate(id: "uuid", input: { botPrEnvironments: true }) { botPrEnvironments } }'
```

**Make project public:**
```bash
railway-api.sh 'mutation { projectUpdate(id: "uuid", input: { isPublic: true }) { isPublic } }'
```

**Multiple fields at once:**
```bash
railway-api.sh 'mutation { projectUpdate(id: "uuid", input: { name: "new-name", prDeploys: true }) { name prDeploys } }'
```

## Error Handling

If the API returns an error, check:
- Project ID is correct (from `railway status --json`)
- User is authenticated (`railway whoami`)
- User has permission to modify the project
