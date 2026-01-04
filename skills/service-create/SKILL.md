---
name: service-create
description: Create a new Railway service. Use when user wants to add a new service, create a service from an image, or add a service from a repo.
---

# Create Service

Create a new service on a Railway project.

## When to Use

- User asks to "create a service", "add a service", "new service"
- User wants to deploy a Docker image as a new service
- User wants to add a GitHub repo as a new service

## Prerequisites

### 1. Get Context
```bash
railway status --json
```

Extract:
- `project.id` - for creating the service
- `environment.id` - for staging the instance config

## Step 1: Create the Service

```graphql
mutation serviceCreate($input: ServiceCreateInput!) {
  serviceCreate(input: $input) {
    id
    name
  }
}
```

### ServiceCreateInput Fields

| Field | Type | Description |
|-------|------|-------------|
| `projectId` | String! | Project ID (required) |
| `name` | String | Service name (auto-generated if omitted) |
| `source.image` | String | Docker image (e.g., `nginx:latest`) |
| `source.repo` | String | GitHub repo (e.g., `user/repo`) |
| `branch` | String | Git branch for repo source |
| `environmentId` | String | If set and is a fork, only creates in that env |

### Example: Create empty service
```bash
skills/lib/railway-api.sh \
  'mutation createService($input: ServiceCreateInput!) {
    serviceCreate(input: $input) { id name }
  }' \
  '{"input": {"projectId": "PROJECT_ID"}}'
```

### Example: Create service with image
```bash
skills/lib/railway-api.sh \
  'mutation createService($input: ServiceCreateInput!) {
    serviceCreate(input: $input) { id name }
  }' \
  '{"input": {"projectId": "PROJECT_ID", "name": "my-service", "source": {"image": "nginx:latest"}}}'
```

### Example: Create service from repo
```bash
skills/lib/railway-api.sh \
  'mutation createService($input: ServiceCreateInput!) {
    serviceCreate(input: $input) { id name }
  }' \
  '{"input": {"projectId": "PROJECT_ID", "source": {"repo": "user/repo"}, "branch": "main"}}'
```

## Step 2: Configure Service Instance

After creating the service, use `environment-update` skill to configure the instance:

```json
{
  "services": {
    "<serviceId>": {
      "isCreated": true,
      "source": { "image": "nginx:latest" },
      "variables": {
        "PORT": { "value": "8080" }
      },
      "deploy": {
        "startCommand": "npm start"
      }
    }
  }
}
```

**Critical:** Always include `isCreated: true` for new service instances.

## Step 3: Apply Changes

Use `environment-apply` skill to commit and deploy.

## Complete Example

Create a service with image and variables:

```bash
# 1. Get project context
railway status --json

# 2. Create service
skills/lib/railway-api.sh \
  'mutation createService($input: ServiceCreateInput!) {
    serviceCreate(input: $input) { id name }
  }' \
  '{"input": {"projectId": "PROJECT_ID", "name": "my-api", "source": {"image": "node:20"}}}'

# 3. Stage instance config (use environment-update skill)
# Include isCreated: true, source, variables, etc.

# 4. Apply changes (use environment-apply skill)
```

## Composability

This skill composes with:
- `environment-update` - Configure the service instance (variables, commands, etc.)
- `environment-apply` - Deploy the changes

Typical flow:
1. `service-create` → creates service, returns ID
2. `environment-update` → stages instance config with `isCreated: true`
3. `environment-apply` → deploys

## Error Handling

### Project Not Found
User may not be in a linked project. Check `railway status`.

### Permission Denied
User needs at least DEVELOPER role to create services.

### Invalid Image
Docker image must be accessible (public or with registry credentials).
