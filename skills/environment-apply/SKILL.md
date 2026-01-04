---
name: environment-apply
description: Apply staged Railway environment changes. Use when user says "apply changes", "commit changes", "deploy changes", or after making configuration updates.
---

# Apply Environment Changes

Commit staged changes and trigger deployments.

## When to Use

- User says "apply changes", "commit changes", "deploy changes"
- After staging changes with environment-update (unless batching multiple changes)
- User asks to "deploy" or "redeploy"

## Get Context

```bash
railway status --json
```

Extract `environment.id` from the response.

## Apply Changes Mutation

**Mutation name: `environmentPatchCommitStaged`** (not `environmentStageChanges` or similar)

```graphql
mutation environmentPatchCommitStaged($environmentId: String!, $message: String, $skipDeploys: Boolean) {
  environmentPatchCommitStaged(
    environmentId: $environmentId
    commitMessage: $message
    skipDeploys: $skipDeploys
  )
}
```

Example call:
```bash
skills/lib/railway-api.sh \
  'mutation commitStaged($environmentId: String!, $message: String) {
    environmentPatchCommitStaged(environmentId: $environmentId, commitMessage: $message)
  }' \
  '{"environmentId": "ENV_ID", "message": "add API_KEY variable"}'
```

## Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `environmentId` | String! | - | Environment ID from status |
| `message` | String | null | Short description of changes |
| `skipDeploys` | Boolean | false | Skip deploys (only if user explicitly asks) |

## Commit Message

Keep very short - one sentence max. Describe what and why.

Examples:
- "set build command to fix npm error"
- "add API_KEY variable"
- "increase replicas to 3"
- "update nginx image"

Leave empty if no meaningful description.

## Default Behavior

**Always deploy** unless user explicitly asks to skip deploys. The `skipDeploys`
parameter defaults to `false`.

Only set `skipDeploys: true` if user says:
- "apply without deploying"
- "commit but don't deploy"
- "skip deploys"

## Response

Returns a workflow ID (string) on success. The workflow handles the actual
deployment process.

## Error Handling

### No Staged Changes
```
No patch to apply
```
There are no staged changes to commit. Use environment-update first.

### Permission Denied
User doesn't have permission to apply changes to this environment.

## After Applying

Tell the user:
```
Changes applied and deploying. Workflow: <workflowId>
```
