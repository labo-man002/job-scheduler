# Saved replay runs

Run the Alembic migrations before using web run history. The web application currently has a single-user, instance-wide history because it has no authenticated user or workspace identity. Restrict network access to the intended operator. A deployment that serves multiple users needs authenticated scope checks on every history operation before exposing this API.

## Save, reopen and reuse

- A save accepts a client-generated UUID request ID and exactly one of a checked-in preset, a saved starting run, or a complete scenario. Optional capacity and topology edits apply to the resolved scenario. A saved starting run keeps its complete recorded job trace and label. Capacity edits with the same number of nodes preserve the saved node IDs. A different number of nodes assigns IDs from one in node-list order.
- A new save returns HTTP 201. A retry using the same request ID and the same effective snapshot returns HTTP 200 and the existing run. HTTP 409 signals that the request ID is already associated with different effective inputs. Use a new ID for an intentional rerun. Preset inputs resolve at request time, so a changed preset can produce a conflict on a retry. Open the recorded run in history to recover its exact snapshot.
- History lists newest first. Pagination with a before_id cursor uses creation time and UUID ordering even when new saves arrive. Offset pagination is also available. The list returns metadata only.
- Reading a detail returns the saved inputs and outputs without running the simulator. A name update changes metadata only. A saved scenario version that the current engine cannot load remains readable, and the API returns HTTP 409 if asked to use it as a starting point.
- The offline CLI keeps its database-free execution path.

## Persistence and concurrency

A PostgreSQL advisory lock serializes fresh work for one request ID across app workers. The service checks for an existing result and closes the read transaction before simulation. It holds one pooled database connection through replay to retain the session lock. A single insert commits both outputs and all provenance together. PostgreSQL enforces instance-wide uniqueness of request IDs. Failures before commit leave no run record. Database parameter logging hides the bound snapshots.

The immutable inputs and outputs JSONB envelopes have independent schema versions. They preserve the full trace, configuration, both policy ledgers and exact GPU-time counts. Preserve the saved response contract or introduce a reader adapter when upgrading its envelope. An engine revision can be absent when the deployed process cannot find Git metadata.
