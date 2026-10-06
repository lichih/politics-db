# politics-db

存放政治相關事實證據，重點不是「現在網路上找得到什麼」，而是保存：

- 某個時間點實際查到什麼；
- 某個時間點查不到什麼；
- 當時來源如何描述事件；
- 後來來源是否修改、消失或出現新資料；
- 不同案件是否採取一致的法律與執法標準。

這個 repo 同時作為 ChatGPT **Politics Project** 的外部 evidence ledger。長對話中已核實、之後可能成為論述基礎的事實，不應只留在 conversation 裡，而應按 session 歸檔。

## 目錄

- `sessions/`：依對話／研究 session 保存可重用的事實、來源、claim 與查詢紀錄；YAML 為 authoritative source。
- `cases/`：事件本身與證據時間軸。
- `comparators/`：可用於制度、司法或執法一致性比較的案件。
- `research/`：查詢過程、尚未解決的問題與「此次未找到」紀錄。
- `docs/evidence-policy.md`：證據保存與查詢紀錄規則。
- `docs/project-workflow.md`：Politics Project 與本 repo 的工作流契約。
- `sessions/_template/evidence.yaml`：session evidence 樣板。
- `schema/evidence.schema.json`：YAML 結構驗證規格。
- `renderer/`：Python + Jinja2 HTML renderer；HTML 為 projection，不進版控。
- `.github/workflows/deploy-pages.yml`：驗證、render、部署 GitHub Pages。

## 第一組資料

- 2026-10-02 信民協會「假民調電話」案：作為選舉假訊息案件的執法強度 baseline。
- 2022 周玉蔻／蔡玉真－張淑娟晶華緋聞案：法院已認定不實，作為選罷法104條執法一致性的 strong comparator。
- 2026-10-04 研究紀錄：另追蹤周玉蔻／高虹安、林靜儀／顏寬恒等案件。

核心原則：**not_found ≠ never_existed；reachable_now ≠ permanent。**


## Renderer

本機：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python renderer/render.py --check
python renderer/render.py
```

輸出在 `site/`。每次 push 到 `main` 且 evidence / renderer / schema 有變更時，GitHub Actions 會先驗證 schema 與 cross-reference，再產生 HTML 並部署 Pages。

設計原則：**YAML authoritative，HTML projection，不產生 Markdown。**
