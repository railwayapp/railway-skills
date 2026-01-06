---
name: environment
description: Manage Railway environment configuration. Use when user wants to check config, set variables, change build/start commands, update replicas, configure health checks, change Docker image, connect GitHub repos, delete services/volumes/buckets, or apply/deploy staged changes. Do NOT use `railway variables` CLI - use this skill instead.
allowed-tools: Bash(railway:*)
---

# Environment Configuration

Query, stage, and apply configuration changes for Railway environments.

## When to Use

- User asks about current build/deploy settings, variables, replicas, health checks, domains
- User asks to change service source (Docker image, branch, commit, root directory)
- User wants to connect a service to a GitHub repo
- User wants to deploy from a GitHub repo (create empty service first via `new` skill, then use this)
- User asks to change build or start command
- User wants to add/update/delete environment variables
- User wants to change replica count or configure health checks
- User asks to delete a service, volume, or bucket
- User says "apply changes", "commit changes", "deploy changes"
- Auto-fixing build errors detected in logs

## Get Context

```bash
railway status --json
```

Extract:
- `project.id` - for service lookup
- `environment.id` - for the mutations
- `service.id` - default service if user doesn't specify one

### Resolve Service ID

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

## Query Configuration

Fetch current environment configuration and staged changes.

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

Example:
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'query envConfig($envId: String!) {
    environment(id: $envId) { id config(decryptVariables: false) }
    environmentStagedChanges(environmentId: $envId) { id patch(decryptVariables: false) }
  }' \
  '{"envId": "ENV_ID"}'
```

### Response Structure

The `config` field contains current configuration:

```json
{
  "services": {
    "<serviceId>": {
      "source": { "repo": "...", "branch": "main" },
      "build": { "buildCommand": "npm run build", "builder": "NIXPACKS" },
      "deploy": { "startCommand": "npm start", "multiRegionConfig": { "us-west2": { "numReplicas": 1 } } },
      "variables": { "NODE_ENV": { "value": "production" } },
      "networking": { "serviceDomains": {}, "customDomains": {} }
    }
  },
  "sharedVariables": { "DATABASE_URL": { "value": "..." } }
}
```

The `patch` field in `environmentStagedChanges` contains pending changes. The effective configuration is the base `config` merged with the staged `patch`.

For complete field reference, see [reference/environment-config.md](../reference/environment-config.md).

## Stage Changes

Stage configuration changes via the `environmentStageChanges` mutation.

### Fetch Existing Staged Changes First (Critical)

The mutation **replaces** all staged changes, it does not merge. You MUST fetch existing staged changes and merge before calling the mutation.

```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'query staged($envId: String!) {
    environmentStagedChanges(environmentId: $envId) { patch(decryptVariables: false) }
  }' \
  '{"envId": "ENV_ID"}'
```

### Stage Changes Mutation

```graphql
mutation stageEnvironmentChanges($environmentId: String!, $input: EnvironmentConfig!) {
  environmentStageChanges(environmentId: $environmentId, input: $input) {
    id
  }
}
```

**Important:** Always use variables (not inline input) because service IDs are UUIDs which can't be used as unquoted GraphQL object keys.

Example:
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'mutation stageChanges($environmentId: String!, $input: EnvironmentConfig!) {
    environmentStageChanges(environmentId: $environmentId, input: $input) { id }
  }' \
  '{"environmentId": "ENV_ID", "input": {"services": {"SERVICE_ID": {"build": {"buildCommand": "npm run build"}}}}}'
```

### Merging Changes

If existing staged changes are:
```json
{"services": {"svc-id": {"source": {"image": "nginx"}}}}
```

And user wants to add a variable, the merged input must be:
```json
{"services": {"svc-id": {"source": {"image": "nginx"}, "variables": {"HELLO": {"value": "world"}}}}}
```

NOT just the new change (which would erase the image change).

### Delete Service

Use `isDeleted: true`:
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'mutation stageChanges($environmentId: String!, $input: EnvironmentConfig!) {
    environmentStageChanges(environmentId: $environmentId, input: $input) { id }
  }' \
  '{"environmentId": "ENV_ID", "input": {"services": {"SERVICE_ID": {"isDeleted": true}}}}'
```

## Apply Changes

Commit staged changes and trigger deployments.

**Note:** There is no `railway apply` CLI command. Use the mutation below or direct users to the web UI.

### Apply Mutation

**Mutation name: `environmentPatchCommitStaged`**

```graphql
mutation environmentPatchCommitStaged($environmentId: String!, $message: String, $skipDeploys: Boolean) {
  environmentPatchCommitStaged(
    environmentId: $environmentId
    commitMessage: $message
    skipDeploys: $skipDeploys
  )
}
```

Example:
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'mutation commitStaged($environmentId: String!, $message: String) {
    environmentPatchCommitStaged(environmentId: $environmentId, commitMessage: $message)
  }' \
  '{"environmentId": "ENV_ID", "message": "add API_KEY variable"}'
```

### Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `environmentId` | String! | - | Environment ID from status |
| `message` | String | null | Short description of changes |
| `skipDeploys` | Boolean | false | Skip deploys (only if user explicitly asks) |

### Commit Message

Keep very short - one sentence max. Examples:
- "set build command to fix npm error"
- "add API_KEY variable"
- "increase replicas to 3"

Leave empty if no meaningful description.

### Default Behavior

**Always deploy** unless user explicitly asks to skip. Only set `skipDeploys: true` if user says "apply without deploying", "commit but don't deploy", or "skip deploys".

Returns a workflow ID (string) on success.

## Auto-Apply Behavior

By default, **apply changes immediately** after staging.

### When to Auto-Apply (default)
- User makes a single configuration change
- No preexisting staged changes before this update
- User doesn't explicitly ask to "just stage" or "stage without deploying"

### When NOT to Auto-Apply
- There were preexisting staged changes (user may be batching changes)
- User explicitly says "stage only", "don't deploy yet", or similar
- Making multiple related changes that should be batched

**When you don't auto-apply, tell the user:**
> Changes staged. Apply them at: https://railway.com/project/{projectId}
> Or ask me to apply them.

Get `projectId` from `railway status --json` → `project.id`

### Flow
1. Check for preexisting staged changes before making updates
2. Stage the new changes
3. If no preexisting changes → apply to commit and deploy
4. If preexisting changes → inform user changes are staged, ask if they want to apply

## Error Handling

### Service Not Found
```
Service "foo" not found in project. Available services: api, web, worker
```

### No Staged Changes
```
No patch to apply
```
There are no staged changes to commit. Stage changes first.

### Invalid Configuration
Common issues:
- `buildCommand` and `startCommand` cannot be identical
- `buildCommand` only valid with NIXPACKS builder
- `dockerfilePath` only valid with DOCKERFILE builder

### No Permission
```
You don't have permission to modify this environment. Check your Railway role.
```

### No Linked Project
```
No project linked. Run `railway link` to link a project.
```

## Composability

- **Create service**: Use `service` skill
- **View logs**: Use `deployment-logs` skill
- **Add domains**: Use `domain` skill
- **Deploy local code**: Use `deploy` skill
