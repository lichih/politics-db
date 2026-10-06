# Politics Project Workflow

`politics-db` 是 ChatGPT Politics Project 的外部事實證據庫（evidence ledger）。

## 目的

長對話中的查核結果不能只留在 conversation 裡。凡是之後可能成為論述基礎、比較基準或再次查核起點的事實，都應寫入本 repo，避免重複搜尋與事後記憶改寫。

## 工作流

### 1. Session 開始

遇到政治／政策／司法／人物爭議的實證問題時：

1. 先檢查 `politics-db` 是否已有相關 case、comparator、research 或 session evidence。
2. 已存在的資料優先重用，但仍要注意 `observed_at` 與來源是否已變動。
3. 不把舊結論當成永久真理；必要時重新查核並追加新的 observation。

### 2. Session 進行中

把「可以成為論述基礎的事實」與「分析／推論」分開：

- facts：來源可直接支持的事實。
- claims：待判斷、待證明或已被反證的主張。
- searches：查詢過程，包括 not_found。
- notes：分析提示，不得冒充事實。

每個事實至少要記：

- statement
- status
- observed_at
- source
- source_type
- evidence_summary
- verification_notes

規則沿用 `docs/evidence-policy.md`。

### 3. Session 結束或證據量開始過長

建立：

`sessions/YYYY-MM-DD-topic-slug/evidence.yaml`

只保存之後值得重用的 evidence，不必保存聊天全文。

若某一項已成為長期案件基礎，升格到：

- `cases/`
- `comparators/`
- `research/`

session 檔保留原始查核脈絡，不因升格而刪除。

### 4. 回答前的 evidence check

當使用者要求：

- 「核實一下」
- 「我有沒有雙標」
- 「之前查到什麼」
- 「拿以前標準比較」
- 「這個論述的事實基礎是什麼」

應先查 `politics-db`，再視需要上網補充最新資料。

### 5. 輸出層

YAML 是 session evidence 的 authoritative source。

Markdown / HTML 都是 projection：

`evidence.yaml -> Python renderer -> evidence.md / evidence.html`

不要人工同步維護多份 authoritative state。

HTML renderer 不是第一階段必要項目；先確保 evidence YAML 穩定、可查、可引用。

## 原則

- facts != claims
- found != proven
- not_found != never_existed
- current web state != historical state
- one true premise != valid conclusion
- political camp != evidence quality
- correction is append/update with traceability, not silent overwrite
