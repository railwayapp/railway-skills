# Configuration in source control

Use Infrastructure as Code for project configuration. Keep one authoring file and never manage a service with both IaC and legacy Config as Code.

## Choose the model

TypeScript IaC is generally available. Python and Go authoring are in beta. Preserve an existing `.railway/railway.ts`, `.railway/railway.py`, or `.railway/railway.go`; do not switch languages based on the app's `package.json`, `go.mod`, or framework. With no existing authoring file, `config init` and `config pull` default to TypeScript even for non-TypeScript apps. `config init` and `config pull` have no language flag: the CLI picks the language only from an existing authoring file. To honor an explicit Python/Go preference on a fresh project, create an empty `.railway/railway.py` or `.railway/railway.go` first, then run `config pull` so the import is emitted in that language. `config migrate --lang py|go` emits Python/Go only when translating legacy `railway.json`/`railway.toml`.

`railway.json` and `railway.toml` are deprecated. New services cannot opt into Config as Code; existing files stop being read on **2026-12-01**. Do not create them as a fallback. For an existing legacy service, use the migration workflow below; if the user requests a temporary legacy edit, explain the cutoff and keep its current format.

| Model | Scope | Applies when |
|---|---|---|
| `.railway/railway.ts`, `.py`, or `.go` | Project/environment: services, databases, buckets, volumes, variables, replicas, domains, and canvas groups | `railway config apply` applies the project plan |
| Existing `railway.json` / `railway.toml` | One legacy service's build and deploy settings | Read during deployments until the cutoff; overrides dashboard values for that deployment |

## Infrastructure as Code

Keep exactly one of these files:

```text
.railway/railway.ts
.railway/railway.py
.railway/railway.go
```

`railway config init` and `railway config pull` also create `.railway/README.md`. Railway agent setup installs the shared `use-railway` skill; config commands do not need or create a project-local skill.

Install the matching authoring package in the config's package environment: `npm install railway`, `pip install railway-sdk`, or `go get github.com/railwayapp/railway-go-sdk`. Python/Go imports can generate `.railway/requirements.txt` or `.railway/go.mod`; use those when present. CLI 5.42+ evaluates the graph natively, but still needs the language runtime and SDK to evaluate authoring code. `--runner` is an optional legacy TypeScript runner override, not a prerequisite.

### Core rules

1. Express Railway product intent, not internal API details.
2. Do not write Railway UUIDs into the authoring file.
3. Do not write `EnvironmentConfigPatch`, `ServiceInstance`, Backboard internals, or generated Railway domains into source.
4. Prefer helpers such as `service()`, `postgres()`, `redis()`, `mysql()`, `mongo()`, `bucket()`, `volume()`, `group()`, `github()`, and `image()`.
5. Use `service.env.VARIABLE` and `database.env.VARIABLE` for references.
6. Keep secrets out of source. Imports use `preserve()` by default for existing variables; omit them only when a smaller import is intended.
7. Prefer product DSL names such as `domains`, `replicas`, and `group`; avoid internal names such as `customDomains` and `multiRegionConfig`.
8. Do not add platform defaults unless the user explicitly wants them.
9. After editing the authoring file, run `railway config plan`.
10. Do not run `railway config apply` unless the user explicitly asks.
11. Never use `railway config apply --yes` or `--confirm-destructive` from an agent session without explicit user approval for the exact plan.

### Initialize or import

```bash
railway config init                         # TypeScript by default; preserve existing language
railway config init --force                 # overwrite existing generated files
railway config pull                         # import the linked project
railway config pull --force                 # overwrite the existing authoring file
railway config pull --omit-preserved-variables # omit unknown variable values
railway config pull --json                  # print current graph instead of writing files
railway config pull --agent                 # ask an agent to clean the import afterward
railway config pull --include-variables     # decrypt and inline non-sealed values
```

Use `--include-variables` only when writing those values to source is intended: it includes non-sealed secrets too. Sealed values remain `preserve()`. A normal import should produce a no-change plan; inspect any diff before applying.

Plan/apply discover the nearest `.railway/railway.{ts,py,go}` by walking up from the current directory. `--file <path>` overrides that selection. Run init/pull/migrate from the intended project root. Config commands do not expose `--project`/`--environment` selectors: verify the link or use `railway link --project <id> --environment <env>` before noninteractive work. Interactive commands can prompt for missing context.

### Authoring

Import the helpers needed by the project:

```ts
import {
  bucket,
  defineRailway,
  github,
  group,
  image,
  mongo,
  mysql,
  postgres,
  preserve,
  project,
  redis,
  service,
  volume,
} from "railway/iac";
```

Common resource patterns:

```ts
const db = postgres("postgres");

const api = service("api", {
  source: github("owner/repo", { branch: "main" }),
  build: "pnpm build",
  preDeploy: "pnpm db:migrate",
  start: "pnpm start",
  env: {
    DATABASE_URL: db.env.DATABASE_URL,
    INTERNAL_TOKEN: preserve(),
  },
  domains: ["api.example.com"],
  replicas: 3,
  volumeMounts: {
    "/data": volume("uploads", { sizeMB: 4096 }),
  },
});

const worker = service("worker", {
  source: image("ghcr.io/acme/worker:latest"),
  env: {
    API_HOST: api.env.RAILWAY_PRIVATE_DOMAIN,
    API_TOKEN: api.env.INTERNAL_TOKEN,
  },
});

const media = bucket("media", { region: "iad" });
const backend = group("Backend", [api, worker, db]);
```

A traced service also carries `tracing: { enabled: true, autoInstrumentation: true }`, which `config pull` renders and `service()` passes through to the CLI. This needs CLI 5.63.0 or newer (an older CLI drops the block on compile and never diffs it) and `railway` 3.12.0+, `railway-sdk` 0.3.0+ or the Go SDK v0.3.0+. An older SDK drops the block too, and on CLI 5.63.0+ that makes every plan against a traced service propose removing `tracing`; see [Infrastructure as code in tracing.md](tracing.md#infrastructure-as-code) before applying one.

Advanced placement can map regions to replica counts:

```ts
const web = service("web", {
  replicas: {
    "us-west2": 2,
    "europe-west4": 1,
  },
});
```

Return every managed resource from the project:

```ts
export default defineRailway(() => {
  const db = postgres("postgres");
  const web = service("web", {
    env: { DATABASE_URL: db.env.DATABASE_URL },
  });

  return project("my-app", {
    resources: [db, web],
  });
});
```

### Plan

Always plan after editing and before applying:

```bash
railway config plan
railway config plan --json
railway config plan --verbose
railway config plan --show-values
railway config plan --detailed-exit-code
```

Plan output summarizes changes in Terraform style:

```text
Plan: 1 to add, 0 to change, 0 to destroy
```

Variable values are redacted by default. Use `--show-values` only when the user accepts the secret exposure risk. For CI drift checks, `--detailed-exit-code` returns `0` for no changes, `2` for pending changes, and another non-zero code for errors.

### Apply

```bash
railway config apply
railway config apply --yes
railway config apply --yes --confirm-destructive
railway config apply --json --yes --confirm-destructive
```

Ordinary `apply` evaluates a fresh plan. Changes to the environment between planning inside that invocation and applying are rejected. In non-interactive or agent sessions, destructive changes require `--confirm-destructive` in addition to `--yes` or `--json`; add it only after the user explicitly approves the exact destructive impact.

### Apply the reviewed plan in CI

CLI 5.45.1+ can save the evaluated change set and apply that exact artifact:

```bash
railway config plan --out railway-plan.json
railway config apply --plan railway-plan.json --yes
```

Review the first command's diff before authorizing the apply. Store the artifact outside `.railway/` because that directory's source tree is pinned. The artifact contains the change set, environment ID and config etag, and source tree identity. `apply --plan` does not reevaluate the authoring code; it rejects changed source or remote state rather than quietly generating another plan. Keep the same CLI version and source checkout between jobs. Use `--source-tree` on `plan` only when CI deliberately supplies the source identity. Treat plan artifacts as potentially secret-bearing even when terminal diffs are redacted.

When a saved plan is stale, create and review a replacement. Destructive saved plans still require `--confirm-destructive`. For maintained CI integration, use [railwayapp/config](https://github.com/railwayapp/config).

### Review checklist

Before applying, confirm:

- The latest plan shows only expected changes.
- The user reviewed the plan and explicitly requested apply.
- Secrets are not replaced with literal placeholders.
- Existing Railway-managed variables are omitted or use `preserve()` when they should remain untouched.
- Custom domains use `domains`, not networking internals.
- Scaling uses `replicas`, not `multiRegionConfig`.
- No generated Railway service domains or Railway UUIDs are committed.

### Troubleshoot IaC

- **Service is already managed by Config as Code**: use migration below; deleting the file alone does not clear its Railway Config File setting.
- **Plan shows secrets as hidden**: expected. Use `--show-values` only with user approval.
- **Apply says the plan is stale**: run a new plan, inspect it, then apply again only if requested.
- **Destructive apply is blocked**: get explicit approval for the exact plan before adding `--confirm-destructive`.
- **Imported variables use `preserve()`**: this is the default, including readable values; it retains the remote value without putting it into source.
- **Missing Railway package**: install the SDK for the existing authoring language in its runtime environment; do not replace the config language to work around the error.
- **Generated code is too literal**: simplify the authoring file, then run another plan.

## Migrate legacy Config as Code

Use CLI **5.49.1 or newer**: its TypeScript migration and all-language pull fixes preserve `preDeployCommand` as the first-class `preDeploy` field. Earlier TypeScript migration output could silently omit a database migration command.

Start with a dry-run from the repository root:

```bash
railway config migrate
railway config migrate --service api
railway config migrate --lang py
railway config migrate --lang go
```

The default emits proposed TypeScript without writing files or clearing remote settings. `--service` selects a service when multiple configs are found; with one file it can name the emitted service. Inspect the discovered paths and service mapping in a monorepo. Single-service migration may emit a named partial rather than claim the whole project; retain that ownership boundary when merging it into existing IaC.

In v5.49.1, Python/Go **migration** emits only build/start commands and the healthcheck path. Manually carry over other intended settings, including pre-deploy commands, replicas, and healthcheck timeouts, before applying the resulting IaC. A successful migration command is not proof of a lossless translation in any language; compare the original files and plan.

For an authorized migration, write the result and clear the discovered services' Railway Config File settings:

```bash
railway config migrate --apply
railway config migrate --apply --delete-files
```

`--apply` here writes source and changes remote config-file settings; it does **not** apply the resulting IaC project plan. `--delete-files` additionally removes discovered legacy files and requires `--apply`. If an authoring file already exists, merge the dry-run output into it instead of using `--force` to overwrite unrelated resources. Preserve the language with `--lang` when needed; migration defaults to `ts`.

Before completing the migration:

- Compare build/start/pre-deploy commands, health checks, regions/replicas, and environment overrides with the original files. Do not assume every legacy field was translated.
- Preserve secrets and review the service identities and ownership scope.
- Run `railway config plan`; inspect unexpected removals or changes, then apply only within the user's authorized scope.
- Check for remaining legacy files and custom Railway Config File paths so deployments do not retain dual ownership.

For a requested temporary edit to an existing legacy service, retain its format, validate against the [Config as Code reference](https://docs.railway.com/config-as-code/reference), and explain the 2026-12-01 cutoff. Config as Code has deployment-time precedence over dashboard settings; a deployment is needed for edits to take effect. Keep variables and secrets in Railway variables.

## Validated against

- Docs: [Infrastructure as Code](https://docs.railway.com/infrastructure-as-code), [IaC reference](https://docs.railway.com/infrastructure-as-code/reference), [Config as Code](https://docs.railway.com/config-as-code)
- CLI source (v5.49.1): [config/mod.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/config/mod.rs), [config/migrate.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/config/migrate.rs), [authoring.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/config/authoring.rs), [eval.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/iac/eval.rs), [saved_plan.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/iac/saved_plan.rs)
- IaC SDK sources for the `tracing` block: railway-ts-sdk `src/iac/sdk.ts` and `src/iac/schema.ts` (`ServiceTracing`; `railway` 3.12.0), railway-py-sdk `_normalize_tracing` (`railway-sdk` 0.3.0), railway-go-sdk `serviceNode` (v0.3.0); CLI 5.63.0 `src/iac/compiler.rs` and `src/iac/change_set.rs`
