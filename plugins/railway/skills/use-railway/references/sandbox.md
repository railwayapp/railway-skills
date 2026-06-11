# Sandboxes

Sandboxes are ephemeral remote Linux environments attached to a Railway project + environment. Use them when the user asks for a sandbox, a scratch/ephemeral environment, or wants to build or run something remotely without touching deployed services. Sandboxes link at the project level — a linked project and environment (or explicit `--project` / `--environment` flags) is enough; no service link is needed.

## Availability — Priority Boarding required

**Sandboxes must be enabled in Priority Boarding.** If sandbox commands fail with a feature-availability error from the API (the `PROJECT_SANDBOXES` feature is not enabled for the workspace), do not retry — prompt the user to enable Sandboxes through Priority Boarding in the Railway dashboard, then resume once they confirm.

Two non-errors to expect:

- Every sandbox command prints `Warning: Railway sandboxes are experimental and APIs may change or break during testing.` on stderr. This is informational — not a failure.
- Context errors (`No project selected...` / `No environment selected...`) mean missing linking, not missing access: run `railway link` or pass `--project` and `--environment`.

## Create and connect

### Create a sandbox

```bash
railway sandbox create
railway sandbox create --variable DB_URL=postgres.DATABASE_URL --env-file .env
railway sandbox create --private-network --idle-timeout-minutes 60 --json
```

`create` boots a sandbox and remembers it as the **active sandbox** — later commands that take `--id` default to it. `--variable` values may reference other Railway variables (`postgres.DATABASE_URL` or the full `${{postgres.DATABASE_URL}}` form), resolved server-side at create time; `--variable` overrides `--env-file` entries with the same key. Sandboxes are isolated with public egress by default — pass `--private-network` when the sandbox must reach internal hosts like `postgres.railway.internal`. `--idle-timeout-minutes` auto-destroys the sandbox after that long idle; attached sessions send a heartbeat that keeps it alive. Prefer `--json` for parsing the created id.

### Connect over SSH

```bash
railway sandbox ssh                      # interactive shell in the active sandbox
railway sandbox ssh --id <sandbox-id> -- ls -la
```

Trailing `-- <command>` runs a single command instead of an interactive shell. `--session <name>` resumes a durable session by name.

## Run commands remotely

### One-off commands

```bash
railway sandbox exec -- npm test
railway sandbox exec --id <sandbox-id> --timeout 120 -- ./integration.sh
```

Everything after `--` is the command. A single argument runs as a shell command; multiple arguments run as argv with quoting preserved. `--timeout <seconds>` is a client-side deadline — on expiry the command is terminated and the CLI exits 124 (GNU timeout convention), so treat exit 124 as "took too long", not "failed".

### Long-running commands — detach and reattach

```bash
railway sandbox exec --detach -- npm run build   # prints a durable session name, exits
railway sandbox exec --session <name>            # reattach and stream the output
```

`--detach` starts the command, prints its durable session name to stdout, and returns while the command keeps running — use it for builds or jobs longer than you want to block on. Reattach with `--session <name>`; add `--resume-from-last-read` to skip replaying retained scrollback. Durable sessions are not available on every sandbox — when the CLI warns `durable sessions are unavailable for this sandbox; ran attached`, the command still ran, just without reattach support.

## Remote builds

Use templates to run build steps remotely. Build steps execute server-side in a transient sandbox; the result is a content-addressed filesystem snapshot cached server-side, so re-running the same recipe is an instant cache hit.

### Build remotely

```bash
railway sandbox template build --name ci -c 'npm ci' -c 'npm run build' --wait
```

`-c` is repeatable and runs in order; each step must exit 0 within 10 minutes. `--wait` polls until READY or FAILED. `--name` is a local-only handle for reuse.

### Boot from the build

```bash
railway sandbox create --template ci             # boots from the cached snapshot
railway sandbox exec -- npm start
```

Template recipes are stored locally by this CLI — `Unknown template` means it was built elsewhere or never built; rebuild it with the command the error message prints. For state that must be reachable from other machines or later sessions, capture a [checkpoint](#checkpoints--save-and-restore-sandbox-state) instead.

### Inspect templates

```bash
railway sandbox template status <id-or-name> --json
railway sandbox template list --json
```

## Port forwarding

```bash
railway sandbox forward 3000              # localhost:3000 → sandbox port 3000
railway sandbox forward 8080:3000 5432    # explicit local port; multiple ports per connection
```

If a requested local port is busy the CLI picks a nearby free one and says so — pass `--strict` to fail instead. The tunnel auto-reconnects with backoff if the relay drops while the sandbox is still running.

## Fork a sandbox

```bash
railway sandbox fork                      # fork the active sandbox; the fork becomes active
railway sandbox fork <sandbox-id> --variable FOO=bar --private-network
```

A fork copies the source's filesystem state but **does not inherit its variables or network mode** — re-pass `--variable`/`--env-file`/`--private-network` as needed.

## Checkpoints — save and restore sandbox state

Checkpoints are named disk snapshots captured from a running sandbox, stored server-side per environment. Use them to set a sandbox up once (clone a repo, install dependencies, seed data) and boot fresh sandboxes from that state later. Pick the right state mechanism:

- **Template**: a reproducible recipe built from shell instructions — deterministic, but stored in this CLI's local store, so it only resolves on the machine that built it.
- **Fork**: a live copy of a sandbox made right now.
- **Checkpoint**: state you set up interactively, saved server-side by name — works from any machine or later agent session.

### Capture

```bash
railway sandbox checkpoint create my-setup       # capture the active sandbox's disk
railway sandbox checkpoint create my-setup --id <sandbox-id> --json
```

Capture is synchronous — the checkpoint is bootable as soon as the command returns, but flushing and uploading a large disk can take a while (the request honors `RAILWAY_HTTP_TIMEOUT`, so raise that rather than assuming a hang). Reusing a name **replaces the previous checkpoint without warning** — run `checkpoint list` first if overwriting matters. 64-character hex names are reserved for template hashes.

### Boot from a checkpoint

```bash
railway sandbox create --checkpoint my-setup
railway sandbox exec -- npm start
```

`--checkpoint` and `--template` are mutually exclusive. A checkpoint restores disk state only — variables and network mode are not part of the snapshot, so re-pass `--variable`/`--env-file`/`--private-network` on create as needed.

### Manage checkpoints

```bash
railway sandbox checkpoint list --json
railway sandbox checkpoint rename <name> <new-name>
railway sandbox checkpoint delete <name>
```

Checkpoints are scoped to the environment: `list` shows only the linked environment's checkpoints, and `--checkpoint` resolves names within that scope. Deleting a checkpoint removes its underlying disk snapshot.

## List and teardown

```bash
railway sandbox list --json               # also refreshes the local id cache
railway sandbox list --all                # include destroyed sandboxes
railway sandbox destroy                   # destroy the active sandbox
railway sandbox destroy <sandbox-id>
```

Destroy sandboxes you created for a task once the task is done — idle timeout is the backstop, not the cleanup plan.

## Troubleshoot sandboxes

- **Feature-availability error from the API**: Sandboxes aren't enabled for this workspace. Prompt the user to enable Sandboxes through Priority Boarding in the Railway dashboard; don't retry until they confirm.
- **`No project selected` / `No environment selected`**: run `railway link` or pass `--project` with `--environment`.
- **`Unknown template ...`**: the recipe isn't in this CLI's local store — rebuild with `railway sandbox template build --name <name> -c '<command>' --wait`, or use a checkpoint if the state was meant to travel between machines.
- **`Template build failed`**: a step exited non-zero or exceeded its 10-minute limit; fix that step and rebuild.
- **`No checkpoint named ...`**: checkpoints are environment-scoped — confirm the linked environment and run `railway sandbox checkpoint list`; the checkpoint may live in another environment or have been deleted/replaced.
- **Checkpoint capture times out**: a large disk is still uploading — raise `RAILWAY_HTTP_TIMEOUT` (seconds) and retry rather than treating it as a failure.
- **Exit code 124 from `exec`**: the client-side `--timeout` expired — rerun with a larger timeout or `--detach`.
- **`that session may have expired; the server started a fresh one instead`**: the durable session lapsed; the command ran in a new session — check whether prior state mattered.
- **SSH/forward drops**: the CLI reconnects automatically while the sandbox is RUNNING; if it reports the sandbox STOPPED, create or fork a new one.

## Validated against

- Docs: [sandboxes.md](https://docs.railway.com/sandboxes), [sandbox.md](https://docs.railway.com/cli/sandbox)
- CLI source: [sandbox.rs](https://github.com/railwayapp/cli/blob/v5.12.0/src/commands/sandbox.rs), [sandbox_exec.rs](https://github.com/railwayapp/cli/blob/v5.12.0/src/controllers/sandbox_exec.rs)
