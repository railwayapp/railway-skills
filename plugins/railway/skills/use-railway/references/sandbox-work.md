# Real work in sandboxes

Use this when work should run off this machine: full test suites, long builds, dependency installs, many tasks in parallel, or generated code that shouldn't run locally. The local agent stays the orchestrator. It edits, runs git, and runs quick focused checks locally, and sends everything heavy to sandboxes. Command details live in [sandbox.md](sandbox.md). This file covers the workflow.

## Target the project explicitly

Resolve the project and environment once, then pass `-p <projectId> -e <environmentId>` on every sandbox command. This makes the workflow independent of the directory's link, so it works the same when the user pastes a project link or names a project.

- **Pasted link**: `https://railway.com/project/<projectId>/...?environmentId=<environmentId>`. Take both IDs from the URL.
- **Project link without `environmentId`, or a project ID**: list the project's environments. Use the only one if there is one, and ask the user which to use if there are several:
  ```bash
  railway api 'query($id: String!) { project(id: $id) { name environments { edges { node { id name } } } } }' \
    --variables '{"id": "<projectId>"}'
  ```
- **Project name**: `railway list --json` maps names to IDs.
- **Linked directory**: `railway status --json` has both IDs. Pass them explicitly anyway so the same commands work from any directory.

After `create`, pass `--id <sandboxId>` on every command. The CLI's active sandbox is one machine-wide setting, so another agent or terminal that creates a sandbox retargets every command that relies on it.

`create` and `fork` return while the sandbox is still `CREATING`, and an `exec` sent before it reaches `RUNNING` can return no output and run nothing. Wait for `RUNNING` first; it usually takes a few seconds:

```bash
sbx_wait() { # sbx_wait <sandboxId>
  for _ in $(seq 60); do
    [ "$(railway sandbox list -p "$P" -e "$E" --json | jq -r --arg id "$1" '.[] | select(.id == $id).status')" = RUNNING ] && return 0
    sleep 2
  done
  return 1
}
```

## Prepare a base once, then checkpoint it

Installing toolchains and dependencies in every sandbox costs minutes per task. Do it once and boot later sandboxes from a checkpoint:

```bash
id=$(railway sandbox create -p "$P" -e "$E" --idle-timeout-minutes 60 --json | jq -r .id)
sbx_wait "$id"
sbx_push "$id" . /root/work      # see Push code
railway sandbox exec -p "$P" -e "$E" --id "$id" -- 'cd /root/work && <install> && <build>'
railway sandbox checkpoint create -p "$P" -e "$E" --id "$id" "myrepo-$(cat <lockfiles> | git hash-object --stdin | cut -c1-12)"
railway sandbox destroy -p "$P" -e "$E" "$id"
```

- Use the project's own install and build commands, as its README, CI config, or task runner defines them.
- Name the checkpoint after the repo and a hash of its dependency lockfiles. When dependencies change, the name changes, so tasks never boot from a stale base, and `checkpoint list` shows whether a matching base already exists before you build one.
- An environment holds at most as many checkpoints as its sandbox cap, so delete bases you have superseded.
- A checkpoint holds disk only. Pass `--variable`, `--env-file`, and `--private-network` again on every create.
- Use `fork <id>` when the state you want exists only in a live sandbox, such as a half-finished experiment. Use a checkpoint for anything reused across tasks or sessions.

## Push code

Send source, not build output. Stream a tarball of the files git knows about (tracked, plus untracked files that aren't ignored) through `exec` stdin. `exec` stdin and stdout are binary-safe, so no separate copy step is needed. The remote side extracts over the existing tree and records which files it received. On the next push it deletes the recorded files that are no longer sent. Renamed and deleted files disappear, and everything the sandbox produced itself (installed dependencies, build output, caches) stays in place:

```bash
sbx_push() { # sbx_push <sandboxId> <localDir> <remoteDir>
  (cd "$2" && git ls-files -z --cached --others --exclude-standard |
    COPYFILE_DISABLE=1 tar -czf - --null -T -) |
  railway sandbox exec -p "$P" -e "$E" --id "$1" -- sh -c '
    set -e; dest=$0; list=$dest.sbx-files
    mkdir -p "$dest"
    tar -xzvf - -C "$dest" | sort > "$list.new"
    if [ -f "$list" ]; then
      comm -23 "$list" "$list.new" | (cd "$dest" && while IFS= read -r f; do rm -f "./$f"; done)
    fi
    mv "$list.new" "$list"' "$3"
}
```

- Push after each change; a typical repo takes seconds. Then run an idempotent prepare step that reinstalls only when the lockfile changed.
- Give the remote directory as an absolute path (`/root/work`). The local shell expands `~` before the sandbox sees it.
- `.git` stays local. When the remote run needs history, `git clone` inside the sandbox.
- A tracked file deleted but not yet staged makes the local `tar` print `Cannot stat`. The push is still correct, and the file is removed remotely.
- Pull files back the same way: `railway sandbox exec ... -- 'cat /root/work/report.json' > report.json`.

## Run work

```bash
railway sandbox exec -p "$P" -e "$E" --id "$id" -- 'cd /root/work && <test command>'
```

- The local exit status is the remote command's exit status, including after reattaching with `--session`.
- Single-quote the command. The local shell then leaves `$VARS` and globs for the sandbox's shell to expand.
- Detach anything longer than a few minutes, and reattach to wait for it:
  ```bash
  s=$(railway sandbox exec -p "$P" -e "$E" --id "$id" --detach -- 'cd /root/work && <long command> > /tmp/job.log 2>&1')
  railway sandbox exec -p "$P" -e "$E" --id "$id" --session "$s"   # blocks until done, exits with the job's code
  ```
  A running detached command counts as activity, so it keeps the sandbox alive past its idle timeout. A process backgrounded with `&` or `nohup` inside a command that returns doesn't count, and the sandbox is destroyed under it.
- A durable session keeps about the last 8 MiB of output. Redirect large output to a file in the sandbox, then read only what you need: the tail, the failing test names, or a JSON report. This also keeps megabytes of logs out of your context.

## Fan out

Create one sandbox per task, agent, or test shard from the base checkpoint, and run them at the same time. Creates return in seconds, and sandboxes booted from a checkpoint already have their dependencies:

```bash
for i in 1 2 3 4; do
  railway sandbox create -p "$P" -e "$E" --checkpoint "$BASE" --idle-timeout-minutes 30 --json | jq -r .id > "shard$i.id" &
done; wait
# sbx_wait and push the candidate to each, then run shard i of 4 with the test runner's shard flag
```

- Give each sandbox one owner. Two agents in one working tree corrupt each other's runs.
- An environment runs at most 10 (Trial, Free), 50 (Hobby), or 100 (Pro) sandboxes at once, and creates beyond that fail. Every running sandbox is billed, so size the fan-out to what the task is worth, not to the cap.
- The CLI creates sandboxes at the plan's default size (Pro: 8 vCPU / 8 GB). Larger sizes need the SDK or the API's `resources` option. Exit code 137 means the process was killed, usually by the OOM killer, so lower the job's parallelism or request a larger size.

## Tell your failures from the environment's

A sandbox differs from the local machine in ways that cause failures unrelated to your change:

- Every sandbox sets `RAILWAY_PROJECT_ID`, `RAILWAY_ENVIRONMENT_ID`, and `RAILWAY_SANDBOX_ID`. Code that detects "running on Railway" through these variables takes a different path. Run such suites under `env -u RAILWAY_PROJECT_ID -u RAILWAY_ENVIRONMENT_ID -u RAILWAY_SANDBOX_ID ...`.
- The standard image runs its tools through mise shims, so in a repo that contains `mise.toml` every command fails with `Config files ... are not trusted` until `mise trust` runs in the repo.
- Sandboxes are isolated by default, with public egress only. Tests that need the environment's databases or internal services need `--private-network` at create time.
- When a failure looks unrelated, run the same test on an untouched checkout in the same sandbox, for example a pristine copy kept in the base at `/root/base`. A failure that also happens there isn't yours.

## Clean up

- Destroy each sandbox you created as soon as its task is done: `railway sandbox destroy -p "$P" -e "$E" <id>`. Keep the IDs you create. `sandbox list --json` shows every sandbox in the environment, including other agents' sandboxes.
- Treat `--idle-timeout-minutes` as the backstop. Size it to cover the longest gap between your commands. Trial and Free plans cap it at 5 minutes.
- Delete checkpoints you have superseded.

## Validated against

- Docs: [sandboxes.md](https://docs.railway.com/sandboxes), [sandbox.md](https://docs.railway.com/cli/sandbox), [agents-in-sandboxes.md](https://docs.railway.com/guides/agents-in-sandboxes)
- Railway CLI 5.71.0, run end to end against a live environment (2026-11-09)
