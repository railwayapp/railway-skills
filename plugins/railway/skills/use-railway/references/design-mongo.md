# MongoDB design: documents, indexes, queries, changes

Use this when designing MongoDB collections, writing or reviewing an index or query, or changing document shape. To measure a live database first, use [analyze-db-mongo.md](analyze-db-mongo.md).

Validate with `db.collection.find(...).explain("executionStats")` on realistic data. Compare `nReturned`, `totalKeysExamined`, and `totalDocsExamined`: a healthy indexed query examines close to as many keys and documents as it returns. A `COLLSCAN` stage on a large collection means no index served the query.

## Document and collection design

- **Model for the reads.** Data that is read together should usually live in one document. Start from the application's most frequent queries, not from a normalized entity diagram.
- **Embed** when the child data belongs to one parent, is read with it, and stays small and bounded (an order's line items, a user's settings).
- **Reference** (store the other document's `_id`) when the related data is large, shared by many parents, updated independently, or grows without limit (a user's events, a product's reviews).
- **No unbounded arrays.** Documents have a hard 16 MiB limit, and large arrays make every update rewrite and replicate more data. Move growing lists into their own collection keyed by the parent `_id`, or bucket them (for example one document per parent per day).
- **`_id`**: the default `ObjectId` is unique, compact (12 bytes), and roughly time-ordered, which keeps inserts at the end of the `_id` index. Use a natural key as `_id` only when it is immutable and unique. Random UUIDs as `_id` scatter inserts across the index; prefer time-ordered UUIDv7 if a UUID is required, stored as BSON UUID (binary subtype 4), not a string.
- **Types**: be consistent per field. Store dates as BSON `Date`, money as `Decimal128` or integer minor units, and IDs with one type everywhere; a field that is sometimes a string and sometimes an `ObjectId` silently fails to match.
- **Schema validation**: add a `$jsonSchema` validator (`collMod` with `validator`) for required fields and types. Start with `validationAction: "warn"` on existing collections, fix violations, then switch to `"error"`.
- **Schema version**: add a `schemaVersion` field when document shape will evolve, so code can handle old and new shapes during a migration.

## Indexing

- **Compound order (ESR)**: put fields matched by **E**quality first, then fields used for **S**orting, then fields filtered by **R**ange. `{ tenantId: 1, createdAt: -1 }` serves `find({ tenantId }).sort({ createdAt: -1 })`; a range field placed before the sort field forces an in-memory sort.
- **Prefixes**: an index on `{ a: 1, b: 1, c: 1 }` serves queries on `a`, `a, b`, and `a, b, c`, so a separate `{ a: 1 }` index is redundant.
- **Covered queries**: if the filter and the projection use only indexed fields and the projection excludes `_id` (unless `_id` is in the index), MongoDB answers from the index alone (`totalDocsExamined: 0`).
- **Partial indexes**: `partialFilterExpression` indexes only matching documents, for example `{ status: "pending" }`. The query must include a condition that implies the filter.
- **Unique indexes** enforce constraints; combine with `partialFilterExpression` for "unique when present".
- **TTL indexes** (single `Date` field with `expireAfterSeconds`) delete expired documents automatically through a background task, so deletion is not instant.
- **Multikey (array) indexes**: a compound index can include more than one array field, but no single document may have arrays in more than one of the indexed fields.
- **Text and wildcard indexes** exist for search and for collections with arbitrary field names; prefer explicit compound indexes for known query shapes.
- **Cost**: every index slows inserts and updates and uses memory. Index the measured query shapes.

### Audit unused and duplicate indexes

```javascript
// Usage counts since each index was created or the server last restarted
db.orders.aggregate([{ $indexStats: {} }, { $project: { name: 1, "accesses.ops": 1, "accesses.since": 1 } }])

// Spot prefixes: an index whose key pattern is the leading part of another is usually redundant
db.orders.getIndexes().map(i => JSON.stringify(i.key))
```

`$indexStats` counts only the member you are connected to, and counters reset on restart. Check the `since` timestamp before calling an index unused. Hide it first (`db.orders.hideIndex("name")`, MongoDB 4.4+) to observe the impact; `unhideIndex` restores it instantly without a rebuild.

## Query patterns

- **N+1**: replace per-document follow-up queries with one `find({ _id: { $in: ids } })` per batch, or a `$lookup` in an aggregation when the joined side is indexed on the lookup field. Frequent `$lookup` on a hot path suggests embedding instead.
- **Pagination**: `skip(n)` walks and discards n entries. Use range pagination on the sort key: `find({ createdAt: { $lt: lastCreatedAt } }).sort({ createdAt: -1 }).limit(50)`, adding `_id` as a tiebreaker when the sort key is not unique.
- **Index-friendly predicates**: anchored, case-sensitive regexes (`/^abc/`) can use an index; unanchored or case-insensitive ones scan. `$ne`, `$nin`, and `$not` are rarely selective. `$where` (server-side JavaScript) cannot use indexes, and `$expr` uses them only for limited comparison forms.
- **Project fields**: return only needed fields, especially when documents contain large arrays or blobs.
- **Batching writes**: `insertMany` and `bulkWrite` with `ordered: false` (when operations are independent) instead of one round trip per document. Run large `updateMany`/`deleteMany` jobs in `_id` ranges so each batch stays short.
- **Aggregation**: put `$match` and `$sort` that can use an index at the start of the pipeline, before `$unwind`, `$group`, or `$lookup`.

## Transactions and consistency

- Writes to a **single document** are atomic, including nested fields and arrays. Design updates so most invariants live within one document and use update operators (`$inc`, `$push`, `$set` with a filter) instead of read-modify-write.
- **Multi-document transactions and change streams require a replica set** (or sharded cluster). A standalone `mongod` does not support them. Check with `db.hello().setName`; it is absent on a standalone server.
- Keep transactions short and small. They hold locks and cache resources, and they abort after a time limit (60 seconds by default, `transactionLifetimeLimitSeconds`). Retry on `TransientTransactionError`.
- Use `writeConcern: { w: "majority" }` for data that must survive a failover, and keep retryable writes enabled (the default in current drivers).

## Safe changes

- **Index builds**: since MongoDB 4.2, builds take an exclusive lock only briefly at the start and end, and the `background` option is ignored. Builds still consume CPU and I/O, and on a replica set they run on all data-bearing members together (4.4+). Create large indexes off-peak and watch progress with `db.currentOp()`.
- **Dropping**: hide the index first, then drop it.
- **Document shape changes**: deploy code that reads both shapes, backfill in `_id`-range batches (stamping `schemaVersion`), then remove the old-shape handling. Lazy migration (rewrite a document when it is next written) is fine when old shapes can stay readable indefinitely.
- **Renaming fields**: `updateMany({}, { $rename: ... })` touches every document; run it in batches, never as one call on a large collection.

## On Railway

- **Connect**: `railway connect <service>` opens `mongosh`; `--tunnel-only` holds a tunnel for GUI tools.
- **Standalone vs replica set**: the MongoDB template starts a standalone `mongod`, so multi-document transactions and change streams need the HA conversion first. Docs: [MongoDB](https://docs.railway.com/databases/mongodb).
- **High availability**: Railway's MongoDB HA converts the service into a replica set (3, 5, or 7 nodes) behind HAProxy. All connections, reads included, go to the primary; replicas exist for failover, not read scaling. Applications must reconnect and retry after an election. Docs: [MongoDB High Availability](https://docs.railway.com/databases/mongo-ha).
- **Backups**: schedule volume backups and take one before risky migrations. Docs: [Backups](https://docs.railway.com/volumes/backups).

## Validated against

- MongoDB manual: data modeling (embedding vs references), BSON document size limit, compound index ESR guideline, covered queries, partial/TTL/multikey indexes, `$indexStats`, hidden indexes, index builds on populated collections, transactions and replica set requirement, `explain` results
- Railway docs: [MongoDB](https://docs.railway.com/databases/mongodb), [MongoDB HA](https://docs.railway.com/databases/mongo-ha), [Backups](https://docs.railway.com/volumes/backups), [`railway connect`](https://docs.railway.com/cli/connect)
