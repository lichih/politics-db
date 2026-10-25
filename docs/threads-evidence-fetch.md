# Threads 採證擷取工具

`tools/fetch_threads.py` 用來處理 Threads 手機版常見的短分享網址，例如：

```text
https://www.threads.com/share/BBtkG8GXY7/
```

## 原則

- **原始證據來源仍是 Threads。**
- 預設先用 Playwright/Chromium 直接載入 Threads，執行頁面 JavaScript，取得 canonical post URL 與 Threads 自己嵌入的 bootstrap JSON。
- 第三方 resolver/proxy 只作為 `auto` 模式備援 transport，不得冒充 primary source。
- 輸出保存 `original_url`、`canonical_url`、`observed_at`、transport、final URL 與原始 Threads post object。
- 抓取失敗只能記為 `blocked_or_unresolved`，不得推論貼文不存在。
- 這符合本 repo 的 `not_found ≠ never_existed` 與 `reachable_now ≠ permanent` 原則。

## 安裝

```bash
pip install playwright
python -m playwright install chromium
```

## 使用

```bash
python tools/fetch_threads.py 'https://www.threads.com/share/BBtkG8GXY7/' --mode browser --pretty
```

預設 `--mode auto`：先直接用 Chromium 讀 Threads；若 browser 路徑失敗，再嘗試 proxy fallback。

存檔：

```bash
python tools/fetch_threads.py URL --mode browser --pretty -o tmp/threads.json
```

canonical Threads URL 也可以直接輸入。

## 輸出結構

主要欄位：

- `source.original_url`
- `source.canonical_url`
- `retrieval.status`
- `retrieval.transport`
- `retrieval.final_url`
- `post.author`
- `post.content`
- `post.media`
- `post.stats`
- `raw_threads_post`

這個 JSON 是採集結果，不直接等同 `evidence.yaml`。是否升格為 session/case evidence，仍依 `docs/project-workflow.md` 處理。

---

## Threads 內 Meta AI 私訊作為研究工具

### 狀態

以下內容是 **2026-10-25 的實際觀察結果**，不是 Meta 對外承諾的正式 API contract。

在 Threads 內與 `@meta.ai` 私訊時，可觀察到它能透過一組平台內 retrieval 工具取得公開 Threads 資料。對話輸出曾明示／呈現的工具能力包括：

- `content_search`
- `fetch_posts`
- `fetch_comments`
- `fetch_profiles`

目前沒有證據足以確認這些工具的實作是否直接對應公開 Threads API；**不得把 Meta AI 私訊工具視為公開 API 的別名或保證具有相同 schema、權限、排序與完整性。**

較安全的工作模型是把 Threads 資料存取分成不同 surface：

```text
Threads production data
        |
        +-- Threads UI
        |     +-- 人類目前可見的公開頁面狀態
        |
        +-- public developer API
        |     +-- 正式 schema / scopes / rate limits / developer contract
        |
        +-- Meta AI in Threads DM
              +-- content_search
              +-- fetch_posts
              +-- fetch_comments
              +-- fetch_profiles
              +-- 自然語言查詢與跨帳號整理
```

這只是研究上的 working model；Meta AI DM 背後確切的資料服務、索引來源與權限邊界目前仍是 unknown。

### 目前觀察到的優勢

Meta AI DM 適合當作 **case discovery / retrieval agent**，尤其在需要快速掃描 Threads 內大量公開內容時。

已觀察到它可以：

- 指定公開帳號與時間範圍，拉取多篇貼文並整理時間序列。
- 同時讀多個公開帳號，做 cross-account comparison。
- 搜尋關鍵字、近似內容、同素材或同事件的公開貼文。
- 取得大量公開 replies，並回傳 comment author、timestamp、parent 關係等結構。
- 查公開 profile 的 follower 數等欄位。
- 依自然語言條件尋找候選案例，例如「follower < 20K、同24小時、quote 某篇」。
- 協助建立 matched cases、author baseline、post-level burst 等研究候選集。

這些能力很適合低成本、高頻寬的初步搜證，但**不等於資料完整，也不代表結果集合可當成母體樣本。**

### 已觀察到的限制與 failure modes

#### 1. 搜尋結果不是可靠 denominator

在實際測試中：

- 即使要求 `num_results_per_page=50`，單次 `content_search` 實際可能只回傳 2–3 筆。
- 多次中性人名搜尋合併後，回傳作者集合仍明顯受隱藏排序／retrieval 邏輯影響。
- 已知存在的帳號可能不會被同一查詢方法帶回。

因此：

- 可用來 **找 case**；
- 不可直接用來估計陣營盛行率、帳號比例、事件 prevalence；
- `0 result` 只能寫「此次搜尋未找到」。

#### 2. UI、search index、fetch 工具的數字可能不同

實際觀察過：

- Threads UI 顯示的 reply / repost / share 數，和 `content_search`、`fetch_comments` 不一致。
- `fetch_comments.total_count` 與實際回傳 records 數也可能不同。
- Meta AI 有時說某欄位 `unavailable`，但 Threads UI 當下其實直接可見。

因此：

- **目前可見狀態**優先回到 Threads UI 核對。
- 工具數字要保留來源名稱與 `observed_at`。
- 不把不同 retrieval surface 的數字混成單一「真值」。

#### 3. 曾發生 post / media 對應錯配

實際查核曾出現：

- 多篇貼文的 `media_id` 與 comments 數被 Meta AI 在整理時手動配錯。
- 重新按 post URL / post ID / media_id 對齊後才校正。

因此：

- 多貼文比較時，不信任整理後表格的 row alignment。
- 重要數字要回到 post ID / media_id 層重新校驗。

#### 4. timestamp / timezone 解讀可能不一致

實際觀察過：

- `fetch_posts` 與 `content_search` 對同一貼文的絕對時間可能相差數小時。
- 相對間隔有時一致，但時區標記／換算不可靠。

因此：

- 不用不同工具回傳的絕對 timestamp 直接做秒級因果推論。
- 若只需要先後順序，可優先使用同一 retrieval source 的相對間隔。
- 要建立歷史時間線時，必須另外校正時區與原始 timestamp semantics。

#### 5. Meta AI 的「找得到」能力強於「判斷這代表什麼」

實際查核曾出現：

- 找到「線上6.2萬、破七萬、8.2萬」等留言後，Meta AI 一度把它們推成 Threads 貼文高曝光的間接證據。
- 重新讀完整上下文後才確認，這些數字其實是在描述同場直播的同時在線人數，**不是該 Threads 貼文的 views，也不是 likes**。

因此必須分開：

```text
retrieval result
    !=
what the result proves
```

Meta AI 可以幫忙找到原文、留言、帳號與候選事件；「這份資料究竟能證明什麼」仍要依 politics-db evidence policy 重新判定。

### Evidence authority 規則

Meta AI DM 在本專案中的定位：

> **高頻寬 discovery / retrieval agent，不是 evidence authority。**

建議流程：

```text
Meta AI discovery
    -> 取得 raw URL / post ID / comment text / candidate account
    -> Threads UI 或原始公開貼文核對
    -> 自行重算 median / ratio / time interval
    -> 檢查 timestamp / source / post mapping
    -> 區分 fact / inference / unresolved
    -> 寫入 politics-db
```

具體規則：

- Meta AI 的摘要、分類、因果判斷不直接升格為 fact。
- 重要數字自己重算；尤其 median、ratio、前後窗口。
- `not_found` 不得寫成 `never_existed`。
- 現在 likes / replies 不得倒推歷史某時點也已達同數字。
- 搜尋結果集合不得自動視為 representative sample。
- 若 UI 與 Meta AI 工具數字衝突，記錄衝突與 retrieval surface，不靜默挑一個。
- Meta AI 找到的原始 URL、公開貼文、公開 reply 才是後續採證起點。
- 對重大結論仍應回到 primary source／公開頁面／可重現查詢。

### 研究價值

這個 surface 的主要價值不是取代正式 API，而是降低 Threads 研究中的 discovery 成本：

- 快速建立 author history。
- 找 post-level selective burst。
- 找同素材／同 framing comparator。
- 從 replies 找 contemporaneous clues。
- 找 cross-account sequential propagation。
- 先篩出值得進一步人工核對的 anomaly。

對本專案最實用的定位是：

> **Meta AI DM 負責「幫我們找到要查什麼」；politics-db workflow 負責「決定找到的東西能證明什麼」。**
