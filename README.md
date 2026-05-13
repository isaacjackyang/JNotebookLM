# JNotebookLM

JNotebookLM 是本地優先的 Notebook + Design Studio 專案，整合：

- Notebook 來源管理與向量檢索問答
- `llama.cpp` 相容聊天 API
- OCR / STT / 影片抽音軌流程
- Huashu Local Studio 設計工作區
- 可持久化的設定頁與一鍵啟動腳本

## 主要功能

### Notebook

- 建立、重新命名、刪除 notebook
- 上傳 `txt / md / pdf / docx / html / json / csv`
- 圖片 OCR、音訊 STT、影片抽音軌後 STT
- `fastembed` 向量嵌入檢索
- 產生 `overview / faq / timeline`
- 回答附來源片段引用

### Design Studio

- 建立設計 session
- 方向顧問一次產生 3 個設計方向
- 生成 `prototype / slides / motion / infographic`
- 5 維度評審
- `EDITMODE` tweaks 套用
- session / artifact / event 落地到本地 workspace 與 SQLite

### Runtime / UX

- `run.py` 會優先切到 repo 內 `.venv`
- 服務就緒後自動開啟瀏覽器
- `install.cmd` 做第一次安裝
- `start.cmd` 固定用 `7000` 啟動
- GUI 右上角齒輪可調整模型與處理細節
- 設定保存於 `data/app-settings.json`

## 專案結構

```text
app/
  config.py
  design_service.py
  embeddings.py
  llama_client.py
  main.py
  retrieval.py
  schemas.py
  services.py
  storage.py
  text_extract.py
static/
  index.html
  app.js
  styles.css
data/
install.cmd
start.cmd
run.py
requirements.txt
```

## 安裝

第一次使用建議直接執行：

```powershell
.\install.cmd
```

它會：

- 建立 `.venv`
- 升級 `pip`
- 安裝 `requirements.txt`
- 檢查 `ffmpeg`
- 檢查 `tesseract`

如果你想手動安裝：

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 系統依賴

- OCR 需要 `tesseract`
- 音訊 / 影片處理需要 `ffmpeg`

如果缺少系統工具，應用程式仍可啟動，但相關功能會失效或回報警告。

## llama.cpp

請先啟動相容 OpenAI API 的 `llama.cpp` 服務，例如：

```powershell
llama-server `
  -m F:\models\your-model.gguf `
  --host 127.0.0.1 `
  --port 8080
```

預設設定：

- `JNOTEBOOKLM_LLAMA_BASE_URL=http://127.0.0.1:8080`

## 啟動

最短路徑：

```powershell
.\start.cmd
```

或：

```powershell
python run.py
```

預設會開啟：

- [http://127.0.0.1:7000](http://127.0.0.1:7000) 使用 `start.cmd`
- [http://127.0.0.1:8000](http://127.0.0.1:8000) 使用 `python run.py` 且未覆寫 port

如果不想自動開瀏覽器：

```powershell
$env:JNOTEBOOKLM_AUTO_OPEN="0"
python run.py
```

## 設定頁

右上角齒輪可調整：

- server host / port
- retrieval chunk size / overlap / top-k
- embedding provider / model / threads / device / cache dir
- `llama.cpp` base URL / model / timeout / API key
- OCR provider / languages
- STT provider / whisper model / device / compute type

API：

- `GET /api/settings`
- `PUT /api/settings`

注意：

- `host` 和 `port` 變更後需要重啟服務才會生效
- embedding 相關設定變更後，下一次檢索會自動重建 embedding client

## 其他 API

- `GET /api/health`
- `GET /api/notebooks`
- `POST /api/notebooks`
- `PUT /api/notebooks/{notebook_id}`
- `DELETE /api/notebooks/{notebook_id}`
- `GET /api/notebooks/{notebook_id}`
- `POST /api/notebooks/{notebook_id}/sources`
- `POST /api/notebooks/{notebook_id}/chat`
- `POST /api/notebooks/{notebook_id}/generate`
- `GET /api/design/sessions`
- `POST /api/design/sessions`
- `GET /api/design/sessions/{session_id}`
- `POST /api/design/sessions/{session_id}/advisor`
- `POST /api/design/sessions/{session_id}/artifacts`
- `GET /api/design/sessions/{session_id}/artifacts/{artifact_id}/content`
- `POST /api/design/sessions/{session_id}/artifacts/{artifact_id}/critique`
- `POST /api/design/sessions/{session_id}/artifacts/{artifact_id}/tweaks`

## 目前限制

- OCR 依賴系統級 `tesseract`
- 設計產物目前以 HTML 為主，尚未補齊 PPTX / PDF 匯出
- 若 `llama.cpp` 離線，Notebook 與 Design Studio 會回退到本地摘要或模板流程
