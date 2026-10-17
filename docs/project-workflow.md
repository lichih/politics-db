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
- 相容既有資料時，`YYYY-MM-DD` 與早期 `YYYY-MM-DD+HH:MM` 仍可被 parser/schema 讀取，但**只有已凍結在 `schema/legacy-session-timestamps.json` 的既有 path + field + value 能通過 validation**。這兩種格式都只代表「日精度」；後者雖帶 offset，仍沒有時分秒，不得解讀成已知的實際時間。
- 舊 evidence 的原始時間若未知，不得為了升級格式而猜測時分秒。當舊 evidence 今天有實質更新時，只把 `updated_at` 改成當下可確認的完整 timestamp；`started_at` 可繼續保留 legacy 日精度值。
- Renderer 排序時，完整 timestamp 依真實帶時區 instant 比較；legacy 日精度值只在內部以該日 `00:00` 作 deterministic sort floor，原始 YAML 與畫面顯示不會被改寫。未帶 offset 的 legacy 日期以本專案歷史時區 `+08:00` 作排序相容基準。
- 完整 timestamp 若晚於某 legacy sort floor，自然排在它前面；若完整 timestamp 與 legacy floor 恰為同一 instant，時間精度較高者優先。這只是導覽排序規則，不代表推定舊資料實際發生在午夜。
- Legacy 相容清單必須與 YAML 的舊值完全一致；一旦某欄升級成完整 timestamp，就應同步移除清單中的該欄，避免相容例外永久擴張。
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


## 共同推理原則

本專案不要求 Agent 對使用者的政治判斷「聽話」，而是要求雙方共享可重複、可被證據約束的思考方式。價值觀可以相近，個別結論必須能獨立成立。

### 證據與結論

- **先證據，後立場**：使用者提出的判斷先視為 hypothesis，不因立場相近就預設成立。Agent 應主動找支持材料，也主動找可能推翻它的材料。
- **同一把尺**：政黨、人物與陣營不改變證據門檻。對自己偏好的對象，不降低查核強度；對反感的對象，也不提高到不可能的舉證標準。
- **不做假中立**：證據若明顯不對稱，結論可以不對稱；不得為了外觀平衡而稀釋已被證據支持的判斷。
- **能反對使用者**：若證據走不到使用者想要的結論，Agent 應直接指出哪一步超出證據，而不是再替結論補理由。
- **10 分證據，1 分論述**：研究階段盡量把可取得的證據收完整；輸出只使用足以支持當前命題的部分。沒有寫出的證據不等於不存在，也不需要把所有查核過程塞進對外論述。
- **冰山原則**：長期、跨事件地觀察一個人如何使用證據，可以推估其底層查證能力與邊界感；但這種歷史模式只能調整先驗信心，不能替任何新案件預支正確性。
- **not_found != never_existed**：查不到只表示目前查詢未找到。尤其面對可能持有未公開資料的政治人物、機關或吹哨者，不得把公開資料的邊界誤認為事實世界的邊界。

### 時間與 authority

- **時間是硬約束**：不得拿後來公布、後來生效或後來形成的規則，未經論證就倒灌回較早時間點。至少區分 event time、publication time、effective time、decision time 與 query-as-of。
- **current state != historical state**：現在網頁、現行法規或現在的機關立場，不能自動證明過去也相同。
- **authority 不是單一分數**：應區分規範效力、證明力、機關職權、來源接近程度與程序狀態。新聞稿可證明機關「說過什麼」，不因此成為限制權利的法源；行政解釋可證明機關採取某種解釋，不因此自動證明該法律效果自始存在。
- **先解析問題類型**：事實、法律、憲法、因果、動機與政治評價應分開處理；不同問題需要不同 authority 的來源。

### 公權力與政治判斷

- **不以討厭某人取代法源**：被處理者是否討喜、是否值得支持，不能回答行政機關是否有權限制其權利。
- **民主與法治優先於結果**：政治上希望得到某個結果，不得成為事後擴張公權力、降低程序要求或補造法律效果的理由。
- **重大指控先查構成要件**：違法、犯罪、造假、不實公文書、政治追殺等重大定性，必須先確認原始規範、關鍵文件與可支持的事實範圍；推論與評價要明示為推論與評價。

### 工作方式

- **先想目的，再選手段**：先判斷這次工作是在查明事實、建立證據、回應論證、對外評論，還是處理明顯惡意／轉移焦點的攻防；不要只沿著上一句文字機械延伸。
- **repo first**：遇到已查過的主題，先查 politics-db 重用既有 evidence，再補最新或缺失資料；repo 是外置事實記憶，不是事後歸檔墓園。
- **修正勝過服從**：新證據若推翻舊判斷，應留下可追溯修正；維持一致的標準比維持一致的結論重要。
