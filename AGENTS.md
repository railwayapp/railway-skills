# Railway Claude Plugin

Claude plugin for [Railway](https://railway.com). Interact with your Railway
projects directly from Claude Code.

## Skills

Skills are model-invoked - Claude decides when to use them based on user intent
matching the skill description. Each skill lives in `plugins/railway/skills/{name}/SKILL.md`.

Read `plugins/railway/skills/{name}/SKILL.md` for detailed usage, examples, and error handling.
For general info on how Claude Code skills work, look up the Claude Code skill
documentation.

## Architecture

Skills can use either the Railway CLI or GraphQL API:

**CLI** - The `railway` command. Best for operations that use the linked
project/service context. Always use `--json` flag for parseable output.

**GraphQL API** - Direct API access at
`https://backboard.railway.com/graphql/v2`. Use for mutations or operations not
available in CLI.

### API Token

Token location: `~/.railway/config.json` → `user.token`

Use `${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh '<query>' '<variables-json>'` to make
authenticated requests. This helper reads the token and handles auth headers.

```bash
# Query with variables
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'query getEnv($id: String!) { environment(id: $id) { name } }' \
  '{"id": "env-uuid"}'

# Mutation with variables
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'mutation update($id: String!, $input: ProjectUpdateInput!) { projectUpdate(id: $id, input: $input) { name } }' \
  '{"id": "proj-uuid", "input": {"name": "new-name"}}'
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

Shared utilities in `plugins/railway/skills/lib/`:

- `railway-common.sh` - CLI preflight checks (is CLI installed, authenticated,
  project linked)
- `railway-api.sh` - GraphQL API helper

## Adding New Skills

1. Create `plugins/railway/skills/{name}/SKILL.md` with YAML frontmatter (`name`, `description`)
2. Choose CLI or API based on what's available/appropriate
3. Reference base skills for preflight checks if needed

## References

Look at these when developing new skills:

- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/plugins
