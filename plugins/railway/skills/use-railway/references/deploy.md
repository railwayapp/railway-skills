# Deploy

Ship code, manage releases, and configure builds.

## Deploy code

### Standard deploy

```bash
railway up --detach -m "<release summary>"
```

`--detach` returns immediately instead of streaming build logs. Without it, the deploy blocks execution until the build finishes. Always include `-m` with a release summary for auditability.

### Watch the build

```bash
railway up --ci -m "<release summary>"
```

`--ci` streams build logs and exits when the build completes. Use this when the user wants to see build output or when you need to triage build failures immediately.

### Targeted deploy

When multiple services exist, target explicitly:

```bash
railway up --service <service> --environment <environment> --detach -m "<summary>"
```

### Deploy to an unlinked project

For CI or cross-project deploys where the directory isn't linked:

```bash
railway up --project <project-id> --environment <environment> --detach -m "<summary>"
```

`--project` requires `--environment`. Railway needs both to resolve context.

## Manage releases

### Redeploy and restart

```bash
railway redeploy --service <service> --yes              # redeploy the latest deployment
railway redeploy --service <service> --from-source --yes # pull latest commit or image
railway restart --service <service> --yes                # restart without rebuilding
```

Redeploy recreates the latest deployment without uploading local code. Use `--from-source` when the service is linked to a repo or image and you need Railway to pull the latest configured source. Restart only restarts the running container. Use restart when the code hasn't changed but the service needs a fresh process.

### Remove latest deployment

```bash
railway down --service <service> --yes
```

This removes the latest successful deployment but doesn't delete the service. To delete a service entirely, use `railway service delete`.

### Delete a service

Use service deletion when the user wants to remove the service itself:

```bash
railway service delete --service <service> --environment <environment> --yes --json
```

Deleting a service is destructive. Confirm the target service and environment before running it.

## Deployment history and logs

```bash
railway deployment list --service <service> --limit 20 --json
railway logs --service <service> --lines 200 --json              # runtime logs
railway logs --service <service> --build --lines 200 --json      # build logs
railway logs --latest --lines 200 --json                         # latest deployment
```

In an interactive terminal, `railway logs` streams indefinitely when no bounding flags are given. Always use `--lines`, `--since`, or `--until` to get a bounded fetch for agent workflows.

## Build configuration

Railway uses Railpack as the default builder. It detects language and framework from repo contents and assembles a build plan automatically.

### Builder selection

Three builder options, set via service config:

- **RAILPACK** auto-detects language and framework, builds from source (default)
- **NIXPACKS** is the legacy builder. Use RAILPACK instead.
- **DOCKERFILE** uses a Dockerfile you provide

```bash
railway environment edit --service-config <service> build.builder RAILPACK
railway environment edit --service-config <service> build.builder DOCKERFILE
railway environment edit --service-config <service> build.dockerfilePath "docker/Dockerfile.prod"
```

### Build and start commands

Override when auto-detection gets it wrong:

```bash
railway environment edit --service-config <service> build.buildCommand "npm run build"
railway environment edit --service-config <service> deploy.startCommand "npm start"
```

Common reasons to override: wrong package manager detected, multiple build targets in a monorepo, framework-specific output paths.

### Railpack environment variables

Control Railpack behavior by setting these as service variables:

| Variable | Purpose |
|---|---|
| `RAILPACK_NODE_VERSION` | Pin Node.js version (e.g., `20`, `22.1.0`) |
| `RAILPACK_PYTHON_VERSION` | Pin Python version (e.g., `3.12`) |
| `RAILPACK_GO_BIN` | Go binary name to build |
| `RAILPACK_STATIC_FILE_ROOT` | Directory for static site output (e.g., `dist`, `build`) |
| `RAILPACK_SPA_OUTPUT_DIR` | SPA output directory with client-side routing support |
| `RAILPACK_PACKAGES` | Additional system packages for the build |
| `RAILPACK_BUILD_APT_PACKAGES` | Apt packages available during build only |
| `RAILPACK_DEPLOY_APT_PACKAGES` | Apt packages available at runtime only |

For full Railpack documentation including language-specific detection, config files, and framework support: https://railpack.com/llms.txt

### Static sites

Railpack detects static sites from `Staticfile`, `index.html`, or `RAILPACK_STATIC_FILE_ROOT` and serves them with a built-in static file server. If the build outputs to a non-standard directory (for example, `dist/`, `build/`), set `RAILPACK_STATIC_FILE_ROOT` as a variable so Railpack knows where to find the output.

## Monorepo patterns

### Isolated monorepo

When services don't share code, isolate each with its own root directory:

```bash
railway environment edit --service-config <service> source.rootDirectory "/packages/api"
```

Each service sees only its subdirectory. This approach is clean but breaks if services import from shared packages.

### Shared monorepo

When services depend on shared packages or root-level workspace config, keep the full repo context and scope via build/start commands instead:

```bash
# pnpm workspaces
railway environment edit --service-config <service> build.buildCommand "pnpm --filter api build"
railway environment edit --service-config <service> deploy.startCommand "pnpm --filter api start"

# yarn workspaces
railway environment edit --service-config <service> build.buildCommand "yarn workspace api build"
railway environment edit --service-config <service> deploy.startCommand "yarn workspace api start"

# bun workspaces
railway environment edit --service-config <service> build.buildCommand "bun run --filter api build"
railway environment edit --service-config <service> deploy.startCommand "bun run --filter api start"

# turborepo (works with any package manager)
railway environment edit --service-config <service> build.buildCommand "npx turbo run build --filter=api"
railway environment edit --service-config <service> deploy.startCommand "npx turbo run start --filter=api"
```

Don't set a restrictive `rootDirectory` in this case. The build needs access to the workspace root.

### Watch paths

Prevent unrelated package changes from redeploying every service:

```bash
railway environment edit --service-config <service> build.watchPatterns '["packages/api/**","packages/shared/**"]'
```

### Common monorepo pitfalls

- **Using `rootDirectory` with shared imports**: if service A imports from `packages/shared/`, setting `rootDirectory: "/packages/a"` hides the shared code. Use the shared monorepo pattern instead.
- **Forgetting watch paths**: without watch paths, every push redeploys all services, even when only one package changed.
- **Wrong filter target**: `pnpm --filter api` uses the `name` field in each package's `package.json`, not the directory name. Verify the package name matches.

## Troubleshoot deploys

- **No project/service context**: run `railway link` or pass `--project` with `--environment`
- **Build fails before compile**: check dependency graph, lockfiles, and whether the right builder is selected
- **Build succeeds but app crashes**: verify start command and required runtime variables
- **Wrong files in build**: check root directory and watch patterns
- **`railway down` treated as delete**: `down` only removes the latest deployment. For service deletion, use `railway service delete`
- **Wrong Node/Python version detected**: set `RAILPACK_NODE_VERSION` or `RAILPACK_PYTHON_VERSION` as a service variable to pin the version
- **Missing system package at runtime**: add the package to `RAILPACK_DEPLOY_APT_PACKAGES`

## Validated against

- Docs: [up.md](https://docs.railway.com/cli/up), [deploying.md](https://docs.railway.com/cli/deploying), [deployment.md](https://docs.railway.com/cli/deployment), [redeploy.md](https://docs.railway.com/cli/redeploy), [service.md](https://docs.railway.com/cli/service), [down.md](https://docs.railway.com/cli/down), [railpack.md](https://docs.railway.com/builds/railpack), [monorepo.md](https://docs.railway.com/deployments/monorepo)
- CLI source: [up.rs](https://github.com/railwayapp/cli/blob/v4.58.0/src/commands/up.rs), [deployment.rs](https://github.com/railwayapp/cli/blob/v4.58.0/src/commands/deployment.rs), [down.rs](https://github.com/railwayapp/cli/blob/v4.58.0/src/commands/down.rs), [redeploy.rs](https://github.com/railwayapp/cli/blob/v4.58.0/src/commands/redeploy.rs), [restart.rs](https://github.com/railwayapp/cli/blob/v4.58.0/src/commands/restart.rs), [service.rs](https://github.com/railwayapp/cli/blob/v4.58.0/src/commands/service.rs)
