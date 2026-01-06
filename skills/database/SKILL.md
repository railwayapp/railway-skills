---
name: database
description: Add an official Railway database to a project. Use when user wants to add Postgres, Redis, MySQL, or MongoDB. For other templates (Ghost, Strapi, n8n, etc.), use the templates skill.
---

# Database

Add official Railway database services. These are maintained templates with pre-configured volumes, networking, and connection variables.

For non-database templates, see the `templates` skill.

## When to Use

- User asks to "add a database", "add Postgres", "add Redis", etc.
- User needs a database for their application
- User asks about connecting to a database

## Available Databases

| Database | Template Code |
|----------|---------------|
| PostgreSQL | `postgres` |
| Redis | `redis` |
| MySQL | `mysql` |
| MongoDB | `mongodb` |

## Prerequisites

Get project context:
```bash
railway status --json
```

Extract:
- `id` - project ID
- `environments.edges[0].node.id` - environment ID

Get workspace ID (not in status output):
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'query getWorkspace($projectId: String!) {
    project(id: $projectId) { workspaceId }
  }' \
  '{"projectId": "PROJECT_ID"}'
```

## Adding a Database

### Step 1: Fetch Template

```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'query template($code: String!) {
    template(code: $code) {
      id
      name
      serializedConfig
    }
  }' \
  '{"code": "postgres"}'
```

This returns the template's `id` and `serializedConfig` needed for deployment.

### Step 2: Deploy Template

```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'mutation deployTemplate($input: TemplateDeployV2Input!) {
    templateDeployV2(input: $input) {
      projectId
      workflowId
    }
  }' \
  '{
    "input": {
      "templateId": "TEMPLATE_ID",
      "serializedConfig": SERIALIZED_CONFIG,
      "projectId": "PROJECT_ID",
      "environmentId": "ENVIRONMENT_ID",
      "workspaceId": "WORKSPACE_ID"
    }
  }'
```

**Important:** `serializedConfig` is the exact object from the template query, not a string.

## Connecting to the Database

After deployment, other services connect using reference variables.

### Backend Services (Server-side)

Use the private/internal URL for server-to-server communication:

| Database | Variable Reference |
|----------|-------------------|
| PostgreSQL | `${{Postgres.DATABASE_URL}}` |
| Redis | `${{Redis.REDIS_URL}}` |
| MySQL | `${{MySQL.MYSQL_URL}}` |
| MongoDB | `${{MongoDB.MONGO_URL}}` |

### Frontend Applications

**Important:** Frontends run in the user's browser and cannot access Railway's private network. They must use public URLs or go through a backend API.

For direct database access from frontend (not recommended):
- Use the public URL variables (e.g., `${{MongoDB.MONGO_PUBLIC_URL}}`)
- Requires TCP proxy to be enabled

Better pattern: Frontend → Backend API → Database

## Example: Add PostgreSQL

```bash
# 1. Get context
railway status --json
# Extract project.id and environment.id

# 2. Get workspace ID
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'query { project(id: "proj-id") { workspaceId } }' '{}'

# 3. Fetch Postgres template
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'query { template(code: "postgres") { id serializedConfig } }' '{}'

# 4. Deploy template
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'mutation deploy($input: TemplateDeployV2Input!) {
    templateDeployV2(input: $input) { projectId workflowId }
  }' \
  '{"input": {"templateId": "...", "serializedConfig": {...}, "projectId": "...", "environmentId": "...", "workspaceId": "..."}}'
```

### Then Connect From Another Service

Use `environment` skill to add the variable reference:

```json
{
  "services": {
    "<backend-service-id>": {
      "variables": {
        "DATABASE_URL": { "value": "${{Postgres.DATABASE_URL}}" }
      }
    }
  }
}
```

## Response

Successful deployment returns:
```json
{
  "data": {
    "templateDeployV2": {
      "projectId": "e63baedb-e308-49e9-8c06-c25336f861c7",
      "workflowId": "deployTemplate/project/e63baedb-e308-49e9-8c06-c25336f861c7/xxx"
    }
  }
}
```

## What Gets Created

Each database template creates:
- A service with the database image
- A volume for data persistence
- Environment variables for connection strings
- TCP proxy for external access (where applicable)

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Template not found | Invalid template code | Use: `postgres`, `redis`, `mysql`, `mongodb` |
| Permission denied | User lacks access | Need DEVELOPER role or higher |
| Project not found | Invalid project ID | Run `railway status --json` for correct ID |

## Composability

- **Connect services**: Use `environment` skill to add variable references
- **View database service**: Use `service` skill
- **Check logs**: Use `deployment-logs` skill
