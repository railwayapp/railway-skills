---
name: environment-update
description: Update Railway environment configuration. Use when user wants to change source (Docker image, branch, root directory), build command, start command, replicas, variables, domains, health checks, or any service settings. Also use to auto-fix build/deploy errors.
---

# Update Environment Configuration

Stage configuration changes for a Railway environment via the GraphQL API.

## When to Use

- User asks to change service source (Docker image, branch, commit, root directory)
- User asks to change build or start command
- User wants to add/update environment variables
- User wants to change replica count
- User wants to configure health checks
- User wants to update domains or networking
- Auto-fixing build errors detected in logs
- Any service configuration change

## Prerequisites

### 1. Get Context
```bash
railway status --json
```

Extract:
- `project.id` - for service lookup
- `environment.id` - for the mutation
- `service.id` - default service if user doesn't specify one

### 2. Resolve Service ID

If user specifies a service by name, query project services:

```graphql
query projectServices($projectId: String!) {
  project(id: $projectId) {
    services {
      edges {
        node {
          id
          name
        }
      }
    }
  }
}
```

Match the service name (case-insensitive) to get the service ID.

If no service specified, use the linked service from `railway status`.

### 3. Fetch Current Staged Changes

Before updating, fetch existing staged changes to merge with:

```graphql
query {
  environmentStagedChanges(environmentId: "ENV_ID") {
    id
    patch(decryptVariables: false)
  }
}
```

## Stage Changes Mutation

```graphql
mutation stageEnvironmentChanges($environmentId: String!, $input: EnvironmentConfig!) {
  environmentStageChanges(environmentId: $environmentId, input: $input) {
    id
  }
}
```

**Important:** Always use variables (not inline input) because service IDs are UUIDs
which can't be used as unquoted GraphQL object keys.

Example call:
```bash
skills/lib/railway-api.sh \
  'mutation stageChanges($environmentId: String!, $input: EnvironmentConfig!) {
    environmentStageChanges(environmentId: $environmentId, input: $input) { id }
  }' \
  '{"environmentId": "ENV_ID", "input": {"services": {"SERVICE_ID": {"build": {"buildCommand": "npm run build"}}}}}'
```

## Patch Structure

The `input` is an `EnvironmentConfig` object. Only include fields being changed:

```json
{
  "services": {
    "<serviceId>": {
      "source": {
        "image": "node:20",
        "branch": "main",
        "rootDirectory": "apps/api"
      },
      "build": {
        "buildCommand": "npm run build",
        "builder": "NIXPACKS",
        "dockerfilePath": "./Dockerfile",
        "watchPatterns": ["src/**", "package.json"]
      },
      "deploy": {
        "startCommand": "npm start",
        "numReplicas": 2,
        "healthcheckPath": "/health",
        "healthcheckTimeout": 30,
        "restartPolicyType": "ON_FAILURE",
        "restartPolicyMaxRetries": 10
      },
      "variables": {
        "NODE_ENV": { "value": "production" },
        "DEBUG": { "value": "true" }
      }
    }
  },
  "sharedVariables": {
    "DATABASE_URL": { "value": "postgres://..." }
  }
}
```

## Common Operations

### Set Build Command
```json
{
  "services": {
    "<serviceId>": {
      "build": { "buildCommand": "npm run build" }
    }
  }
}
```

### Set Start Command
```json
{
  "services": {
    "<serviceId>": {
      "deploy": { "startCommand": "node server.js" }
    }
  }
}
```

### Set Replicas
```json
{
  "services": {
    "<serviceId>": {
      "deploy": { "numReplicas": 3 }
    }
  }
}
```

### Add Service Variables
```json
{
  "services": {
    "<serviceId>": {
      "variables": {
        "API_KEY": { "value": "xxx" },
        "DEBUG": { "value": "true" }
      }
    }
  }
}
```

### Add Shared Variables
```json
{
  "sharedVariables": {
    "DATABASE_URL": { "value": "postgres://..." }
  }
}
```

### Set Health Check
```json
{
  "services": {
    "<serviceId>": {
      "deploy": {
        "healthcheckPath": "/health",
        "healthcheckTimeout": 30
      }
    }
  }
}
```

### Change Builder
```json
{
  "services": {
    "<serviceId>": {
      "build": { "builder": "DOCKERFILE", "dockerfilePath": "./Dockerfile" }
    }
  }
}
```

### Change Source to Docker Image
```json
{
  "services": {
    "<serviceId>": {
      "source": { "image": "nginx:latest" }
    }
  }
}
```

### Change Git Branch
```json
{
  "services": {
    "<serviceId>": {
      "source": { "branch": "develop" }
    }
  }
}
```

### Set Root Directory (monorepo)
```json
{
  "services": {
    "<serviceId>": {
      "source": { "rootDirectory": "apps/api" }
    }
  }
}
```

### Deploy Specific Commit
```json
{
  "services": {
    "<serviceId>": {
      "source": { "commitSha": "abc123def456" }
    }
  }
}
```

### Enable Auto-Updates for Docker Image
```json
{
  "services": {
    "<serviceId>": {
      "source": {
        "image": "postgres:16",
        "autoUpdates": { "type": "patch" }
      }
    }
  }
}
```

## Merging Changes (Critical)

The `environmentStageChanges` mutation **replaces** all staged changes, it does not
merge. You MUST fetch existing staged changes and merge before calling the mutation.

### Required Flow

1. **Fetch current staged changes:**
```bash
skills/lib/railway-api.sh \
  'query staged($envId: String!) {
    environmentStagedChanges(environmentId: $envId) { patch(decryptVariables: false) }
  }' \
  '{"envId": "ENV_ID"}'
```

2. **Deep merge** user's new changes into the existing `patch`

3. **Send merged result** as `input` to the mutation

### Example

If existing staged changes are:
```json
{"services": {"svc-id": {"source": {"image": "nginx"}}}}
```

And user wants to add a variable, the merged input must be:
```json
{"services": {"svc-id": {"source": {"image": "nginx"}, "variables": {"HELLO": {"value": "world"}}}}}
```

NOT just the new change (which would erase the image change):
```json
{"services": {"svc-id": {"variables": {"HELLO": {"value": "world"}}}}}
```

## Available Fields

### Source Config
| Field | Type | Description |
|-------|------|-------------|
| `image` | string | Docker image (e.g., `nginx:latest`, `ghcr.io/org/app:v1`) |
| `repo` | string | Git repository URL |
| `branch` | string | Git branch to deploy |
| `commitSha` | string | Specific commit SHA to deploy |
| `rootDirectory` | string | Root directory in repo (for monorepos) |
| `checkSuites` | boolean | Wait for GitHub check suites |
| `autoUpdates.type` | disabled \| patch \| minor | Auto-update policy for Docker images |

### Build Config
| Field | Type | Description |
|-------|------|-------------|
| `builder` | NIXPACKS \| DOCKERFILE \| RAILPACK | Build system |
| `buildCommand` | string | Command for Nixpacks builds |
| `dockerfilePath` | string | Path to Dockerfile |
| `watchPatterns` | string[] | Patterns to trigger deploys |
| `nixpacksConfigPath` | string | Path to nixpacks config |

### Deploy Config
| Field | Type | Description |
|-------|------|-------------|
| `startCommand` | string | Container start command |
| `numReplicas` | number | Number of instances (1-200) |
| `healthcheckPath` | string | Health check endpoint |
| `healthcheckTimeout` | number | Seconds to wait for health |
| `restartPolicyType` | ON_FAILURE \| ALWAYS \| NEVER | Restart behavior |
| `restartPolicyMaxRetries` | number | Max restart attempts |
| `cronSchedule` | string | Cron schedule for cron jobs |
| `sleepApplication` | boolean | Sleep when inactive |

### Variables
| Field | Type | Description |
|-------|------|-------------|
| `value` | string | Variable value |
| `isOptional` | boolean | Allow empty value |

## Error Handling

### Service Not Found
If user specifies a service name that doesn't exist:
```
Service "foo" not found in project. Available services: api, web, worker
```

### Invalid Configuration
The API will return validation errors for invalid configs. Common issues:
- `buildCommand` and `startCommand` cannot be identical
- `buildCommand` only valid with NIXPACKS builder
- `dockerfilePath` only valid with DOCKERFILE builder

### No Permission
```
You don't have permission to modify this environment. Check your Railway role.
```

## After Staging

Changes are staged, not deployed. Tell the user:
```
Changes staged successfully. They will apply on next deploy.
To deploy now, run `railway up` or push to the linked GitHub repo.
```
