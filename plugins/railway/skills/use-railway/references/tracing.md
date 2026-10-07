# Tracing

Trace a request from Railway's edge through a service and into the services it calls. Tracing is switched on per service **and per environment**: with the `set-service-tracing` MCP tool, `railway trace enable`, or the **Tracing setup** drawer on the project's **Traces** tab. Read the result with `list-traces` and `get-trace`, or on the same tab.

Tracing is a preview feature. If the project has no **Traces** tab, the account needs **Tracing** enabled in Priority Boarding first.

## What Railway records without code changes

- **Edge and proxy spans.** For every sampled request to a traced service's public domain, Railway's edge records a server span (method, path, status, cache result, upstream) and the regional proxy adds a span for its hop. The edge forwards a W3C `traceparent` header to the service and stamps `x-railway-trace-id` on the response.
- **Automatic instrumentation (OBI).** A per-service switch that attaches eBPF probes to the service's Node.js, Go, Python, Ruby, or Java processes on the host. It exports server spans for incoming HTTP/gRPC requests, client spans for plaintext outgoing calls, and spans for database and cache protocols it decodes. No SDK, no redeploy.

Spans from inside the service only appear once the service exports them, through automatic instrumentation or an OpenTelemetry SDK. A service without a public domain never gets edge spans; only what it exports itself shows up, joined to traces other services propagate to it over the private network.

## Enable tracing

Tracing is two switches on each service instance, so they are set per service and per environment. `tracingEnabled` makes the edge trace requests to the service and gives its next deploy the OpenTelemetry variables below; `autoInstrumentationEnabled` attaches eBPF probes to the service's processes and only does anything while tracing is on. There is no project-wide default and no sample rate: every client-facing request to a traced service is traced. Enabling a service in `production` says nothing about `staging`, so check and set each environment the user cares about.

**Dashboard:** open the **Traces** tab → **Tracing setup**. The drawer lists the services of the environment the dashboard is on (the subtitle names it); each row's **Traced** switch and **Automatic instrumentation** / **Manual instrumentation** choice apply to that environment only. Switch environment to configure another. The service's **Settings → Tracing** section links to the same drawer.

**Agent path:** two MCP tools read and change these settings, and `railway trace` does the same from the CLI. Resolve IDs from the URL or `railway status --json` first, and read before writing. Both tools use the `production` environment when `environmentId` is omitted, so pass it whenever the user is looking at another environment. On a Railway cloud agent in a dashboard chat session the `railway` CLI is unauthenticated, so resolve IDs with `list-services` and stay on the MCP tools throughout.

| Tool | Access | Purpose |
|---|---|---|
| `get-tracing` | viewer | The `environment` and, per service in it, `tracingEnabled`, `autoInstrumentationEnabled` and whether it is `autoInstrumentationActive` (both on). Pass `serviceId` for one service, omit it for every service in the environment |
| `set-service-tracing` | member | `tracingEnabled` and `autoInstrumentationEnabled` for one service in one environment. Each is optional and independent; omit what should stay as it is. Returns the service's state in that environment |

Both take `projectId` and an optional `environmentId`. `describe-service` reports the same tracing state for one service in the environment it was asked about.

```text
Get tracing for project 6adb5ae3-0e3a-4ead-b42c-1fd36f217ffb in environment <environment-id>
```

```text
Set service tracing for project 6adb5ae3-0e3a-4ead-b42c-1fd36f217ffb, service <service-id>, environment <environment-id>: tracingEnabled true
```

```text
Set service tracing for project 6adb5ae3-0e3a-4ead-b42c-1fd36f217ffb, service <service-id>, environment <environment-id>: autoInstrumentationEnabled true
```

`set-service-tracing` warns when it switches auto-instrumentation on for a service whose tracing is off: the switch does nothing until tracing is enabled too. Without Railway MCP or `railway trace`, the public `serviceInstanceUpdate` mutation sets the same fields through `railway api`, and the environment's service instances carry them for reading; see [request.md](request.md). That fallback needs an authenticated CLI, which a cloud agent's chat session does not have.

```bash
railway api \
  'mutation traceInstance($serviceId: String!, $environmentId: String!) {
    serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId,
      input: { tracingEnabled: true, autoInstrumentationEnabled: false })
  }' \
  --variables '{"serviceId":"<service-id>","environmentId":"<environment-id>"}'

railway api \
  'query tracing($id: String!) {
    environment(id: $id) { serviceInstances { edges { node {
      serviceId serviceName tracingEnabled autoInstrumentationEnabled
    } } } }
  }' \
  --variables '{"id":"<environment-id>"}'
```

The older `Project` and `Service` tracing fields still exist as deprecated stubs: `projectUpdate(tracingEnabled)` switches every instance in the project, `serviceUpdate(tracingEnabled)` the service in every environment, and `tracingSampleRate` is ignored. Don't use them; they flip environments the user didn't mention.

**CLI:** `railway trace` (aliases `traces`, `tracing`) sets the same switches, in one environment at a time: the linked one, or `--environment <name>`. This needs a CLI release newer than 5.62.1. An older CLI still runs `railway trace enable`, but through the deprecated service field, so it sets the service in every environment, and its `inherit`, `--project-default` and `--sample-rate` belong to the model that is gone. Use the CLI when the user works in a linked repo or wants exact command output; on a cloud agent's chat session stay on MCP.

```bash
railway trace status                                    # linked service in the linked environment
railway trace status --all                              # every service in the environment, last edge/app span
railway trace enable --service <service>                # trace one service in the linked environment
railway trace enable --auto-instrument                  # tracing plus OBI for the linked service
railway trace enable --all --environment staging        # every service in staging
railway trace disable --auto-instrument                 # tracing and OBI off
```

`--all` and `--service` are mutually exclusive. Pass `--project <id> --environment <name>` together when nothing is linked. `--json` prints one document with `environment: { id, name }` and the service state. Changing tracing needs a user or workspace token; a project token (`RAILWAY_TOKEN`) can only read. The CLI has no switch for auto-instrumentation alone: `railway trace disable --auto-instrument` followed by `railway trace enable` leaves tracing on and OBI off, or use `set-service-tracing` with only `autoInstrumentationEnabled`.

What happens next:

- The edge starts tracing requests to the service's domains in that environment within seconds.
- Automatic instrumentation reaches the running containers within about a minute. No redeploy.
- The OpenTelemetry variables below are added on the **next deploy** in that environment. An app with an SDK exports nothing until it is redeployed: `railway redeploy --service <service> --yes`.

### Infrastructure as code

The environment config carries the same two switches as `services[<id>].tracing: { enabled, autoInstrumentation }`, so tracing is part of what `railway config pull`, `plan` and `apply` manage (see [iac.md](iac.md)). Railway serialises only the switches that are on: an untraced service has no `tracing` block, and `enabled: false` is the same as leaving it out. `railway config pull` renders the block for a traced service:

```ts
const api = service("api", {
  source: github("owner/repo", { branch: "main" }),
  tracing: { enabled: true, autoInstrumentation: true },
});
```

A plan shows a tracing change as a `resource.update` with `field: "tracing"`. Turning `enabled` on or off has `deployEffect: deploy`, because the `OTEL_*` variables land with a deploy; an `autoInstrumentation`-only change is `deployEffect: none` and reaches the running containers live. A new service carries `tracing` on its create.

**Setting `tracing` in config.** `service()` passes the block through to the CLI as `tracing: { enabled?, autoInstrumentation? }`, both optional booleans: `tracing: { enabled: true }` in TypeScript (typed as `ServiceTracing`), `tracing={"enabled": True}` in Python, `"tracing": map[string]any{"enabled": true}` in Go. `fn()` takes it too; `database()` and the database helpers don't, since databases never carry tracing. `{ enabled: false }`, `null` and no block all plan the same.

Two version requirements, both to check before writing the block:

- **CLI 5.63.0 or newer.** An older CLI drops `tracing` on compile and never diffs it, so the setting silently doesn't apply, but nothing proposes removing it either.
- **`railway` 3.12.0+, `railway-sdk` 0.3.0+ or the Go SDK v0.3.0+.** All three accept the block the same way. An older SDK drops it before the CLI sees it; `npm ls railway`, `pip show railway-sdk` or the `require` line in `.railway/go.mod` shows which one is installed.

**The hazard is an old SDK on a new CLI.** The SDK drops the block, the compiled config has no `tracing`, and `railway config plan` against a traced service shows a `tracing` update with `after: null` and `deployEffect: deploy`; `railway config apply` then turns tracing off and redeploys. So:

- If the SDK is too old, upgrade it before adding `tracing` to config, or set tracing with `set-service-tracing`, `railway trace enable` or the dashboard and say why.
- Read every plan for a `tracing` removal nobody authored, and don't apply one. Upgrade the SDK and plan again. `railway config pull` reproduces the block, but an old SDK drops it again on the next plan, so pulling alone doesn't fix it.
- If an apply already disabled tracing, re-enable it with `set-service-tracing` or `railway trace enable`; the redeploy for the variables follows.

## Choose how the service exports spans

**Recommend the OpenTelemetry SDK.** Spans the service exports itself are much higher quality than what automatic instrumentation can recover from outside the process: they carry the route, the query, the business identifiers and the errors the code knows about; they nest under handler-level spans, so the trace shows which step of a request took the time instead of a flat list of calls; they continue the trace through queue consumers, cron work and TLS callees; and they work in any language. Automatic instrumentation is the fallback for a service whose code can't be changed right now, or a first look while the SDK is being added. Present it as a stopgap, not the destination. When a user asks to "instrument my app", default to the SDK unless they ask for the no-code path.

| | Automatic instrumentation (OBI) | OpenTelemetry SDK |
|---|---|---|
| Code changes | None | Install the SDK, load it before the app serves requests |
| Takes effect | About a minute after enabling, no redeploy | Next deploy |
| Runtimes | Node.js, Go, Python, Ruby, Java. Not Bun, so not [Functions](#instrument-a-function-bun) | Any language with an OTel SDK |
| Captures | Incoming HTTP/gRPC, plaintext outgoing HTTP/gRPC, decoded DB and cache protocols | Whatever the SDK's instrumentations cover, plus custom spans and attributes |
| Misses | Outbound TLS callees don't join the trace; queue consumers, cron work and background jobs start new traces; Node.js and Python context propagation is best effort | Nothing structural; depends on the instrumentations you enable |

Pick one per service. Running an SDK in a service that also has automatic instrumentation produces duplicate spans for every request. When moving from OBI to an SDK, deploy the SDK first, confirm its spans arrive, then switch the service to manual instrumentation.

## Instrument with an OpenTelemetry SDK

When tracing is on for a service in an environment, its next deploy there gets these variables. They show up in the service's **Variables** tab alongside the other Railway-provided variables and every OpenTelemetry SDK reads them, so an SDK configured without an explicit endpoint exports to Railway:

| Variable | Value |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Railway's OTLP receiver on the host running the service |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` |
| `OTEL_EXPORTER_OTLP_HEADERS` | A header the receiver requires on every export |
| `OTEL_SERVICE_NAME` | The Railway service name |
| `OTEL_SERVICE_VERSION` | The commit SHA, or the deployment ID for image and CLI deploys |

Rules the agent must apply:

- **Don't hardcode the endpoint, protocol, or header** in code or Dockerfiles. Let the SDK read the variables.
- **The receiver accepts traces only.** Most SDKs also export metrics and logs to the same endpoint by default and log errors when that fails. Set both on the service with the `set-variables` MCP tool (`skipDeploys: true`, since the deploy that adds the SDK picks them up); `railway variable set ... --skip-deploys` does the same from a linked repo:

  ```text
  Set variables for project <project-id>, service <service-id>: OTEL_METRICS_EXPORTER=none, OTEL_LOGS_EXPORTER=none, skipDeploys true
  ```

- **User variables win.** A service that sets its own `OTEL_EXPORTER_OTLP_ENDPOINT` or `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` (for example to keep exporting to its own collector) gets none of the tracing variables, and its spans don't reach the Traces tab; edge spans still do. Railway sets no sampler variables, so a sampler the service configures is the only one in play. Check `railway variable list --service <service> --json` before assuming the provided values apply.
- **Load the SDK first.** Instrumentation libraries (`@opentelemetry/auto-instrumentations-node`, `opentelemetry-instrumentation-*` and the like) patch libraries at import time, so the SDK must be loaded before the app's modules: a `--require`/`--import` flag in the start command, `NODE_OPTIONS`, a Python `opentelemetry-instrument` wrapper, a Java `-javaagent`, and so on. Set it with `railway environment edit --service-config <service> deploy.startCommand "<command>"` or as a variable; see [deploy.md](deploy.md).
- **Keep W3C Trace Context propagation on** (the SDK default in most languages; Go requires setting the propagator explicitly) so the service continues the edge's trace instead of starting its own.
- **Don't override `OTEL_SERVICE_NAME`** unless the user wants spans attributed under a different name than the Railway service.

Per-language install steps, framework notes, and a custom-span example are in the docs: [Node.js](https://docs.railway.com/observability/tracing/nodejs), [Deno](https://docs.railway.com/observability/tracing/deno), [Functions (Bun)](https://docs.railway.com/observability/tracing/functions), [Python](https://docs.railway.com/observability/tracing/python), [Go](https://docs.railway.com/observability/tracing/go), [Java](https://docs.railway.com/observability/tracing/java), [Ruby](https://docs.railway.com/observability/tracing/ruby), [.NET](https://docs.railway.com/observability/tracing/dotnet), [Rust](https://docs.railway.com/observability/tracing/rust), [PHP](https://docs.railway.com/observability/tracing/php). Fetch the page for the user's stack rather than reciting SDK commands from memory.

## What to instrument

Instrumentation libraries give a trace its skeleton: a server span per request and a client span per call a library recognises. On its own that is barely better than automatic instrumentation. The value comes from spans the app opens itself around the units of work its authors think in. When adding tracing to a codebase, or when asked what to instrument, cover these three layers, in this order:

1. **Inbound work.** One span per HTTP handler, gRPC method, queue or job consumer invocation, cron run and WebSocket message. The HTTP and gRPC server instrumentations usually cover handlers. Consumers, cron and background jobs are not covered by the edge or by most instrumentations, so wrap each message or run in its own span (kind `CONSUMER` or `INTERNAL`) and, where the message carries a `traceparent`, continue that context so the trace links back to the producer. Without this, background work is invisible or shows up as orphaned client spans.
2. **I/O: database queries, cache calls, outgoing HTTP and gRPC calls, queue publishes.** This is where latency and failures hide. Use the driver or client instrumentation where one exists. Where none does (a raw socket client, a vendor SDK the instrumentations don't know), wrap the call in a `CLIENT` span with the standard `db.*`, `server.address` or `url.full` attributes. Every remote call should be visible as its own span. List every database driver or ORM, cache, HTTP and queue client in the dependency manifest and check each one, because the bundles miss common ones:
   - **Node.js**: `@opentelemetry/auto-instrumentations-node` covers `pg`, `mysql2`, `ioredis`, `mongodb`, `mongoose`, `knex` and `undici`/`http`, but not Prisma (add `@prisma/instrumentation` to the SDK's instrumentations) and not postgres.js, Drizzle on postgres.js, `Bun.sql` or the Neon serverless driver (no instrumentation exists; wrap queries in a `CLIENT` span with `db.system`, `db.namespace`, `db.operation.name`). An app written as ES modules needs the `@opentelemetry/instrumentation/hook.mjs` loader, or imported drivers stay unpatched while the `http` server span still appears.
   - **Python**: `opentelemetry-distro` alone instruments nothing; run `opentelemetry-bootstrap -a install` so the instrumentations for the installed drivers (`psycopg2`, `asyncpg`, `SQLAlchemy`, `redis`, `pymongo`, `requests`, `httpx`) are installed too.
   - **Go**: nothing is automatic. Wrap `database/sql` with `otelsql`, pgx with `otelpgx`, go-redis with `redisotel`, HTTP clients with `otelhttp.NewTransport`.
   - **Rust**: `sqlx` emits tracing events, not spans; wrap queries in a span. `reqwest` needs `reqwest-tracing`.
   - **Deno**: `OTEL_DENO=true` covers `fetch`, `Deno.serve` and `node:http`; npm database drivers need their own instrumentation or a hand-written span.
   - **Java, Ruby, .NET, PHP**: the agent, `opentelemetry-instrumentation-all`, the per-library packages (`Npgsql.OpenTelemetry`, `OpenTelemetry.Instrumentation.SqlClient`, ...) and `opentelemetry-auto-pdo` cover JDBC, ActiveRecord, ADO.NET and PDO; confirm the package for the driver in use is present.
   A server span with no client spans under it means this layer was skipped. Before opening the PR, run the app once with the console exporter (`OTEL_TRACES_EXPORTER=console` or the runtime's equivalent) and hit a route that queries the database: a `CLIENT` span carrying `db.system`, even a failed one, proves the driver is patched. List each client and the instrumentation that covers it, or why it is not covered, in the PR description.

3. **Logical units of work.** A function that groups several I/O calls into one meaningful step (`checkout`, `syncUser`, `renderInvoice`), or one that is CPU-heavy on its own (parsing a large payload, image resizing, template rendering, serialising a big response). Give each an `INTERNAL` span carrying the identifiers a person debugging it would want (`order.id`, `tenant`, item counts). This turns twelve sibling `SELECT` spans under a handler into a tree that reads like the code and says which step took the time. Rule of thumb: if you would want log lines saying "starting X" and "finished X in N ms", X is a span.

Keep spans out of tight loops and trivial helpers. A span per item in a loop of thousands hits the per-replica export limit (see Sampling) and adds nothing a `count` attribute on the parent wouldn't; instrument the loop, not the iteration. Name spans with low-cardinality names (`GET /users/{id}`, `db.query users`, `process order`) and put the variable parts in attributes. Set span status to `ERROR` and record the exception when a unit fails, so `@status:error` finds it. Never put secrets, tokens or raw personal data in span names or attributes.

## Instrument a Function (Bun)

A [Railway Function](https://docs.railway.com/functions) is a service whose source image starts with `ghcr.io/railwayapp/function-` (`function-bun:1.4.0` today) and whose code is one TypeScript file, base64-encoded into the start command. `get-service-config` shows the image; `get-function-source-code` returns the code. Automatic instrumentation does not cover Bun, and Bun 1.4 has no OpenTelemetry of its own, so a function exports spans only through the OpenTelemetry JavaScript SDK loaded inside that one file.

What differs from a repo service:

- **One file, no start command.** There is no `--require`, `--preload` or `bunfig.toml`. Put the SDK setup at the top of the file. It runs before `Bun.serve` takes its first request, which is all that is needed, because nothing gets monkey-patched.
- **Dependencies come from imports.** The runtime turns every bare import into a `package.json` entry and runs `bun install` at every cold start, without a cache. Pin with `pkg@version` specifiers: `hono@4`, `@hono/otel@1`, `@opentelemetry/api@1`, and `@opentelemetry/sdk-node` to the exact `0.x` version tested, since it has no stable major. Every package added lengthens the cold start.
- **Nothing is instrumented for free.** `NodeSDK` configures the exporter, the resource and W3C propagation from the `OTEL_*` variables, but no OpenTelemetry package instruments `Bun.serve`, Bun's `fetch`, `Bun.sql` or `Bun.redis` (the Node `http` and `undici` instrumentations don't see them). Incoming requests need `@hono/otel` (Hono) or a hand-written wrapper (`Bun.serve`); outgoing `fetch` calls need `propagation.inject` for the callee to join the trace. The three layers in [What to instrument](#what-to-instrument) still apply; the function's handlers, I/O and logical units are what to wrap.
- **A code push is a deploy.** The variables land on the next deploy, and `update-function-source-code` or `railway functions push` is one, so a single push adds the SDK and picks up the variables.

Recipe:

1. Turn tracing on for the function in the environment it runs in with `set-service-tracing` (or `railway trace enable --service <function>`) if `get-tracing` shows it off there. Leave `autoInstrumentationEnabled` off; it does nothing for Bun.
2. Set the exporter variables with `set-variables`. `NodeSDK` exports metrics and logs over OTLP by default and the receiver rejects both. Pass `skipDeploys: true`; the code push in step 5 is the deploy that picks them up. Check `list-variables` first: a function that sets its own `OTEL_EXPORTER_OTLP_ENDPOINT` gets none of Railway's tracing variables.

   ```text
   Set variables for project <project-id>, service <function-id>: OTEL_METRICS_EXPORTER=none, OTEL_LOGS_EXPORTER=none, skipDeploys true
   ```

3. Read the code with `get-function-source-code`: `code` is what is current, `deployedCode` what runs, `staged` whether a commit is pending. Edit that, never a version recalled from memory.
4. Add the SDK block at the top and wrap the requests, leaving the rest of the file as it is. A Hono function ends up like this:

   ```typescript
   import { NodeSDK } from "@opentelemetry/sdk-node@0.222.0";
   import { trace } from "@opentelemetry/api@1";
   import { Hono } from "hono@4";
   import { httpInstrumentationMiddleware } from "@hono/otel@1";

   // Reads OTEL_EXPORTER_OTLP_* and OTEL_SERVICE_NAME from the variables
   // Railway provides. Nothing to configure.
   const sdk = new NodeSDK();
   sdk.start();
   process.on("SIGTERM", () => sdk.shutdown().finally(() => process.exit(0)));

   const tracer = trace.getTracer("greeter");

   const app = new Hono();
   // One SERVER span per request, continuing the edge's traceparent.
   app.use(httpInstrumentationMiddleware());

   app.get("/hello/:name", async (c) => {
     const name = c.req.param("name");
     const greeting = await tracer.startActiveSpan("build-greeting", async (span) => {
       try {
         span.setAttribute("greeting.name", name);
         return `Hello, ${name}`;
       } finally {
         span.end();
       }
     });
     return c.json({ greeting });
   });

   export default { port: Number(Bun.env.PORT ?? 3000), fetch: app.fetch };
   ```

   For a function that calls `Bun.serve` itself, wrap its `fetch` handler: take the parent from `propagation.extract(context.active(), req.headers, { get: (h, k) => h.get(k) ?? undefined, keys: (h) => [...h.keys()] })` and run the handler inside `tracer.startActiveSpan(name, { kind: SpanKind.SERVER }, parent, ...)`. For an outgoing call, start a `SpanKind.CLIENT` span and `propagation.inject(context.active(), headers, { set: (h, k, v) => h.set(k, v) })` into a `Headers` object before `fetch`. A cron or script function has no server: its spans are new roots, recorded on every run, and it must `await sdk.shutdown()` as its last statement, or the batch never leaves the process. The docs page has all three in full.

5. Write it back with `update-function-source-code` (the whole file; pass `staged: true` to stage instead of deploying live) or `railway functions push --path <file>`. This deploy also adds the variables.
6. Verify with the steps below: `curl -sI https://<domain>/hello/x | grep -i x-railway-trace-id`, then `get-trace` on the ID. A span with `component` `service` and scope `@hono/otel` (or the tracer name) means the function exports. If the deploy logs show `bun install` failing, an import specifier is wrong; if they show OTLP export errors for metrics or logs, step 2 was skipped.

Docs: [Functions](https://docs.railway.com/observability/tracing/functions).

## Sampling

- **Every request is traced.** The edge traces 100% of client-facing requests to a traced service and writes the decision into the `traceparent` sampled flag. Railway sets no sampler variables, so the SDK's default parent-based sampler follows the edge and records every root span of its own (cron jobs, queue consumers, private-network calls without a `traceparent`). There is no project or service rate to set.
- **A client `traceparent` overrides.** A request that arrives with the sampled flag set is always traced; one with it cleared never is. An instrumented client can start a trace that continues into Railway, and a caller can keep a request out of tracing by sending a cleared flag. To trace one specific request while debugging:

  ```bash
  curl -H "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01" https://<domain>/<path>
  ```

  Generate a fresh random 32-hex trace ID (the second field) for each request; reusing one merges requests into a single trace.

- **Sample in the SDK when the volume is too high.** Each replica can export 1,000 spans per 10 seconds; exports over the limit are rejected and the SDK reports a partial success. Disable noisy instrumentations first. If that isn't enough, set `OTEL_TRACES_SAMPLER=traceidratio` and `OTEL_TRACES_SAMPLER_ARG=<fraction>` on the service yourself; a `parentbased_*` sampler follows the edge's flag and would change nothing for edge requests. Traces the SDK drops still show the edge and proxy hops.

## Read traces

Traces are read through **Remote MCP** (the default agent path), `railway trace list` and `railway trace get` on the CLI, or the dashboard. The `traces`, `trace` and `tracingStatus` queries are on the public GraphQL API as well, so `railway api` can fetch them where neither fits.

| Tool | Access | Purpose |
|---|---|---|
| `list-traces` | viewer | Traces of an environment, newest first, one row per request with at least one span matching `filter`. Optional `serviceId`, `startDate`/`endDate` (ISO 8601 with timezone; defaults to the last hour), `limit` (default 100, max 500) |
| `get-trace` | viewer | One trace as an indented span tree (each line shows the span kind and the attribute that says what it talked to: `db.system`, `http.route`, `url.full` or `server.address`), with every span's attributes, events and links in the structured result. Takes `traceId` (32 hex characters); `maxSpans` caps the result and the output says when it was hit |
| `get-tracing-coverage` | viewer | What one service's own instrumentation covers: its spans in the window (default the last hour) by span kind, by the remote system they name (`db.system`, `messaging.system`, `rpc.system`, or `http` for HTTP client spans) and by the instrumentation scope that emitted them (`@opentelemetry/instrumentation-pg`, ...). Takes `serviceId`; optional `startDate`/`endDate`. Edge and proxy spans are left out. The one call that answers "are the database queries instrumented?" |

Both take `projectId` and an optional `environmentId`; omit it and the `production` environment is used, so pass the ID explicitly when the user is looking at another environment. Traces belong to the environment they were exported from.

```text
List traces for project 6adb5ae3-0e3a-4ead-b42c-1fd36f217ffb in environment <environment-id> with filter "@status:error"
```

```text
Get trace 4bf92f3577b34da6a3ce929d0e0e4736 for project 6adb5ae3-0e3a-4ead-b42c-1fd36f217ffb
```

`filter` uses the same syntax as logs: `@status:error`, `@component:edge AND @duration:>1000`, `@service:api AND @kind:client`, `@http.route:/checkout AND @http.response.status_code:500`, `@name:SELECT*`. Built-in fields are `trace`, `span`, `name`, `serviceName`, `service`, `deployment`, `replica`, `component` (`edge`, `proxy`, `service`), `kind`, `status`, `duration` (ms); any other `@key` matches a span or resource attribute, free text matches the span name, and `-` negates. Narrow the filter or the window before raising `limit`.

On the CLI, `list` scopes to the linked service unless `--all`, `--since`/`--until` take relative (`30m`, `2h`, `1d`) or ISO 8601 times, `--limit` is 1 to 500 (default 100), `--errors` adds `@status:error`, and `get --max-spans` goes up to 2000. Human output is a table and an indented span tree; `--json` prints one trace summary or one span per line, like `railway logs --json`.

```bash
railway trace list --since 30m --errors --json
railway trace list --all --filter '@http.route:/api/users @duration:>500'
railway trace get 4bf92f3577b34da6a3ce929d0e0e4736 --json
```

Workflow for "why is this request slow / failing":

1. `list-traces` (or `railway trace list`) with a filter that isolates the symptom (`@status:error`, `@duration:>1000`, `@http.route:<route>`), optionally `serviceId` for one service.
2. `get-trace` (or `railway trace get`) on a returned `traceId`. The tree runs from the edge span down through every service; the `component` on each span says which hop exported it, and a span with `ERROR` status carries the message.
3. Read the span attributes in the structured result for the detail (`http.route`, `http.response.status_code`, `db.statement`, custom attributes).

## Verify tracing works

1. **Prove the edge traced a request.** The header is present only on traced responses:

   ```bash
   curl -sI https://<domain>/ | grep -i x-railway-trace-id
   ```

2. **Fetch that trace** with `get-trace` or `railway trace get <trace-id>` and the returned ID. Edge and proxy spans confirm tracing is on; a span with `component` `service` confirms the app is exporting. After enabling an SDK, that only happens once the redeploy that added the variables is live; after enabling automatic instrumentation, allow about a minute.
3. **Check what the app covers** with `get-tracing-coverage` for the service, after sending a few requests that hit the database. Every database, cache and queue the service uses must appear under "Remote systems" and the driver instrumentations under "Instrumentation scopes". `SERVER` spans with no database client span mean a driver is still unpatched (see the I/O layer in [What to instrument](#what-to-instrument)); `list-traces` with `@kind:client @db.system:*` is the same check as a trace list.
4. **Or watch the dashboard.** The Traces tab is at `https://railway.com/project/<project-id>/traces?environmentId=<environment-id>`; its **Trace ID** field accepts a bare 32-hex ID or a whole `traceparent` header. In **Tracing setup**, each service row shows when the edge and the app last exported a span, and the **App** indicator turns green on the first span from the service itself.

## Troubleshoot

- **No traces at all**: confirm `get-tracing` or `railway trace status` reports tracing on for the service in the environment the user is looking at (the switches and the traces both belong to an environment), the service has a public domain, and the account has Tracing in Priority Boarding. With little traffic, send a request and check for `x-railway-trace-id` on the response, then `get-trace` it.
- **Traced in `production` but not elsewhere**: tracing is set per environment. Enable it in the other environment with `set-service-tracing` and its `environmentId`, or `railway trace enable --environment <name>`.
- **Edge spans only, nothing from the app** (`get-trace` shows only `edge` and `proxy` components): the variables land on the next deploy, so redeploy. Then check the service doesn't set its own `OTEL_EXPORTER_OTLP_ENDPOINT`, the SDK loads before the app serves, and, for OBI, the process is a supported runtime handling HTTP or gRPC.
- **Server spans but no database or client spans** (`get-tracing-coverage` shows `SERVER` and `INTERNAL` only, or `get-trace` shows a request span with no `CLIENT` children): the driver is not instrumented. In Node.js an ES-module app without the `@opentelemetry/instrumentation/hook.mjs` loader, Prisma without `@prisma/instrumentation`, or a client no instrumentation covers (postgres.js, Drizzle on it, `Bun.sql`); in Python a missing `opentelemetry-bootstrap -a install`; in Go an unwrapped `database/sql`. See the I/O layer in [What to instrument](#what-to-instrument).
- **App spans appear as separate traces** (`list-traces` shows service-rooted traces with `hasEdge` false next to edge-only ones): the SDK isn't reading `traceparent`. Enable the W3C Trace Context propagator and make sure nothing in front of the handlers strips the header.
- **SDK logs metrics or logs export errors**: set `OTEL_METRICS_EXPORTER=none` and `OTEL_LOGS_EXPORTER=none`.
- **Duplicate spans per request**: the service runs an SDK with automatic instrumentation on. Switch it off with `set-service-tracing` (`autoInstrumentationEnabled` false), or on the CLI `railway trace disable --auto-instrument` then `railway trace enable`.
- **Spans missing from a busy service**: over 1,000 spans per replica per 10 seconds. Disable noisy instrumentations or sample in the SDK; see [Sampling](#sampling).
- **A Function shows edge spans only**: automatic instrumentation can't help (Bun); the SDK has to be in the file. Check `get-function-source-code` for the `NodeSDK` block and the request wrapper, that the deploy logs show `bun install` succeeding, and that `OTEL_METRICS_EXPORTER`/`OTEL_LOGS_EXPORTER` are `none`. See [Instrument a Function (Bun)](#instrument-a-function-bun).
- **`railway config plan` wants to remove `tracing`** (`after: null`, nobody changed it): the IaC SDK is too old to carry the field and drops it (`railway` below 3.12.0, `railway-sdk` below 0.3.0, Go SDK below v0.3.0). Don't apply it; upgrade the SDK and plan again. See [Infrastructure as code](#infrastructure-as-code).

## Validated against

- Docs: [tracing.md](https://docs.railway.com/observability/tracing), [automatic-instrumentation.md](https://docs.railway.com/observability/tracing/automatic-instrumentation), [nodejs.md](https://docs.railway.com/observability/tracing/nodejs), [tracing/functions.md](https://docs.railway.com/observability/tracing/functions), [functions.md](https://docs.railway.com/functions), [variables/reference.md](https://docs.railway.com/variables/reference), [cli/trace.md](https://docs.railway.com/cli/trace), [infrastructure-as-code/reference.md](https://docs.railway.com/infrastructure-as-code/reference)
- Public GraphQL API (`railway api schema`): `ServiceInstance.tracingEnabled`, `ServiceInstance.autoInstrumentationEnabled` and `ServiceInstanceUpdateInput` as the per-environment path; `Project.tracingEnabled`, `Project.tracingSampleRate`, `Service.tracingEnabled`, `Service.autoInstrumentationEnabled` and their update inputs marked deprecated; the `traces`, `trace` and `tracingStatus` queries
- Railway MCP (`https://mcp.railway.com`) tool descriptions and schemas: `get-tracing` and `set-service-tracing` with `environmentId`, `describe-service`, `list-traces`, `get-trace`, `get-tracing-coverage`, `get-function-source-code`, `update-function-source-code`
- CLI source (railwayapp/cli, per-environment `railway trace` and the IaC `tracing` block in #1239): `src/commands/trace.rs` (subcommands, `--all`, `--environment`), `src/iac/compiler.rs` (`services[id].tracing` on service nodes), `src/iac/change_set.rs` (tracing diff, `deployEffect`, removal when the block is absent), `src/commands/config/mod.rs` (pull renderer)
- IaC SDK sources for the `tracing` block: railway-ts-sdk `src/iac/sdk.ts` and `src/iac/schema.ts` (`ServiceTracing`; `railway` 3.12.0), railway-py-sdk `_normalize_tracing` in `src/railway_sdk/__init__.py` (`railway-sdk` 0.3.0), railway-go-sdk `serviceNode` in `railway.go` (v0.3.0); CLI 5.63.0 `src/iac/compiler.rs` and `src/iac/change_set.rs`
- Provided variables observed on a traced service's deploy: the five `OTEL_*` variables in the table above and no sampler variables
- Function runtime: the public `ghcr.io/railwayapp/function-bun:1.4.0` image (Bun 1.4.0, bare imports turned into a `package.json` and installed with `bun install` at every start)
- Function examples run on Bun 1.4.0 with `@opentelemetry/sdk-node` 0.222.0 and `@hono/otel` 1.1.2 against a stub OTLP receiver: server span continues the incoming `traceparent`, client span propagates it, script flushes on `sdk.shutdown()`
