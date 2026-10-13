# Threads 採證擷取工具

`tools/fetch_threads.py` 用來處理 Threads 手機版常見的短分享網址，例如：

```text
https://www.threads.com/share/BBtkG8GXY7/
```

## 原則

- **原始證據來源仍是 Threads。**
- 第三方 resolver/proxy 只記為 transport，不得冒充 primary source。
- 輸出同時保存 `original_url`、`canonical_url`、`observed_at`、transport 與原始 transport payload。
- 若抓取失敗，只能記為 `blocked_or_unresolved`，不得推論貼文不存在。
- 這符合本 repo 的 `not_found ≠ never_existed` 與 `reachable_now ≠ permanent` 原則。

目前 transport 使用 FxThreads 公開 API。FxThreads 本身使用 headless browser 解析 Threads 的新 `/share/:shareID` 格式；本工具只消費其公開 JSON API，不把它視為證據來源。

## 使用

```bash
python tools/fetch_threads.py 'https://www.threads.com/share/BBtkG8GXY7/' --pretty
```

存檔：

```bash
python tools/fetch_threads.py URL --pretty -o tmp/threads.json
```

canonical Threads URL 也可以直接輸入：

```bash
python tools/fetch_threads.py 'https://www.threads.com/@user/post/POST_ID' --pretty
```

## 輸出結構

主要欄位：

- `source.original_url`
- `source.canonical_url`
- `retrieval.status`
- `retrieval.transport`
- `post.author`
- `post.content`
- `post.media`
- `post.stats`
- `raw_transport_payload`

這個 JSON 是採集結果，不直接等同 `evidence.yaml`。是否升格為 session/case evidence，仍依 `docs/project-workflow.md` 處理。
