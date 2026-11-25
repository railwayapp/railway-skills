# Redis design: keys, data structures, access patterns, changes

Use this when designing how an application stores data in Redis, reviewing Redis access code, or changing a key layout. To measure a live instance first, use [analyze-db-redis.md](analyze-db-redis.md). For HA commands, use [databases.md](databases.md).

Redis keeps the dataset in memory and runs commands on a single main thread. Two rules follow: memory is the capacity limit, and one slow command delays every other client.

## Decide the role first

State whether Redis is a **cache** (data can be rebuilt from another store) or a **store of record** (queues, sessions, rate-limit state, or data that exists nowhere else). The role decides eviction, persistence, and HA:

| Role | `maxmemory-policy` | TTLs | Losing data |
|---|---|---|---|
| Cache | `allkeys-lru` or `allkeys-lfu` | On every key | Acceptable; rebuild on miss |
| Store of record | `noeviction` (writes fail when full instead of deleting data) | Only where the data model needs expiry | Not acceptable; plan persistence, backups, and HA |
| Mixed | `volatile-lru`/`volatile-lfu` (evict only keys with a TTL) | On cache keys only | Cache keys only |

Prefer separate instances for cache and store-of-record data when the workload is significant; one eviction policy rarely fits both.

## Keys and data structures

- **Key names**: a consistent `type:id[:field]` scheme, for example `user:42:profile`, `session:<token>`, `rate:login:<ip>`. Add a version segment (`v2:user:42`) when the encoding may change. Keep names short but readable.
- **Pick the structure for the access pattern**:
  - String: a single value, serialized object, or counter (`INCR`, `INCRBY`).
  - Hash: an object whose fields are read or updated individually (`HSET`, `HGET`, `HINCRBY`). Small hashes use a compact encoding.
  - Sorted set: ranking, leaderboards, time-ordered indexes (score = timestamp), sliding-window rate limits.
  - Set: membership and tags; intersections for simple filtering.
  - List: simple FIFO/LIFO queues and capped recent-item lists (`LPUSH` + `LTRIM`).
  - Stream: durable event logs and work queues with consumer groups and acknowledgements (`XADD`, `XREADGROUP`, `XACK`). Prefer streams over lists when a crashed worker must not lose a message.
  - HyperLogLog and bitmaps: approximate unique counts and compact flags.
- **Bound every collection.** A hash, set, list, or sorted set that grows without limit becomes a "big key": slow to read, slow to delete, and costly to replicate. Shard large collections by a key segment (`events:2026-10-09`), cap them (`LTRIM`, `XADD ... MAXLEN ~ n`), or expire them.
- **Expire what is temporary.** Set TTLs atomically on write (`SET key value EX 3600`). Add jitter to TTLs on bulk-loaded cache entries so they do not all expire in the same second.

## Secondary lookups ("indexes")

Redis has no automatic secondary indexes. Options, in order of preference:

1. Design the key so the lookup is a direct read (`user:by-email:<email>` -> id).
2. Maintain an index structure yourself (a set per tag, a sorted set per time order) and update it in the same `MULTI`/`EXEC` or Lua script as the primary write so they cannot drift.
3. Use the Redis Query Engine (`FT.CREATE`, `FT.SEARCH`) for multi-field queries. It ships with Redis Open Source 8; confirm it is available on the running server (`MODULE LIST` or `FT._LIST`) before designing around it.

If the application needs ad-hoc filtering, joins, or reporting, that data belongs in a relational or document database, with Redis in front as a cache.

## Access patterns

- **Never `KEYS *` in production.** It scans the whole keyspace and blocks the server. Use `SCAN` with `MATCH` and `COUNT`, or maintain an index set.
- **Avoid unbounded reads**: `HGETALL`, `SMEMBERS`, `LRANGE 0 -1`, and `ZRANGE 0 -1` on large collections are O(N). Use `HSCAN`/`SSCAN`/`ZSCAN` or bounded ranges.
- **N+1 round trips**: fetching many keys one by one pays network latency per key. Use `MGET`/`HMGET`, or pipeline commands so many requests share one round trip.
- **Pagination**: page sorted sets by score (`ZRANGE key (last_score +inf BYSCORE LIMIT 0 50`) rather than by rank offset when items are inserted concurrently.
- **Deleting big keys**: `UNLINK` frees memory in the background; `DEL` on a large collection blocks.
- **Lua and functions** run atomically and block every other client while running. Keep scripts short and bounded.
- **Cache stampede**: when a hot key expires, many clients rebuild it at once. Use a short lock (`SET lock:key token NX PX 5000`), serve stale data while one client refreshes, or refresh before expiry.

Find offenders on a live instance with `SLOWLOG GET 20`, `redis-cli --bigkeys`, `redis-cli --memkeys`, and `MEMORY USAGE <key>`. These scans are read-only but add load; run them off-peak on large datasets.

## Transactions and locking

- `MULTI`/`EXEC` queues commands and runs them without interleaving. There is no rollback: a command that fails at runtime does not undo the others.
- `WATCH` gives optimistic concurrency: `EXEC` aborts if a watched key changed, and the client retries.
- For read-modify-write logic that must be atomic, prefer a single command (`INCR`, `HINCRBY`, `SET ... NX`) or a Lua script.
- A simple lock is `SET lock:<name> <random-token> NX PX <ttl>`, released only by the holder with a compare-and-delete script. Replication is asynchronous, so a lock can be lost if the primary fails over before replicating it. Do not use Redis locks as the only guard for correctness-critical work; pair them with idempotent writes or a database constraint.

## Changing a key layout

There is no schema to migrate, so changes are application deploys:

1. Write the new format under a new key name or version prefix while still reading the old one (read new, fall back to old).
2. Backfill with a `SCAN`-driven script in small batches, pipelined, with pauses so latency stays flat.
3. Switch reads to the new keys only, then delete old keys with `UNLINK` in batches, or let them expire.

For a cache, the simplest migration is often a new key prefix and letting the old keys expire.

## On Railway

- **Connect**: `railway connect <service>` opens `redis-cli`; `--tunnel-only` holds a tunnel for GUI tools.
- **Persistence**: the Railway Redis template runs the official `redis` image. If Redis is a store of record, confirm the persistence settings (`CONFIG GET appendonly` and `CONFIG GET save`) match the durability the data needs, and schedule volume backups. Docs: [Redis](https://docs.railway.com/databases/redis), [Backups](https://docs.railway.com/volumes/backups).
- **High availability**: Railway's Redis HA runs Sentinel on every data node behind HAProxy, with AOF persistence always on. Clients connect to HAProxy and do not need a Sentinel-aware client, but they must reconnect after a failover, and writes not yet replicated when the primary fails can be lost. Use HA when Redis holds state the app cannot rebuild quickly. Docs: [Redis High Availability](https://docs.railway.com/databases/redis-ha).
- **Memory**: set `maxmemory` below the service's memory limit so Redis evicts or rejects writes before the container runs out of memory.

## Validated against

- Redis documentation: data types, key eviction policies, `SCAN`, pipelining, transactions (`MULTI`/`EXEC`/`WATCH`), `UNLINK`, `SLOWLOG`, `redis-cli --bigkeys`/`--memkeys`, persistence (RDB/AOF), replication, Redis Open Source 8 Query Engine
- Railway docs: [Redis](https://docs.railway.com/databases/redis), [Redis HA](https://docs.railway.com/databases/redis-ha), [Backups](https://docs.railway.com/volumes/backups), [`railway connect`](https://docs.railway.com/cli/connect)
