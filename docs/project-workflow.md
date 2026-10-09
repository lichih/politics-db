# Politics Project Workflow

`politics-db` 是 ChatGPT Politics Project 的外部事實證據庫（evidence ledger）。

## 目的

長對話中的查核結果不能只留在 conversation 裡。凡是之後可能成為論述基礎、比較基準或再次查核起點的事實，都應寫入本 repo，避免重複搜尋與事後記憶改寫。

## 工作流

### 0. 寫入契約：先驗證，再進 authoritative main

`main` 是 evidence 的 authoritative state。任何 Agent 或人工對 evidence、schema、renderer 或其工作流的修改，都不得把未驗證內容直接寫入 `main`。

標準流程：

1. 從最新 `main` 建立工作 branch。
2. 只在工作 branch 寫入或修改檔案。
3. 在送出 PR 前執行 `python renderer/render.py --check`；失敗時先修正，不得建立「明知驗證失敗」的可合併 PR。
4. 建立 PR 至 `main`，由 `.github/workflows/validate-evidence.yml` 再執行同一套 schema 與 cross-reference validation。
5. validation 成功後才可 merge。
6. 不得以直接 push `main`、停用 validation、刪除錯誤 evidence 或降低 schema 約束來繞過失敗檢查；若 schema 本身需要調整，應在同一 PR 中說明原因並讓既有資料全部通過新版驗證。
7. merge 後由部署 workflow 再驗證一次，render HTML 並 force-push `gh-pages`。GitHub Pages 直接由 `gh-pages` branch 發布；部署失敗不得改寫 authoritative evidence 來掩蓋問題。

GitHub branch protection / ruleset 是額外的機械 enforcement；即使 repository 尚未啟用 protection，本工作流仍是 Politics Project Agent 的操作契約。

YAML 注意事項：年份、日期、純數字代碼等在 `tags`、ID 或其他要求 string 的欄位中必須顯式加引號，例如 `"2027"`，避免 YAML scalar inference 將其解析為 integer。


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

YAML 是 evidence 的 authoritative source。

目前只維護一種 projection：

`evidence.yaml -> schema / cross-reference validation -> Python + Jinja2 -> HTML`

不產生 Markdown，避免 YAML / Markdown / HTML 三份內容並存而增加同步成本。

HTML 只負責閱讀、導覽、filter 與展開 evidence graph；不得作為資料回寫來源。產生的 `site/` 不進版控，由 GitHub Actions build 後部署到 GitHub Pages。

Renderer 在 `renderer/render.py`，schema 在 `schema/evidence.schema.json`。

## 原則

- facts != claims
- found != proven
- not_found != never_existed
- current web state != historical state
- one true premise != valid conclusion
- political camp != evidence quality
- correction is append/update with traceability, not silent overwrite
