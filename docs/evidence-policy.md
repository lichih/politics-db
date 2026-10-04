# Evidence policy

politics-db 記錄的是「在特定時間點可驗證到的證據與查詢結果」，不是把目前網路狀態倒推成歷史事實。

## 核心規則

1. **observed_at 必填**：每一個來源、查詢結果與「找不到」紀錄都要附觀察時間。
2. **not_found ≠ never_existed**：某次查詢沒有找到資料，只能表示「用當時的查詢方法沒有找到」，不得寫成「從未存在」。
3. **reachable_now ≠ permanent**：現在可存取的網頁、新聞、政府文件，未來可能修改、搬移或消失，所以至少保存標題、來源、URL、日期、關鍵事實摘要與觀察時間。
4. **區分來源層級**：
   - primary：法院、檢察署、政府機關、法規、當事人原始內容。
   - secondary：新聞媒體、研究文章、第三方整理。
   - commentary：評論、社群轉述。
5. **區分事實與推論**：資料庫保存「來源說了什麼」；分析檔再處理「可以推出什麼」。
6. **保留矛盾**：後來出現相反資料時，不覆蓋舊紀錄；新增較晚的觀察與更正。
7. **避免事後改寫歷史**：若來源後來刪除、修改或搜尋不到，要保留先前曾經可查得的紀錄；反過來，今天找不到也不得推論過去一定不存在。

## 建議欄位

- case_id
- claim_id
- observed_at
- event_date / published_at
- source_type
- publisher
- title
- url
- retrieval_status: reachable | not_found | removed | blocked | changed
- evidence_summary
- excerpt（必要時短引）
- verification_notes
- related_claims
- supersedes / contradicted_by

## 查詢紀錄

對「沒有找到」也要留下：
- 查詢日期時間
- 搜尋平台／資料庫
- 使用的 query
- 查詢範圍
- 結果數或代表性結果
- 結論只能寫成「此次查詢未找到」

這讓日後可以分辨：
- 當時真的沒有公開資料；
- 當時有但後來消失；
- 當時只是搜尋方法沒找到；
- 後來才新增／公開的資料。
