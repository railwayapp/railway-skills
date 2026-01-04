---
name: environment-config
description: Check Railway environment configuration. Use when user asks about current settings, build/deploy config, variables, replicas, or before making configuration changes.
---

# Environment Configuration

Fetch current environment configuration and staged changes for a Railway environment.

## When to Use

- User asks about current build/deploy settings
- User asks what variables are configured
- User asks about replicas, health checks, domains
- Before making configuration changes (preflight)
- Debugging why a service isn't building/deploying correctly

## Get Context

First get the environment ID:
```bash
railway status --json
```

Extract `environment.id` from the response.

## Query Configuration

Use `railway-api.sh` to fetch the environment config:

```graphql
query environmentConfig($environmentId: String!) {
  environment(id: $environmentId) {
    id
    config(decryptVariables: false)
    serviceInstances {
      edges {
        node {
          id
          serviceId
        }
      }
    }
  }
  environmentStagedChanges(environmentId: $environmentId) {
    id
    patch(decryptVariables: false)
  }
}
```

Example call:
```bash
skills/lib/railway-api.sh \
  'query envConfig($envId: String!) {
    environment(id: $envId) { id config(decryptVariables: false) }
    environmentStagedChanges(environmentId: $envId) { id patch(decryptVariables: false) }
  }' \
  '{"envId": "ENV_ID"}'
```

## Response Structure

The `config` field contains the current environment configuration:

```json
{
  "services": {
    "<serviceId>": {
      "source": { "repo": "...", "branch": "main" },
      "build": { "buildCommand": "npm run build", "builder": "NIXPACKS" },
      "deploy": { "startCommand": "npm start", "numReplicas": 1 },
      "variables": { "NODE_ENV": { "value": "production" } },
      "networking": { "serviceDomains": {}, "customDomains": {} }
    }
  },
  "sharedVariables": { "DATABASE_URL": { "value": "..." } }
}
```

The `patch` field in `environmentStagedChanges` contains pending changes not yet deployed.

For complete field reference, see [reference/environment-config.md](../reference/environment-config.md).

## Merging Config and Staged Changes

The effective configuration is the base `config` merged with the staged `patch`. Present the merged result to show what will be active after next deploy.

## Present to User

Show relevant fields based on what the user asked about:

**Build configuration:**
- Builder (NIXPACKS, DOCKERFILE, RAILPACK)
- Build command
- Dockerfile path (if DOCKERFILE builder)
- Watch patterns

**Deploy configuration:**
- Start command
- Number of replicas
- Health check path/timeout
- Region(s)

**Variables:**
- List variable names (not values for security)
- Indicate which are shared vs service-specific

**Networking:**
- Service domains
- Custom domains
- TCP proxies

## Error Handling

### No Linked Project
```
No project linked. Run `railway link` to link a project.
```

### No Environment
```
No environment selected. Run `railway environment` to select one.
```
