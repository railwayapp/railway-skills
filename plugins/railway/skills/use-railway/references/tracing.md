# Tracing

Trace a request from Railway's edge through a service and into the services it calls. Turn tracing on with the `set-service-tracing` and `set-project-tracing` MCP tools and read the result with `list-traces` and `get-trace`, or do both on the project's **Traces** tab.

Tracing is a preview feature. If the project has no **Traces** tab, the account needs **Tracing** enabled in Priority Boarding first.

## What Railway records without code changes

- **Edge and proxy spans.** For every sampled request to a traced service's public domain, Railway's edge records a server span (method, path, status, cache result, upstream) and the regional proxy adds a span for its hop. The edge forwards a W3C `traceparent` header to the service and stamps `x-railway-trace-id` on the response.
- **Automatic instrumentation (OBI).** A per-service switch that attaches eBPF probes to the service's Node.js, Go, Python, Ruby, or Java processes on the host. It exports server spans for incoming HTTP/gRPC requests, client spans for plaintext outgoing calls, and spans for database and cache protocols it decodes. No SDK, no redeploy.

Spans from inside the service only appear once the service exports them, through automatic instrumentation or an OpenTelemetry SDK. A service without a public domain never gets edge spans; only what it exports itself shows up, joined to traces other services propagate to it over the private network.

## Enable tracing

Tracing has three settings. The project default (`tracingEnabled`) and the sample rate (`tracingSampleRate`) live on the project; a per-service override (`tracingEnabled`, `null` follows the project) and the automatic instrumentation switch (`autoInstrumentationEnabled`) live on the service. Automatic instrumentation only takes effect while the service's tracing is on.

**Dashboard:** open the **Traces** tab → **Tracing setup**. Toggle **Trace requests by default** under Project, optionally set a **Sample rate** (percentage), and use each service row's **Traced** switch for overrides and **Automatic instrumentation** / **Manual instrumentation** to pick how it exports spans. The same controls are on the service under **Settings → Tracing**.

**Agent path:** three MCP tools read and change these settings, and `railway trace` does the same from the CLI. Resolve IDs from the URL or `railway status --json` first, and read before writing. On a Railway cloud agent in a dashboard chat session the `railway` CLI is unauthenticated, so resolve IDs with `list-services` and stay on the MCP tools throughout.

| Tool | Access | Purpose |
|---|---|---|
| `get-tracing` | viewer | The project default (`tracingEnabled`, `sampleRate`) and, per service, `tracingOverride` (`true`/`false` pinned, `null` follows the project), the resolved `tracingEnabled`, `autoInstrumentationEnabled` and whether it is `autoInstrumentationActive`. Pass `serviceId` for one service, omit it for every service in the project |
| `set-service-tracing` | member | `tracingEnabled` `true`/`false` pins one service regardless of the project default, `null` makes it follow the project again; `autoInstrumentationEnabled` switches OBI for the service. Each is optional and independent; omit what should stay as it is. Service-wide, not per environment |
| `set-project-tracing` | member | `tracingEnabled` sets the project default for every service without an override; `sampleRate` is the fraction of client-facing requests the edge traces, `0..1`, `null` resets to Railway's default of every request. Each is optional |

All three take `projectId`. `describe-service` reports the same tracing state for one service.

```text
Get tracing for project 6adb5ae3-0e3a-4ead-b42c-1fd36f217ffb
```

```text
Set service tracing for project 6adb5ae3-0e3a-4ead-b42c-1fd36f217ffb, service <service-id>: tracingEnabled true
```

```text
Set project tracing for project 6adb5ae3-0e3a-4ead-b42c-1fd36f217ffb: tracingEnabled true, sampleRate 0.25
```

```text
Set service tracing for project 6adb5ae3-0e3a-4ead-b42c-1fd36f217ffb, service <service-id>: autoInstrumentationEnabled true
```

The sample rate is a fraction from 0 to 1 in the tools and the API; the dashboard shows it as a percentage. `set-service-tracing` warns when it switches auto-instrumentation on for a service whose tracing is off: the switch does nothing until the service, or the project default, is enabled. Without Railway MCP or `railway trace`, the public `projectUpdate` (`tracingEnabled`, `tracingSampleRate`) and `serviceUpdate` (`tracingEnabled`, `autoInstrumentationEnabled`) mutations through `railway api` set the same fields; see [request.md](request.md). That fallback needs an authenticated CLI, which a cloud agent's chat session does not have.

**CLI:** `railway trace` (aliases `traces`, `tracing`) sets the same fields. Use it when the user works in a linked repo or wants exact command output; on a cloud agent's chat session the CLI is unauthenticated, so stay on MCP there.

```bash
railway trace status --all                              # project default, every service, last edge/app span
railway trace enable --service <service>                # pin tracing on for one service
railway trace enable --auto-instrument                  # tracing plus OBI for the linked service
railway trace enable --project-default --sample-rate 0.25
railway trace disable --auto-instrument                 # pin tracing off and switch OBI off
railway trace inherit                                   # follow the project default again
```

Tracing is service-wide, so `--environment` only scopes `status`, `list` and `get`; pass `--project <id> --environment <name>` when nothing is linked. `--json` prints one document with the project default and the service state. Changing tracing needs a user or workspace token; a project token (`RAILWAY_TOKEN`) can only read. The CLI has no switch for auto-instrumentation alone: `railway trace disable --auto-instrument` followed by `railway trace enable` leaves tracing on and OBI off.

What happens next:

- The edge starts tracing requests to the service's domains within seconds.
- Automatic instrumentation reaches the running containers within about a minute. No redeploy.
- The OpenTelemetry variables below are added on the **next deploy**. An app with an SDK exports nothing until it is redeployed: `railway redeploy --service <service> --yes`.

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

When tracing is on for a service, its next deploy gets these variables. They show up in the service's **Variables** tab alongside the other Railway-provided variables and every OpenTelemetry SDK reads them, so an SDK configured without an explicit endpoint exports to Railway:

| Variable | Value |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Railway's OTLP receiver on the host running the service |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` |
| `OTEL_EXPORTER_OTLP_HEADERS` | A header the receiver requires on every export |
| `OTEL_SERVICE_NAME` | The Railway service name |
| `OTEL_SERVICE_VERSION` | The commit SHA, or the deployment ID for image and CLI deploys |
| `OTEL_TRACES_SAMPLER` | `parentbased_traceidratio`, only when the project set its own sample rate |
| `OTEL_TRACES_SAMPLER_ARG` | The project's sample rate as a fraction, only when the project set its own sample rate |

Rules the agent must apply:

- **Don't hardcode the endpoint, protocol, or header** in code or Dockerfiles. Let the SDK read the variables.
- **The receiver accepts traces only.** Most SDKs also export metrics and logs to the same endpoint by default and log errors when that fails. Set both on the service with the `set-variables` MCP tool (`skipDeploys: true`, since the deploy that adds the SDK picks them up); `railway variable set ... --skip-deploys` does the same from a linked repo:

  ```text
  Set variables for project <project-id>, service <service-id>: OTEL_METRICS_EXPORTER=none, OTEL_LOGS_EXPORTER=none, skipDeploys true
  ```

- **User variables win.** A service that sets its own `OTEL_EXPORTER_OTLP_ENDPOINT` or `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` (for example to keep exporting to its own collector) gets none of the tracing variables, and its spans don't reach the Traces tab; edge spans still do. A service that sets either `OTEL_TRACES_SAMPLER` or `OTEL_TRACES_SAMPLER_ARG` keeps both of its own and Railway adds neither. Check `railway variable list --service <service> --json` before assuming the provided values apply.
- **Load the SDK first.** Instrumentation libraries (`@opentelemetry/auto-instrumentations-node`, `opentelemetry-instrumentation-*` and the like) patch libraries at import time, so the SDK must be loaded before the app's modules: a `--require`/`--import` flag in the start command, `NODE_OPTIONS`, a Python `opentelemetry-instrument` wrapper, a Java `-javaagent`, and so on. Set it with `railway environment edit --service-config <service> deploy.startCommand "<command>"` or as a variable; see [deploy.md](deploy.md).
- **Keep W3C Trace Context propagation on** (the SDK default in most languages; Go requires setting the propagator explicitly) so the service continues the edge's trace instead of starting its own.
- **Don't override `OTEL_SERVICE_NAME`** unless the user wants spans attributed under a different name than the Railway service.

Per-language install steps, framework notes, and a custom-span example are in the docs: [Node.js](https://docs.railway.com/observability/tracing/nodejs), [Deno](https://docs.railway.com/observability/tracing/deno), [Functions (Bun)](https://docs.railway.com/observability/tracing/functions), [Python](https://docs.railway.com/observability/tracing/python), [Go](https://docs.railway.com/observability/tracing/go), [Java](https://docs.railway.com/observability/tracing/java), [Ruby](https://docs.railway.com/observability/tracing/ruby), [.NET](https://docs.railway.com/observability/tracing/dotnet), [Rust](https://docs.railway.com/observability/tracing/rust), [PHP](https://docs.railway.com/observability/tracing/php). Fetch the page for the user's stack rather than reciting SDK commands from memory.

## What to instrument

Instrumentation libraries give a trace its skeleton: a server span per request and a client span per call a library recognises. On its own that is barely better than automatic instrumentation. The value comes from spans the app opens itself around the units of work its authors think in. When adding tracing to a codebase, or when asked what to instrument, cover these three layers, in this order:

1. **Inbound work.** One span per HTTP handler, gRPC method, queue or job consumer invocation, cron run and WebSocket message. The HTTP and gRPC server instrumentations usually cover handlers. Consumers, cron and background jobs are not covered by the edge or by most instrumentations, so wrap each message or run in its own span (kind `CONSUMER` or `INTERNAL`) and, where the message carries a `traceparent`, continue that context so the trace links back to the producer. Without this, background work is invisible or shows up as orphaned client spans.
2. **I/O: database queries, cache calls, outgoing HTTP and gRPC calls, queue publishes.** This is where latency and failures hide. Use the driver or client instrumentation where one exists. Where none does (a raw socket client, a vendor SDK the instrumentations don't know), wrap the call in a `CLIENT` span with the standard `db.*`, `server.address` or `url.full` attributes. Every remote call should be visible as its own span.
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

1. Turn tracing on for the function with `set-service-tracing` (or `railway trace enable --service <function>`) if `get-tracing` shows it off. Leave `autoInstrumentationEnabled` off; it does nothing for Bun.
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

   // Reads OTEL_EXPORTER_OTLP_*, OTEL_SERVICE_NAME and OTEL_TRACES_SAMPLER*
   // from the variables Railway provides. Nothing to configure.
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

   For a function that calls `Bun.serve` itself, wrap its `fetch` handler: take the parent from `propagation.extract(context.active(), req.headers, { get: (h, k) => h.get(k) ?? undefined, keys: (h) => [...h.keys()] })` and run the handler inside `tracer.startActiveSpan(name, { kind: SpanKind.SERVER }, parent, ...)`. For an outgoing call, start a `SpanKind.CLIENT` span and `propagation.inject(context.active(), headers, { set: (h, k, v) => h.set(k, v) })` into a `Headers` object before `fetch`. A cron or script function has no server: its spans are new roots (sampled at the project rate through the sampler variables) and it must `await sdk.shutdown()` as its last statement, or the batch never leaves the process. The docs page has all three in full.

5. Write it back with `update-function-source-code` (the whole file; pass `staged: true` to stage instead of deploying live) or `railway functions push --path <file>`. This deploy also adds the variables.
6. Verify with the steps below: `curl -sI https://<domain>/hello/x | grep -i x-railway-trace-id`, then `get-trace` on the ID. A span with `component` `service` and scope `@hono/otel` (or the tracer name) means the function exports. If the deploy logs show `bun install` failing, an import specifier is wrong; if they show OTLP export errors for metrics or logs, step 2 was skipped.

Docs: [Functions](https://docs.railway.com/observability/tracing/functions).

## Sampling

- **Default is every request.** With no project sample rate, the edge traces 100% of client-facing requests and Railway adds neither sampler variable, so the SDK's default parent-based sampler follows the edge's decision and records every root span of its own.
- **A project rate applies everywhere.** The edge draws once per client-facing request and writes the decision into the `traceparent` sampled flag; requests it didn't sample carry a cleared flag, so the SDK records nothing for them. The two sampler variables make the SDK sample roots the edge never saw (cron jobs, queue consumers, private-network calls without a `traceparent`) at the same rate.
- **A client `traceparent` overrides the draw.** A request that arrives with the sampled flag set is always traced; one with it cleared never is. Use this to force a single trace while debugging a service with a low rate:

  ```bash
  curl -H "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01" https://<domain>/<path>
  ```

  Generate a fresh random 32-hex trace ID (the second field) for each request; reusing one merges requests into a single trace.

- Lower the rate for busy services. Each replica can export 1,000 spans per 10 seconds; exports over the limit are rejected and the SDK reports a partial success.

## Read traces

Traces are read through **Remote MCP** (the default agent path), `railway trace list` and `railway trace get` on the CLI, or the dashboard. The `traces`, `trace` and `tracingStatus` queries are on the public GraphQL API as well, so `railway api` can fetch them where neither fits.

| Tool | Access | Purpose |
|---|---|---|
| `list-traces` | viewer | Traces of an environment, newest first, one row per request with at least one span matching `filter`. Optional `serviceId`, `startDate`/`endDate` (ISO 8601 with timezone; defaults to the last hour), `limit` (default 100, max 500) |
| `get-trace` | viewer | One trace as an indented span tree, with every span's attributes, events and links in the structured result. Takes `traceId` (32 hex characters); `maxSpans` caps the result and the output says when it was hit |

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
3. **Or watch the dashboard.** The Traces tab is at `https://railway.com/project/<project-id>/traces?environmentId=<environment-id>`; its **Trace ID** field accepts a bare 32-hex ID or a whole `traceparent` header. In **Tracing setup**, each service row shows when the edge and the app last exported a span, and the **App** indicator turns green on the first span from the service itself.

## Troubleshoot

- **No traces at all**: confirm `get-tracing` or `railway trace status` reports tracing on for the service (its override, then the project default), the service has a public domain, and the account has Tracing in Priority Boarding. With a low rate and little traffic, force one with the `traceparent` curl above, then `get-trace` it.
- **Edge spans only, nothing from the app** (`get-trace` shows only `edge` and `proxy` components): the variables land on the next deploy, so redeploy. Then check the service doesn't set its own `OTEL_EXPORTER_OTLP_ENDPOINT`, the SDK loads before the app serves, and, for OBI, the process is a supported runtime handling HTTP or gRPC.
- **App spans appear as separate traces** (`list-traces` shows service-rooted traces with `hasEdge` false next to edge-only ones): the SDK isn't reading `traceparent`. Enable the W3C Trace Context propagator and make sure nothing in front of the handlers strips the header.
- **SDK logs metrics or logs export errors**: set `OTEL_METRICS_EXPORTER=none` and `OTEL_LOGS_EXPORTER=none`.
- **Duplicate spans per request**: the service runs an SDK with automatic instrumentation on. Switch it off with `set-service-tracing` (`autoInstrumentationEnabled` false), or on the CLI `railway trace disable --auto-instrument` then `railway trace enable`.
- **Spans missing from a busy service**: over 1,000 spans per replica per 10 seconds. Disable noisy instrumentations or lower the sample rate.
- **A Function shows edge spans only**: automatic instrumentation can't help (Bun); the SDK has to be in the file. Check `get-function-source-code` for the `NodeSDK` block and the request wrapper, that the deploy logs show `bun install` succeeding, and that `OTEL_METRICS_EXPORTER`/`OTEL_LOGS_EXPORTER` are `none`. See [Instrument a Function (Bun)](#instrument-a-function-bun).
- **Setting the sample rate fails validation**: `set-project-tracing`, `railway trace enable --project-default --sample-rate` and the API take a fraction 0..1, not a percentage.

## Validated against

- Docs: [tracing.md](https://docs.railway.com/observability/tracing), [automatic-instrumentation.md](https://docs.railway.com/observability/tracing/automatic-instrumentation), [nodejs.md](https://docs.railway.com/observability/tracing/nodejs), [tracing/functions.md](https://docs.railway.com/observability/tracing/functions), [functions.md](https://docs.railway.com/functions), [variables/reference.md](https://docs.railway.com/variables/reference)
- Platform source (railwayapp/mono): `common/javascript/models/src/tracingVariables.ts` (provided variables and precedence), `common/javascript/models/src/functions.ts` and `services.ts` (function start command, image prefix), `packages/backboard/src/graphql/v2/schema/schema.graphql` (`Project.tracingEnabled`, `Project.tracingSampleRate`, `Service.tracingEnabled`, `Service.autoInstrumentationEnabled`, `ProjectUpdateInput`, `ServiceUpdateInput`), `packages/hikari/src/settings/tunables.rs` (default sample rate), `packages/stacker-oteld/configs/main.go` (span limit), `packages/backboard/src/handlers/http/routes/mcp/tools/listTraces.ts`, `getTrace.ts`, `getTracing.ts`, `setServiceTracing.ts`, `setProjectTracing.ts`, `tracingMcpHelpers.ts`, `getFunctionSourceCode.ts` and `updateFunctionSourceCode.ts` (MCP tools)
- Function runtime (railwayapp/code-images): `bun/Dockerfile` (Bun 1.4.0), `bun/run.sh` (import scan, `bun install` per start, `bun run --smol index.tsx`)
- Function examples run on Bun 1.4.0 with `@opentelemetry/sdk-node` 0.222.0 and `@hono/otel` 1.1.2 against a stub OTLP receiver: server span continues the incoming `traceparent`, client span propagates it, script flushes on `sdk.shutdown()`
