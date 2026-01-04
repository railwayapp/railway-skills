---
name: environment-update
description: Update Railway environment configuration. Use when user wants to change source (Docker image, branch, root directory), build command, start command, replicas, variables, domains, health checks, delete services/volumes, or any service settings. Also use to auto-fix build/deploy errors.
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
- User asks to delete a service, volume, or bucket
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

For patch structure and available fields, see [reference/environment-config.md](../reference/environment-config.md).

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

## After Staging: Auto-Apply

By default, **apply changes immediately** after staging using the `environment-apply`
skill. This triggers a deployment.

### When to Auto-Apply (default)
- User makes a single configuration change
- No preexisting staged changes before this update
- User doesn't explicitly ask to "just stage" or "stage without deploying"

### When NOT to Auto-Apply
- There were preexisting staged changes (user may be batching changes)
- User explicitly says "stage only", "don't deploy yet", or similar
- Making multiple related changes that should be batched

### Flow
1. Check for preexisting staged changes before making updates
2. Stage the new changes
3. If no preexisting changes → call `environment-apply` to commit and deploy
4. If preexisting changes → inform user changes are staged, ask if they want to apply

### After Auto-Apply
```
Changes applied and deploying.
```

### After Stage-Only
```
Changes staged. Run environment-apply or say "apply changes" to deploy.
```
