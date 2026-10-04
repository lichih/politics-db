# Search / FTS 技術調研

- Date: 2026-10-04
- Scope: politics-db 本機全文檢索與 JSONL 索引
- Status: archived research; implementation decision is recorded separately in `docs/adr/0001-local-search-index.md`

## Requirements

politics-db 的搜尋需求不是一般網站搜尋框，而是讓本機工具／ChatGPT sandbox 能：

1. 從 GitHub 取得 authoritative JSONL。
2. 不依賴常駐 server 即可重建索引。
3. 對繁體中文／CJK 做可用的全文或子字串搜尋。
4. 由全文命中回到結構化的 case / claim / source / observation / procedural event。
5. 能把查到的 fact 與 evidence chain 拉回當前討論。
6. 索引可以丟棄重建，不把 binary DB 當歷史真相。
7. 保持日後換搜尋引擎的可能性。

## Candidate technologies

### SQLite FTS5

**Architecture:** embedded / single-file DB.

**JSONL:** Python 逐行讀取後匯入 normal tables 與 FTS virtual tables。

**CJK:** SQLite 內建 FTS5 `trigram` tokenizer 可做 CJK 子字串索引，不需要額外 tokenizer extension。

**Pros**
- sandbox 已直接可用。
- 無 daemon、無額外 binary。
- Python stdlib `sqlite3` 即可操作。
- 結構化 SQL、JOIN 與全文檢索在同一個 DB。
- index 可隨時從 JSONL 重建。
- 很適合目前 politics-db 的資料量與單使用者研究流程。

**Cons / limitations**
- trigram 是字元 n-gram，不是中文語意分詞。
- 很短的查詢（尤其少於 3 個 Unicode 字元）不能只依賴 FTS MATCH；需 fallback 到 `LIKE` 或其他欄位條件。
- 未提供 search-as-you-type、HTTP service、distributed indexing 等服務型能力。
- binary SQLite file 不適合直接作為 Git canonical data。

### Quickwit / Tantivy

**Architecture:** Rust search engine / service or local indexing tooling.

**JSONL:** 適合大量 JSON/JSONL ingest。

**CJK:** 可透過適當 tokenizer / n-gram strategy 支援。

**Pros**
- 高吞吐、大量文件與 log-style data 的伸縮性較高。
- 當 evidence corpus 擴大到大量全文、法院全文、新聞封存時有吸引力。
- JSON-centric ingest workflow 與 politics-db 的 durable source format 相容。

**Cons for current project**
- sandbox 目前沒有預裝 Quickwit / Tantivy。
- 需要額外 binary / dependency。
- 對目前資料量屬於過度架構。
- structured relational query 仍需要額外資料層或 application logic。

### Meilisearch

**Architecture:** standalone HTTP service.

**Strengths**
- developer experience 佳。
- 適合 UI 搜尋、即時搜尋、模糊／容錯型搜尋。

**Weaknesses for current project**
- 需要常駐服務。
- sandbox 不保證已安裝或可啟動。
- politics-db 的主要需求是 evidence retrieval + relational filtering，而不是 end-user search UI。

### Elasticsearch / OpenSearch

**Architecture:** standalone/distributed service.

**Strengths**
- 成熟的全文檢索與 aggregation。
- 適合大型 production search cluster。

**Weaknesses for current project**
- JVM/service 維運成本遠高於需求。
- sandbox portability 差。
- 對目前單 repo、單使用者、本機重建索引的工作流不合理。

### ZincSearch

**Architecture:** lightweight HTTP search service.

**Strengths**
- 比 Elasticsearch 輕。
- 適合需要 HTTP API 但不想承擔 ES 維運成本的場景。

**Weaknesses for current project**
- 仍然需要額外 binary / service。
- 目前沒有比 SQLite 的 zero-dependency 優勢更重要的需求。

## Sandbox verification

2026-10-04 實測環境：

- SQLite version: **3.46.1**
- FTS5: available
- `tokenize='trigram'`: available
- Chinese query test:
  - `周玉蔻`: hit
  - `不起訴`: hit

Example verification:

```python
import sqlite3

db = sqlite3.connect(":memory:")
db.execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='trigram')")
db.execute("INSERT INTO t VALUES (?)", ("周玉蔻 高虹安 不起訴",))

assert db.execute(
    "SELECT x FROM t WHERE t MATCH '周玉蔻'"
).fetchone()

assert db.execute(
    "SELECT x FROM t WHERE t MATCH '不起訴'"
).fetchone()
```

## Conclusion

Current architecture should prefer:

```text
GitHub JSONL (authoritative)
        ↓
sandbox build
        ↓
SQLite normal tables
        +
SQLite FTS5(trigram)
        ↓
fact / evidence retrieval
```

Quickwit/Tantivy remains the primary future candidate if the corpus becomes dominated by very large document collections or local rebuild/query performance becomes materially inadequate.

Do not migrate merely because another engine has a higher theoretical throughput ceiling.
