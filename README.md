# JNotebookLM

JNotebookLM 是一個本地優先的 NotebookLM 風格研究工具，使用 Python 後端與 `index.html` 單頁 GUI，重點放在：

- 與本地 `llama.cpp` 的 `llama-server` OpenAI 相容 API 配合
- 上傳文件後做 chunk 向量嵌入檢索與來源引用
- 圖片 OCR
- 音訊 STT
- 影片抽音軌後再做 STT

這不是雲端 SaaS 複製品，而是可在你自己機器上擴充的本地 MVP。

## 目前功能

- 建立 notebook
- 上傳來源檔案
- 支援 `txt/md/pdf/docx/html/json/csv`
- 支援圖片 OCR
  - 預設 `pytesseract`
  - 可自行改成 `easyocr`
- 支援音訊轉文字
  - 預設 `faster-whisper`
- 支援影片抽音軌後轉文字
  - 需要系統安裝 `ffmpeg`
- 本地向量嵌入檢索
  - 預設 `fastembed`
  - 預設模型 `BAAI/bge-small-zh-v1.5`
- 將檢索結果送到 `llama.cpp` 生成回答
- 產生 `overview / faq / timeline`

## 專案結構

```text
app/
  config.py
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
run.py
requirements.txt
```

## 安裝

### 1. 建立虛擬環境

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 安裝系統依賴

- OCR:
  - `tesseract` 必須安裝到系統中，且可從命令列呼叫
- 影片 STT:
  - `ffmpeg` 必須安裝到系統中，且可從命令列呼叫

如果你要改用 `easyocr`，請額外安裝：

```powershell
pip install easyocr
```

`fastembed` 第一次使用時會下載 embedding model 到本機快取資料夾。

## llama.cpp 串接方式

建議用 `llama-server` 啟動 OpenAI 相容 API，例如：

```powershell
llama-server `
  -m F:\models\your-model.gguf `
  --host 127.0.0.1 `
  --port 8080
```

JNotebookLM 預設會呼叫：

- `http://127.0.0.1:8080/v1/models`
- `http://127.0.0.1:8080/v1/chat/completions`

如果你的埠號或 URL 不同，可用環境變數調整。

## 環境變數

```powershell
$env:JNOTEBOOKLM_HOST="127.0.0.1"
$env:JNOTEBOOKLM_PORT="8000"
$env:JNOTEBOOKLM_EMBEDDING_PROVIDER="fastembed"
$env:JNOTEBOOKLM_EMBEDDING_MODEL="BAAI/bge-small-zh-v1.5"
$env:JNOTEBOOKLM_EMBEDDING_THREADS="4"
$env:JNOTEBOOKLM_EMBEDDING_DEVICE="auto"
$env:JNOTEBOOKLM_EMBEDDING_CACHE_DIR="F:\Documents\GitHub\JNotebookLM\data\models"
$env:JNOTEBOOKLM_LLAMA_BASE_URL="http://127.0.0.1:8080"
$env:JNOTEBOOKLM_LLAMA_MODEL=""
$env:JNOTEBOOKLM_LLAMA_TIMEOUT="180"
$env:JNOTEBOOKLM_OCR_PROVIDER="tesseract"
$env:JNOTEBOOKLM_OCR_LANGUAGES="eng,chi_tra"
$env:JNOTEBOOKLM_STT_PROVIDER="faster-whisper"
$env:JNOTEBOOKLM_WHISPER_MODEL="small"
$env:JNOTEBOOKLM_WHISPER_DEVICE="auto"
$env:JNOTEBOOKLM_WHISPER_COMPUTE_TYPE="int8"
```

## 啟動

```powershell
python run.py
```

打開瀏覽器：

```text
http://127.0.0.1:8000
```

## 使用流程

1. 建立 notebook
2. 上傳文件、圖片、音訊或影片
3. 等待來源狀態變成 `ready`
4. 在 Chat 區提問
5. 或使用 `Overview / FAQ / Timeline` 按鈕整理內容

## 重要限制

- 這版已改為本地向量嵌入檢索，但仍是 SQLite + JSON 向量，還不是專門的向量資料庫
- `llama.cpp` 需要你自己先啟動 `llama-server`
- embedding model 第一次推論前可能需要先下載
- OCR 成功率依影像品質與語言包而定
- `faster-whisper` 第一次載入模型可能較慢
- 影片檔如果很大，轉錄時間會明顯增加

## 下一步建議

如果要更接近真正 NotebookLM，建議下一輪補這些：

- 專用向量資料庫或 ANN 索引
- notebook 級摘要快取
- speaker diarization
- PDF 頁碼級引用
- 引用片段高亮
- 背景工作佇列
- WebSocket 即時進度
