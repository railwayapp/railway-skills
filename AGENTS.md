# Railway Claude Plugin

Claude plugin for [Railway](https://railway.com). Interact with your Railway
projects directly from Claude Code.

## Skills

Skills are model-invoked - Claude decides when to use them based on user intent
matching the skill description. Each skill lives in `plugins/railway/skills/{name}/SKILL.md`.

Read `plugins/railway/skills/{name}/SKILL.md` for detailed usage, examples, and error handling.
For general info on how Claude Code skills work, look up the Claude Code skill
documentation.

When editing or creating skills, use the `skill-development` skill to follow best practices.

## Architecture

Skills can use either the Railway CLI or GraphQL API:

**CLI** - The `railway` command. Best for operations that use the linked
project/service context. Always use `--json` flag for parseable output.

**GraphQL API** - Direct API access at
`https://backboard.railway.com/graphql/v2`. Use for mutations or operations not
available in CLI.

### API Token

Token location: `~/.railway/config.json` → `user.token`

Each skill that needs GraphQL has `scripts/railway-api.sh` for authenticated requests:

```bash
# From within a skill directory
scripts/railway-api.sh \
  'query getEnv($id: String!) { environment(id: $id) { name } }' \
  '{"id": "env-uuid"}'
```

API docs: https://docs.railway.com/api/llms-docs.md

Full schema introspection:

```bash
curl -s https://backboard.railway.com/graphql/v2 \
  -H 'content-type: application/json' \
  -d '{"query":"{ __schema { types { name fields { name args { name type { name } } type { name } } } } }"}'
```

## Composability

Skills build on each other. Base skills (`status`, `service-status`) provide
preflight checks that operation skills can reference before making changes.

## Shared Files

Scripts and references are shared across skills. Canonical versions live in
`plugins/railway/skills/_shared/`. Each skill has its own copy for portability.

**DO NOT edit files in individual skill `scripts/` or `references/` directories.**
Edit the canonical version in `_shared/`, then run:

```bash
./scripts/sync-shared.sh
```

Shared files:
- `_shared/scripts/railway-api.sh` - GraphQL API helper
- `_shared/scripts/railway-common.sh` - CLI preflight checks
- `_shared/references/*.md` - Config schemas, variable patterns, etc.

## Adding New Skills

1. Create `plugins/railway/skills/{name}/SKILL.md` with YAML frontmatter (`name`, `description`)
2. Choose CLI or API based on what's available/appropriate
3. Reference base skills for preflight checks if needed

## References

Look at these when developing new skills:

- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/plugins
