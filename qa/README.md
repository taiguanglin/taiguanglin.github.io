# QA 線上校稿編輯器

`https://taiguanglin.github.io/qa/` 是純前端校稿工具，會讀取此資料夾中的 `*.txt`，依 `### N. 提問內容` 與 `時間：HH:MM:SS.mmm - HH:MM:SS.mmm` 分段，並串流播放 `https://taiguanglin.github.io/lectures/QnA/<同名>.opus`。

段落格式（格式 A）：`### N.` 這一行直接放「提問內容」（不另立標題，也不寫第幾樓或誰提問）；接著是 `時間：`、`最後播放：`、`最後編輯：`，最後是 `Taiguanglin：` 與回答內容。

## GitHub PAT 權限

若只閱讀與播放音檔，不需要 token。若要按「儲存到 GitHub」把校稿內容寫回 repo，請建立 GitHub Fine-grained PAT：

1. Repository access 選 `taiguanglin.github.io`。
2. Permissions 選 `Contents: Read and write`。
3. 進入 `/qa/` 後點「設定」，貼上 PAT 並測試。

PAT 會明碼存在目前瀏覽器的 `localStorage`。這個工具設計給個人校稿使用，請不要在公共電腦保存 PAT。

## 儲存模型

- 本機草稿：編輯時會自動暫存在 `localStorage`，避免關掉分頁後丟稿。
- 正式儲存：按 `Cmd/Ctrl+S` 或「儲存到 GitHub」會透過 GitHub Contents API 直接 commit 到 `main`。
- 跨電腦續編：另一台電腦打開 `/qa/`，重新設定 PAT 後會讀取 GitHub 上的最新版本。
