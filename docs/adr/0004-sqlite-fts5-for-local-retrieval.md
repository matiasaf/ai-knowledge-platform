# 4. SQLite FTS5 for local lexical retrieval

- Status: accepted
- Date: 2026-08-13

## Context

Milestone 3 introduces query-shaped data: indexed documents, page-bounded chunks and
ranked retrieval. JSON sidecars are no longer an appropriate query engine, but the
application still targets one local process and has no need for shared or remote
storage. Adding PostgreSQL and pgvector before semantic retrieval exists would add an
operational service without improving the current lexical quality baseline.

## Decision

Keep PDFs, document metadata and extracted pages as the ingestion source of truth.
Treat a local `knowledge.db` as rebuildable derived data containing relational
`indexed_documents` and `chunks` tables plus an external-content FTS5 index.

Database triggers keep the FTS index synchronized with chunk inserts, updates and
deletes. Replacing one document's index happens in one transaction. Every chunk stays
inside one page and stores its document ID, one-based page number, per-page chunk index
and source character offsets.

Search accepts plain language, extracts at most twenty letter/number tokens, removes a
small set of English question words and quotes every remaining token before building an
OR expression. Clients cannot pass raw FTS syntax. FTS5's default rank/BM25 order is
used internally and results expose a simple one-based rank rather than an opaque score.

Schema compatibility is pinned with SQLite `user_version = 1`. An unknown version is a
hard error rather than an attempted implicit migration.

## Consequences

- Local startup still needs only Python and Node; SQLite ships with Python and no
  database server or credentials are required.
- Chunk/document relationships can be queried and the derived index is transactionally
  replaced per document.
- Retrieval is lexical. Synonyms or conceptually related wording with no shared tokens
  can miss; the UI calls this a retrieval miss and never invents an answer.
- The index is local to one API process. Multiple hosts, access control and shared
  tenants will require a server database.
- External-content FTS requires synchronization discipline. Triggers and repository
  tests keep the content and search index in the same transaction.

## When this gets revisited

Revisit when semantic or hybrid retrieval materially improves a versioned evaluation,
when more than one API process must share data, or when authentication/multi-tenancy
requires centrally enforced isolation. PostgreSQL with a vector extension is a likely
candidate then, but it should win on measured requirements rather than appearance.
