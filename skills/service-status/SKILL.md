---
name: service-status
description: Check Railway service deployment status. Use when user asks about service health, deployment state, build status, or before operations that require the service to be running.
---

# Service Status

Check the linked service's deployment state and recent deployment history.

## When to Use

- User asks about service status, health, or deployments
- Before operations that need the service running
- User asks "is my service deployed?" or "what's the deployment status?"
- Checking if a recent deploy succeeded

## Check Service Status

```bash
railway service status --json
```

Returns current deployment status for the linked service.

## Get Deployment History

If service has deployments, get recent history:
```bash
railway deployment list --json --limit 5
```

## Handle Errors

### No Service Linked
If no service is linked to the directory:

> No service linked. Run `railway service` to select a service, or `railway link` to link a project and service.

### No Deployments
If service exists but has no deployments:

> Service exists but has no deployments yet. Deploy with `railway up` or push to the linked GitHub repo.

## Present Status

Show:
- **Service**: name and current status
- **Latest Deployment**: status (SUCCESS, FAILED, DEPLOYING, CRASHED, etc.)
- **Deployed At**: when the current deployment went live
- **Recent Deployments**: last 3-5 with status and timestamps

Example:
```
Service: api (linked)
Status: SUCCESS
Deployed: 2 hours ago

Recent Deployments:
- SUCCESS  2h ago   "fix auth bug"
- SUCCESS  1d ago   "add new endpoint"
- FAILED   2d ago   "broken config"
```

## Deployment Statuses

| Status | Meaning |
|--------|---------|
| SUCCESS | Deployed and running |
| FAILED | Build or deploy failed |
| DEPLOYING | Currently deploying |
| BUILDING | Build in progress |
| CRASHED | Runtime crash |
| REMOVED | Deployment removed |
