# JNotebookLM

JNotebookLM 現在是 **本地優先 Notebook + Design Studio** 的 Python 專案：

- 左欄管理來源與 notebook
- 中欄進行檢索問答
- 右欄進行 Studio 產出（Overview/FAQ/Timeline + Huashu Local Studio）

---

## 這次重構重點

### 1. 抽 Huashu 的設計方法

已落地到 `DesignStudioService`：

- `方向顧問 Fallback`：一次輸出 3 個差異化方向（色彩 / 字型 / 敘事）
- `多模式設計產物`：`prototype / slides / motion / infographic`
- `5 維度專家評審`：哲學一致性 / 視覺層級 / 細節執行 / 功能性 / 創新性
- `Tweaks 可調參`：採用 EDITMODE block，透過 API 即時套用
- `反 AI slop` 提示約束：避免 generic 風格，強化有意圖的視覺語言

### 2. 抽 Open CoDesign 的工程骨架

已落地到 Python 本地架構：

- `Design as Session`：每個設計任務都是 session
- `Workspace on disk`：每個 session 都有自己的本地 workspace
- `DESIGN.md baton`：每個 workspace 內都有可持續更新的設計系統檔
- `JSONL history`：session 事件可回放 (`data/design/sessions/<session_id>.jsonl`)
- `SQLite metadata`：session/artifact/event 狀態查詢與 UI 切換

---

## 專案結構

```text
app/
  config.py
  design_service.py        # Huashu 方法 + Open CoDesign 骨架的 Python 落地
  embeddings.py
  llama_client.py
  main.py
  retrieval.py
  schemas.py
  services.py
  storage.py
  text_extract.py
static/
  index.html               # 三欄版面：左來源 / 中對話 / 右Studio
  app.js
  styles.css
run.py
requirements.txt
```

---

## 本地資料目錄

```text
data/
  jnotebooklm.db
  uploads/
  texts/
  models/
  design/
    workspaces/
      <session-slug-id>/
        DESIGN.md
        brief.md
        artifacts/
    sessions/
      <session-id>.jsonl
```

---

## API（新增設計工作流）

- `GET /api/design/sessions`
- `POST /api/design/sessions`
- `GET /api/design/sessions/{session_id}`
- `POST /api/design/sessions/{session_id}/advisor`
- `POST /api/design/sessions/{session_id}/artifacts`
- `GET /api/design/sessions/{session_id}/artifacts/{artifact_id}/content`
- `POST /api/design/sessions/{session_id}/artifacts/{artifact_id}/critique`
- `POST /api/design/sessions/{session_id}/artifacts/{artifact_id}/tweaks`

---

## 既有 Notebook 功能（保留）

- 建立 notebook
- 上傳來源檔案 (`txt/md/pdf/docx/html/json/csv`)
- 圖片 OCR、音訊 STT、影片抽音軌後 STT
- 向量檢索 + llama.cpp 回答
- 產生 `overview / faq / timeline`

---

## 安裝

### 1. 建立虛擬環境

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 安裝系統依賴

- OCR: `tesseract`
- 影片 STT: `ffmpeg`

### 3. 啟動 llama.cpp 相容 API（例如 `llama-server`）

```powershell
llama-server `
  -m F:\models\your-model.gguf `
  --host 127.0.0.1 `
  --port 8080
```

### 4. 啟動服務

```powershell
python run.py
```

打開：`http://127.0.0.1:8000`

---

## 環境變數（節錄）

```powershell
$env:JNOTEBOOKLM_HOST="127.0.0.1"
$env:JNOTEBOOKLM_PORT="8000"
$env:JNOTEBOOKLM_LLAMA_BASE_URL="http://127.0.0.1:8080"
$env:JNOTEBOOKLM_LLAMA_MODEL=""
$env:JNOTEBOOKLM_OCR_PROVIDER="tesseract"
$env:JNOTEBOOKLM_STT_PROVIDER="faster-whisper"
$env:JNOTEBOOKLM_EMBEDDING_MODEL="BAAI/bge-small-zh-v1.5"
```

---

## 目前限制

- 設計產物先以 HTML 為主，尚未補齊 PPTX/PDF 自動匯出流水線
- 設計生成品質仍受本地模型能力影響
- 若模型離線，Design Studio 會回退到本地模板與規則評估

---

## 下一步建議

- 補上 HTML→PPTX/PDF 的 Python 匯出器
- 增加多檔案 artifact 編排（landing + pricing + onboarding）
- 加入 Playwright 視覺驗證流程（生成後自檢）
