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

### 首頁時間語意、格式與排序

- `session.started_at`：這份 evidence session 開始建立／查核的時間，不等於底層事件發生時間。
- `session.updated_at`：這份 evidence 最後一次有實質內容更新的時間，例如新增或修正 source、fact、claim、search、status 或會改變證據解讀的重要 note；renderer、CSS、純格式整理等投影層變更不得更新此欄。
- **新寫入或新的實質更新一律使用 RFC3339 完整 timestamp 並明確帶 timezone**，例如 `2026-10-15T19:10:00+08:00`；不得再新增只有日期的 session timestamp。
- 相容既有資料時，`YYYY-MM-DD` 與早期 `YYYY-MM-DD+HH:MM` 仍可通過 validation。這兩種格式都只代表「日精度」；後者雖帶 offset，仍沒有時分秒，不得解讀成已知的實際時間。
- 舊 evidence 的原始時間若未知，不得為了升級格式而猜測時分秒。當舊 evidence 今天有實質更新時，只把 `updated_at` 改成當下可確認的完整 timestamp；`started_at` 可繼續保留 legacy 日精度值。
- Renderer 排序時，完整 timestamp 依真實帶時區時間比較；legacy 日精度值只在內部以該日 `00:00` 作 deterministic sort floor，原始 YAML 與畫面顯示不會被改寫。未帶 offset 的 legacy 日期以本專案歷史時區 `+08:00` 作排序相容基準。
- 因此同一天若同時存在完整 timestamp 與 legacy 日精度資料，完整 timestamp 可依時分秒互相比較，並排在該日的 legacy sort floor 之前；這只是導覽排序規則，不代表推定舊資料實際發生在午夜。
- 事件日期、來源發布時間仍記在 evidence 自身對應欄位，不拿來冒充 session 更新時間。
- 首頁跨 `sessions/`、`cases/`、`comparators/`、`research/`、`proposals/` 統一排序：先 `updated_at` 新到舊，再 `started_at` 新到舊，最後以 `session.id` 與 path 作 deterministic tie-break。
- 儲存區域是資料分類，不是閱讀優先級；不得因 area 讓較舊 evidence 固定排在較新 evidence 前面。
- 目前首頁搜尋是 client-side filter，保留上述時間順序；未來若接 FTS／query projection，搜尋結果應由查詢層另行定義 relevance 排序，不反向改寫 evidence 時間欄位。

Renderer 在 `renderer/render.py`，schema 在 `schema/evidence.schema.json`。

## 原則

- facts != claims
- found != proven
- not_found != never_existed
- current web state != historical state
- one true premise != valid conclusion
- political camp != evidence quality
- correction is append/update with traceability, not silent overwrite
