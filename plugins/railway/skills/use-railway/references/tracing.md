# Tracing

Trace a request from Railway's edge through a service and into the services it calls, and read the result with the `list-traces` and `get-trace` MCP tools or on the project's **Traces** tab.

Tracing is a preview feature. If the project has no **Traces** tab, the account needs **Tracing** enabled in Priority Boarding first.

## What Railway records without code changes

- **Edge and proxy spans.** For every sampled request to a traced service's public domain, Railway's edge records a server span (method, path, status, cache result, upstream) and the regional proxy adds a span for its hop. The edge forwards a W3C `traceparent` header to the service and stamps `x-railway-trace-id` on the response.
- **Automatic instrumentation (OBI).** A per-service switch that attaches eBPF probes to the service's Node.js, Go, Python, Ruby, or Java processes on the host. It exports server spans for incoming HTTP/gRPC requests, client spans for plaintext outgoing calls, and spans for database and cache protocols it decodes. No SDK, no redeploy.

Spans from inside the service only appear once the service exports them, through automatic instrumentation or an OpenTelemetry SDK. A service without a public domain never gets edge spans; only what it exports itself shows up, joined to traces other services propagate to it over the private network.

## Enable tracing

Tracing has three settings. The project default (`tracingEnabled`) and the sample rate (`tracingSampleRate`) live on the project; a per-service override (`tracingEnabled`, `null` follows the project) and the automatic instrumentation switch (`autoInstrumentationEnabled`) live on the service. Automatic instrumentation only takes effect while the service's tracing is on.

**Dashboard:** open the **Traces** tab → **Tracing setup**. Toggle **Trace requests by default** under Project, optionally set a **Sample rate** (percentage), and use each service row's **Traced** switch for overrides and **Automatic instrumentation** / **Manual instrumentation** to pick how it exports spans. The same controls are on the service under **Settings → Tracing**.

**Agent path:** there is no CLI command or MCP tool for changing these settings; use `railway api` with the public `projectUpdate` and `serviceUpdate` mutations. Resolve IDs from the URL or `railway status --json` first.

```bash
# Trace every service in the project by default, at Railway's default sample rate
railway api \
  'mutation enableTracing($id: String!) {
    projectUpdate(id: $id, input: { tracingEnabled: true }) { tracingEnabled tracingSampleRate }
  }' \
  --variables '{"id":"<project-id>"}'

# Trace 25% of client-facing requests instead; null resets to the default
railway api \
  'mutation setRate($id: String!, $rate: Float) {
    projectUpdate(id: $id, input: { tracingSampleRate: $rate }) { tracingSampleRate }
  }' \
  --variables '{"id":"<project-id>","rate":0.25}'

# Pin one service on or off regardless of the project default (null follows the project)
railway api \
  'mutation traceService($id: String!, $on: Boolean) {
    serviceUpdate(id: $id, input: { tracingEnabled: $on }) { tracingEnabled }
  }' \
  --variables '{"id":"<service-id>","on":true}'

# Turn on automatic instrumentation for a service whose tracing is on
railway api \
  'mutation autoInstrument($id: String!) {
    serviceUpdate(id: $id, input: { autoInstrumentationEnabled: true }) { tracingEnabled autoInstrumentationEnabled }
  }' \
  --variables '{"id":"<service-id>"}'
```

`tracingSampleRate` is a fraction from 0 to 1 in the API; the dashboard shows it as a percentage. Read the settings back with `project(id) { tracingEnabled tracingSampleRate }` and `service(id) { tracingEnabled autoInstrumentationEnabled }`.

What happens next:

- The edge starts tracing requests to the service's domains within seconds.
- Automatic instrumentation reaches the running containers within about a minute. No redeploy.
- The OpenTelemetry variables below are added on the **next deploy**. An app with an SDK exports nothing until it is redeployed: `railway redeploy --service <service> --yes`.

## Choose how the service exports spans

| | Automatic instrumentation (OBI) | OpenTelemetry SDK |
|---|---|---|
| Code changes | None | Install the SDK, load it before the app serves requests |
| Takes effect | About a minute after enabling, no redeploy | Next deploy |
| Runtimes | Node.js, Go, Python, Ruby, Java | Any language with an OTel SDK |
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
- **The receiver accepts traces only.** Most SDKs also export metrics and logs to the same endpoint by default and log errors when that fails. Set both on the service:

  ```bash
  railway variable set OTEL_METRICS_EXPORTER=none OTEL_LOGS_EXPORTER=none --service <service> --skip-deploys
  ```

- **User variables win.** A service that sets its own `OTEL_EXPORTER_OTLP_ENDPOINT` or `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` (for example to keep exporting to its own collector) gets none of the tracing variables, and its spans don't reach the Traces tab; edge spans still do. A service that sets either `OTEL_TRACES_SAMPLER` or `OTEL_TRACES_SAMPLER_ARG` keeps both of its own and Railway adds neither. Check `railway variable list --service <service> --json` before assuming the provided values apply.
- **Load the SDK first.** Auto-instrumentation packages patch libraries at import time, so the SDK must be loaded before the app's modules: a `--require`/`--import` flag in the start command, `NODE_OPTIONS`, a Python `opentelemetry-instrument` wrapper, a Java `-javaagent`, and so on. Set it with `railway environment edit --service-config <service> deploy.startCommand "<command>"` or as a variable; see [deploy.md](deploy.md).
- **Keep W3C Trace Context propagation on** (the SDK default in most languages; Go requires setting the propagator explicitly) so the service continues the edge's trace instead of starting its own.
- **Don't override `OTEL_SERVICE_NAME`** unless the user wants spans attributed under a different name than the Railway service.

Per-language install steps, framework notes, and a custom-span example are in the docs: [Node.js](https://docs.railway.com/observability/tracing/nodejs), [Deno](https://docs.railway.com/observability/tracing/deno), [Python](https://docs.railway.com/observability/tracing/python), [Go](https://docs.railway.com/observability/tracing/go), [Java](https://docs.railway.com/observability/tracing/java), [Ruby](https://docs.railway.com/observability/tracing/ruby), [.NET](https://docs.railway.com/observability/tracing/dotnet), [Rust](https://docs.railway.com/observability/tracing/rust), [PHP](https://docs.railway.com/observability/tracing/php). Fetch the page for the user's stack rather than reciting SDK commands from memory.

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

Traces are read through **Remote MCP** or the dashboard. There is no `railway` CLI command for them, and the GraphQL trace queries are not on the public API, so `railway api` cannot fetch them.

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

Workflow for "why is this request slow / failing":

1. `list-traces` with a filter that isolates the symptom (`@status:error`, `@duration:>1000`, `@http.route:<route>`), optionally `serviceId` for one service.
2. `get-trace` on a returned `traceId`. The tree runs from the edge span down through every service; the `component` on each span says which hop exported it, and a span with `ERROR` status carries the message.
3. Read the span attributes in the structured result for the detail (`http.route`, `http.response.status_code`, `db.statement`, custom attributes).

## Verify tracing works

1. **Prove the edge traced a request.** The header is present only on traced responses:

   ```bash
   curl -sI https://<domain>/ | grep -i x-railway-trace-id
   ```

2. **Fetch that trace** with `get-trace` and the returned ID. Edge and proxy spans confirm tracing is on; a span with `component` `service` confirms the app is exporting. After enabling an SDK, that only happens once the redeploy that added the variables is live; after enabling automatic instrumentation, allow about a minute.
3. **Or watch the dashboard.** The Traces tab is at `https://railway.com/project/<project-id>/traces?environmentId=<environment-id>`; its **Trace ID** field accepts a bare 32-hex ID or a whole `traceparent` header. In **Tracing setup**, each service row shows when the edge and the app last exported a span, and the **App** indicator turns green on the first span from the service itself.

## Troubleshoot

- **No traces at all**: confirm `tracingEnabled` resolves to true for the service (service override, then project default), the service has a public domain, and the account has Tracing in Priority Boarding. With a low rate and little traffic, force one with the `traceparent` curl above, then `get-trace` it.
- **Edge spans only, nothing from the app** (`get-trace` shows only `edge` and `proxy` components): the variables land on the next deploy, so redeploy. Then check the service doesn't set its own `OTEL_EXPORTER_OTLP_ENDPOINT`, the SDK loads before the app serves, and, for OBI, the process is a supported runtime handling HTTP or gRPC.
- **App spans appear as separate traces** (`list-traces` shows service-rooted traces with `hasEdge` false next to edge-only ones): the SDK isn't reading `traceparent`. Enable the W3C Trace Context propagator and make sure nothing in front of the handlers strips the header.
- **SDK logs metrics or logs export errors**: set `OTEL_METRICS_EXPORTER=none` and `OTEL_LOGS_EXPORTER=none`.
- **Duplicate spans per request**: the service runs an SDK with automatic instrumentation on. Switch it to manual instrumentation.
- **Spans missing from a busy service**: over 1,000 spans per replica per 10 seconds. Disable noisy instrumentations or lower the sample rate.
- **Setting `tracingSampleRate` fails validation**: the API takes a fraction 0..1, not a percentage.

## Validated against

- Docs: [tracing.md](https://docs.railway.com/observability/tracing), [automatic-instrumentation.md](https://docs.railway.com/observability/tracing/automatic-instrumentation), [nodejs.md](https://docs.railway.com/observability/tracing/nodejs), [variables/reference.md](https://docs.railway.com/variables/reference)
- Platform source (railwayapp/mono): `common/javascript/models/src/tracingVariables.ts` (provided variables and precedence), `packages/backboard/src/graphql/v2/schema/schema.graphql` (`Project.tracingEnabled`, `Project.tracingSampleRate`, `Service.tracingEnabled`, `Service.autoInstrumentationEnabled`, `ProjectUpdateInput`, `ServiceUpdateInput`), `packages/hikari/src/settings/tunables.rs` (default sample rate), `packages/stacker-oteld/configs/main.go` (span limit), `packages/backboard/src/handlers/http/routes/mcp/tools/listTraces.ts` and `getTrace.ts` (MCP tools)
