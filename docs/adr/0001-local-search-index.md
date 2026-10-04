# ADR-0001: Local search index uses SQLite FTS5 trigram

- Status: **Superseded by ADR-0002**
- Date: 2026-10-04
- Decision owner: politics-db
- Supersedes: none

## Context

politics-db needs durable evidence storage plus fast local retrieval.

The Git repository must preserve facts, sources, observations and historical lookup state in a diffable format. At discussion time, ChatGPT/sandbox must be able to reconstruct a local index, search Chinese text, and return the matching structured evidence chain.

A binary search database must not become the authoritative record.

## Decision

### 1. Authoritative data

**JSONL is authoritative.**

Expected logical datasets include:

- cases
- claims
- sources
- observations
- procedural_events
- relations

Exact schema may evolve independently of this ADR.

### 2. Search/index projection

**SQLite is the local derived projection.**

The SQLite database is disposable and rebuildable from JSONL.

It should normally be excluded from Git.

### 3. Full-text backend

**SQLite FTS5 with the built-in `trigram` tokenizer is the initial FTS backend.**

Reason:

- confirmed available in the current sandbox;
- works on Traditional Chinese/CJK substrings without external tokenizer extensions;
- zero daemon and zero non-stdlib Python dependency;
- searchable content and relational metadata can be joined in the same query;
- sufficient for the current expected corpus size.

### 4. Structured query is not FTS

FTS is only a candidate-retrieval mechanism.

Questions such as:

- 有人提告嗎？
- 是否不起訴？
- 高檢是否發回？
- 後來是否起訴／判決有罪？
- observed_at 是何時？

must be represented as structured fields/events and queried with SQL.

Do not encode important procedural state only in prose and expect FTS to recover it reliably.

### 5. Search flow

```text
query
  ↓
structured filters when known
  +
FTS5 trigram candidate search
  ↓
claim_id / case_id / source_id
  ↓
normal SQLite tables
  ↓
complete evidence chain
  ↓
discussion / report
```

### 6. Short-query fallback

FTS5 trigram is designed around 3-character grams.

For search terms shorter than three Unicode characters, the search layer must not rely solely on `MATCH`.

Fallback order:

1. exact structured field lookup where applicable;
2. indexed/equality lookup for IDs, names, tags or normalized entities;
3. `LIKE '%term%'` for limited text fallback.

This is especially relevant to short Chinese terms.

### 7. No external Chinese tokenizer dependency in v1

v1 will **not** require Jieba, IK, Lindera or a loadable SQLite tokenizer extension.

Reason: sandbox portability and reproducibility are more important than linguistic tokenization at this stage.

Entity aliases and structured metadata should cover many cases where word segmentation would otherwise be useful.

### 8. SQLite DB is not evidence

The generated `politics.sqlite`:

- may be deleted at any time;
- may be rebuilt at any time;
- should not be cited as the historical source;
- must retain IDs that point back to authoritative JSONL records and their source metadata.

## Consequences

### Positive

- Works immediately in the sandbox.
- Simple Python implementation.
- Git diffs remain meaningful.
- Chinese search works without installation.
- FTS and relational evidence queries compose naturally.
- Backend replacement remains possible because JSONL stays authoritative.

### Negative

- trigram search is lexical substring matching, not semantic Chinese tokenization.
- index size can be larger than token-based FTS.
- short queries need fallback logic.
- future large-scale document archival may outgrow this backend.

## Supersession

Superseded on 2026-10-04 after connecting a Supabase project directly to ChatGPT and verifying that the project exposes PGroonga, pg_trgm and pgvector. SQLite FTS5 remains the local/offline fallback described here.

## Reconsideration triggers

Re-evaluate the backend if one or more become material:

- local index rebuild time becomes operationally inconvenient;
- corpus grows to large archived document collections where FTS5 storage/query cost is problematic;
- concurrent remote search service becomes a requirement;
- ranking/tokenization quality becomes more important than exact evidence retrieval;
- external systems need an HTTP search API.

Primary migration candidate: **Quickwit/Tantivy**.

The migration should replace only the derived search projection, not the JSONL evidence model.

## Verified environment

Verified on 2026-10-04 in the current sandbox:

- SQLite **3.46.1**
- FTS5 available
- FTS5 `trigram` tokenizer available
- Traditional Chinese sample queries successfully matched
