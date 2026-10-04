# ADR-0002: Supabase Postgres is the primary query projection

- Status: **Accepted**
- Date: 2026-10-04
- Supersedes: ADR-0001 as primary search backend

## Context

politics-db needs two properties that should not be conflated:

1. durable, diffable historical evidence storage;
2. a queryable index that ChatGPT can access directly during discussion.

GitHub JSONL satisfies the first requirement. A connected Supabase project satisfies the second while preserving relational SQL, Chinese full-text search and future vector retrieval in one system.

The connected project `politicsdb` was verified on 2026-10-04:

- PostgreSQL 17
- PGroonga available: 3.2.5
- pg_trgm available: 1.6
- pgvector extension (`vector`) available: 0.8.2
- public schema currently empty

## Decision

### 1. Authoritative storage remains GitHub JSONL

GitHub JSONL remains the source of truth for:

- cases
- claims
- sources
- observations
- procedural events
- entities / relations
- query logs and not-found observations

The remote database is a projection and must be rebuildable from repository data.

### 2. Primary online query projection is Supabase/Postgres

Supabase Postgres becomes the primary searchable projection because ChatGPT can query it directly through the connected integration.

This removes the need to clone/build a local index before every evidence-retrieval discussion.

### 3. Chinese/CJK FTS backend is PGroonga

Use PGroonga for Chinese/CJK lexical full-text search.

Rationale:

- Supabase documents PGroonga specifically for multilingual search including Chinese and Japanese.
- The extension is available in the connected project.
- It supports substring/full-text-style search over ordinary text columns.
- It avoids depending on English-oriented PostgreSQL native tsvector parsing for Chinese evidence text.

PGroonga is the **primary FTS backend**.

### 4. pg_trgm is auxiliary, not the main FTS engine

Use pg_trgm for:

- fuzzy person/name matching
- aliases
- typo tolerance
- short fragments
- similarity ranking

Do not use pg_trgm as the sole evidence FTS layer.

### 5. pgvector is semantic retrieval, not evidence truth

Use pgvector for semantic candidate retrieval such as:

> 找和「檢方知道、兩次不起訴、後來發回」概念相近的案件

Vector search returns candidate records only.

Every semantic hit must resolve back to structured records and source IDs before being used as evidence.

### 6. Structured SQL remains authoritative for procedural predicates

Questions such as:

- 是否有人檢舉？
- 是否主動偵辦？
- 是否不起訴？
- 是否再議發回？
- 是否搜索／扣押手機？
- 後來是否起訴或有罪？

must be represented as structured fields / procedural events and queried relationally.

FTS/vector search must not substitute for explicit procedural state.

### 7. Local fallback remains SQLite FTS5 trigram

SQLite FTS5 `trigram` remains the offline/local fallback:

- CI
- sandbox without Supabase access
- reproducible local rebuild
- disaster recovery / independent verification

The SQLite DB remains disposable and derived from JSONL.

## Architecture

```text
GitHub politics-db
JSONL = authoritative
        |
        | sync / rebuild
        v
Supabase Postgres = primary query projection
  |- relational tables
  |- PGroonga  -> Chinese lexical FTS
  |- pg_trgm   -> fuzzy/name/fragment matching
  `- pgvector  -> semantic candidate retrieval
        |
        v
ChatGPT direct SQL retrieval
        |
        v
claim/source/evidence chain returned to discussion

Local fallback:
JSONL -> SQLite + FTS5(trigram)
```

## Evidence safety rule

A database hit is not itself a citation.

Every returned item must carry stable IDs linking back to authoritative repository records and ultimately to the original source metadata.

Likewise:

- `not_found` means only that a particular search at a particular time found nothing.
- a currently reachable source does not imply permanent availability.

## Why not Firebase

Firebase/Firestore can store documents and newer Firestore offerings can support vector/text search, but politics-db is naturally relational and procedural.

The critical queries are joins and event sequences rather than document lookup alone.

More importantly, the current ChatGPT environment has a direct Supabase integration that can execute SQL against the database, while no equivalent direct Firebase integration was found during the 2026-10-04 plugin survey.

## Reconsideration triggers

Revisit this decision if:

- direct Supabase access becomes unavailable;
- PGroonga becomes unavailable on the platform;
- corpus size or concurrency requires a dedicated search service;
- ranking quality requires a specialized search engine;
- a future connector offers a materially better evidence-query interface.

JSONL remains authoritative regardless of query backend.
