---
name: projects
description: Manage Railway projects. Use when user wants to list all projects, switch projects, rename project, enable/disable PR deploys, make project public/private, or modify project settings.
allowed-tools: Bash(railway:*)
---

# Project Management

List, switch, and configure Railway projects.

## When to Use

- User asks "show me all my projects" or "what projects do I have"
- User asks about projects across workspaces
- User asks "what workspaces do I have"
- User wants to switch to a different project
- User asks to rename a project
- User wants to enable/disable PR deploys
- User wants to make a project public or private
- User asks about project settings

## List Projects

```bash
railway list --json
```

Returns all projects across **all workspaces** with IDs, names, and environments.

## List Workspaces

```bash
railway whoami --json
```

Returns user info including all workspaces the user belongs to.

## Switch Project

Link a different project to the current directory:

```bash
railway link -p <project-id-or-name>
```

Or interactively:

```bash
railway link
```

After switching, use `status` skill to see project details.

## Update Project

Modify project settings via GraphQL API.

### Get Project ID

```bash
railway status --json
```

Extract `project.id` from the response.

### Update Mutation

```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'mutation updateProject($id: String!, $input: ProjectUpdateInput!) {
    projectUpdate(id: $id, input: $input) { name prDeploys isPublic botPrEnvironments }
  }' \
  '{"id": "PROJECT_ID", "input": {"name": "new-name"}}'
```

### ProjectUpdateInput Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | String | Project name |
| `description` | String | Project description |
| `isPublic` | Boolean | Make project public/private |
| `prDeploys` | Boolean | Enable/disable PR deploys |
| `botPrEnvironments` | Boolean | Enable Dependabot/Renovate PR environments |

### Examples

**Rename project:**
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh '<mutation>' '{"id": "uuid", "input": {"name": "new-name"}}'
```

**Enable PR deploys:**
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh '<mutation>' '{"id": "uuid", "input": {"prDeploys": true}}'
```

**Make project public:**
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh '<mutation>' '{"id": "uuid", "input": {"isPublic": true}}'
```

**Multiple fields:**
```bash
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh '<mutation>' '{"id": "uuid", "input": {"name": "new-name", "prDeploys": true}}'
```

## Composability

- **View project details**: Use `status` skill
- **Create new project**: Use `new` skill
- **Manage environments**: Use `environment` skill

## Error Handling

### Not Authenticated
```
Not authenticated. Run `railway login` first.
```

### No Projects
```
No projects found. Create one with `railway init`.
```

### Permission Denied
```
You don't have permission to modify this project. Check your Railway role.
```

### Project Not Found
```
Project "foo" not found. Run `railway list` to see available projects.
```
