# Environment Config Reference

The `EnvironmentConfig` object is used to configure services, volumes, and shared variables in Railway.

## Structure

```json
{
  "services": {
    "<serviceId>": {
      "source": { ... },
      "build": { ... },
      "deploy": { ... },
      "variables": { ... },
      "networking": { ... }
    }
  },
  "sharedVariables": { ... },
  "volumes": { ... },
  "buckets": { ... }
}
```

Only include fields being changed. The patch is merged with existing config.

## Service Config

### Source
| Field | Type | Description |
|-------|------|-------------|
| `image` | string | Docker image (e.g., `nginx:latest`) |
| `repo` | string | Git repository URL |
| `branch` | string | Git branch to deploy |
| `commitSha` | string | Specific commit SHA |
| `rootDirectory` | string | Root directory (monorepos) |
| `checkSuites` | boolean | Wait for GitHub check suites |
| `autoUpdates.type` | disabled \| patch \| minor | Auto-update policy for Docker images |

### Build
| Field | Type | Description |
|-------|------|-------------|
| `builder` | NIXPACKS \| DOCKERFILE \| RAILPACK | Build system |
| `buildCommand` | string | Command for Nixpacks builds |
| `dockerfilePath` | string | Path to Dockerfile |
| `watchPatterns` | string[] | Patterns to trigger deploys |
| `nixpacksConfigPath` | string | Path to nixpacks config |

### Deploy
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

Set to `null` to delete a variable.

For variable references, see [variables.md](variables.md).

### Lifecycle
| Field | Type | Description |
|-------|------|-------------|
| `isDeleted` | boolean | Mark for deletion (requires ADMIN) |
| `isCreated` | boolean | Mark as newly created |

## Common Operations

### Set Build Command
```json
{ "services": { "<serviceId>": { "build": { "buildCommand": "npm run build" } } } }
```

### Set Start Command
```json
{ "services": { "<serviceId>": { "deploy": { "startCommand": "node server.js" } } } }
```

### Set Replicas
```json
{ "services": { "<serviceId>": { "deploy": { "numReplicas": 3 } } } }
```

### Add Variables
```json
{ "services": { "<serviceId>": { "variables": { "API_KEY": { "value": "xxx" } } } } }
```

### Delete Variable
```json
{ "services": { "<serviceId>": { "variables": { "OLD_VAR": null } } } }
```

### Add Shared Variable
```json
{ "sharedVariables": { "DATABASE_URL": { "value": "postgres://..." } } }
```

### Change Docker Image
```json
{ "services": { "<serviceId>": { "source": { "image": "nginx:latest" } } } }
```

### Change Git Branch
```json
{ "services": { "<serviceId>": { "source": { "branch": "develop" } } } }
```

### Set Health Check
```json
{ "services": { "<serviceId>": { "deploy": { "healthcheckPath": "/health", "healthcheckTimeout": 30 } } } }
```

### Change Builder
```json
{ "services": { "<serviceId>": { "build": { "builder": "DOCKERFILE", "dockerfilePath": "./Dockerfile" } } } }
```

### Delete Service
```json
{ "services": { "<serviceId>": { "isDeleted": true } } }
```

### Delete Volume
```json
{ "volumes": { "<volumeId>": { "isDeleted": true } } }
```

### New Service Instance
```json
{ "services": { "<serviceId>": { "isCreated": true, "source": { "image": "nginx" } } } }
```

**Note:** `isCreated: true` is required for new service instances.
