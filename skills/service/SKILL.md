---
name: service
description: Manage Railway services. Use when user asks about service status, wants to rename a service, change service icon, or link a service.
---

# Service Management

Check service status and update service properties.

## When to Use

- User asks about service status, health, or deployments
- User wants to rename a service
- User wants to change service icon
- User asks "is my service deployed?"
- User wants to link a different service

## Check Service Status

```bash
railway service status --json
```

Returns current deployment status for the linked service.

### Deployment History

```bash
railway deployment list --json --limit 5
```

### Present Status

Show:
- **Service**: name and current status
- **Latest Deployment**: status (SUCCESS, FAILED, DEPLOYING, CRASHED, etc.)
- **Deployed At**: when the current deployment went live
- **Recent Deployments**: last 3-5 with status and timestamps

### Deployment Statuses

| Status | Meaning |
|--------|---------|
| SUCCESS | Deployed and running |
| FAILED | Build or deploy failed |
| DEPLOYING | Currently deploying |
| BUILDING | Build in progress |
| CRASHED | Runtime crash |
| REMOVED | Deployment removed |

## Update Service

Update service name or icon via GraphQL API.

### Get Service ID

```bash
railway status --json
```

Extract `service.id` from the response.

### Update Name

```bash
skills/lib/railway-api.sh \
  'mutation updateService($id: String!, $input: ServiceUpdateInput!) {
    serviceUpdate(id: $id, input: $input) { id name }
  }' \
  '{"id": "SERVICE_ID", "input": {"name": "new-name"}}'
```

### Update Icon

```bash
skills/lib/railway-api.sh \
  'mutation updateService($id: String!, $input: ServiceUpdateInput!) {
    serviceUpdate(id: $id, input: $input) { id icon }
  }' \
  '{"id": "SERVICE_ID", "input": {"icon": "🚀"}}'
```

### ServiceUpdateInput Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | String | Service name |
| `icon` | String | Service icon (emoji) |

## Link Service

Switch the linked service for the current directory:

```bash
railway service link
```

Or specify directly:

```bash
railway service link <service-name>
```

## Composability

- **Create service**: Use `service-create` skill
- **Delete service**: Use `environment-update` skill with `isDeleted: true`
- **View logs**: Use `deployment-logs` skill
- **Deploy**: Use `deploy` skill

## Error Handling

### No Service Linked
```
No service linked. Run `railway service link` to link a service.
```

### No Deployments
```
Service exists but has no deployments yet. Deploy with `railway up`.
```

### Service Not Found
```
Service "foo" not found. Check available services with `railway status`.
```
