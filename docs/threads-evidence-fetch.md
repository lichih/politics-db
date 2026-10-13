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
