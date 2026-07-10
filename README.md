# GeminiFlow

GeminiFlow 是一個基於 Web Cookie 與逆向工程的高效 Gemini 客戶端與伺服器。
此專案支援完整的文字對話串流 (Streaming)、對話歷史紀錄 (Session) 以及圖片生成與下載。

## 🚀 快速開始 (Quick Start)

### 1. 安裝相依套件

請確保您已經安裝了 `uv` (Python 專案管理工具)：

```bash
uv sync
```

由於系統會使用 Playwright 進行無頭瀏覽器登入以獲取 Cookie，請確保初始化 Playwright：
```bash
uv run playwright install chromium
```

### 2. 環境變數配置

請複製環境變數範本並根據需求修改：

```bash
cp .env.example .env
```
（詳細的設定說明請參考 `.env` 檔案內部的註解）

### 3. 登入與授權 (Authentication)

系統會自動啟動無頭瀏覽器抓取 Cookie。如果發生授權失敗，您可以透過系統提示的路徑，開啟您的 Chrome/Edge 登入 Google 帳號。

> **⚠️ 嚴禁手動開啟 `--user-data-dir` 鎖死設定檔**  
> 絕對不要在 Server 或 CLI 執行期間，手動啟動 `chrome.exe` 並將設定檔指向 `user_cookies/.pw-profile`。這樣做會鎖死設定檔 (Lock Profile)，導致 Playwright 拋出 `exitCode=21` 錯誤並中斷自動 Cookie 更新流程。若您必須手動登入，請務必在執行程式前完全關閉該瀏覽器。

---

## 💻 CLI 終端機模式 (CLI Usage)

CLI 模式適合用來快速測試與終端機對話。

### 基本文字對話
```bash
uv run python cli.py chat "你好，請用繁體中文介紹你自己"
```

### 攜帶圖片提問
```bash
uv run python cli.py chat "請描述這張圖片的內容" --image ./photo.png
```

### 選擇指定的模型
```bash
# 可選模型: gemini-3-pro, gemini-3.5-flash, gemini-3-pro-image-preview
uv run python cli.py chat "講個故事" -m gemini-3.5-flash
```

### 啟用 Debug 模式 (查看詳細系統日誌)
```bash
uv run python cli.py chat "測試" --debug
```

---

## 🌐 Server 伺服器模式 (Server Usage)

Server 模式可以將 GeminiFlow 變成一個對外提供 RESTful API 的服務，並且**會自動處理所有生成的圖片下載與對外連結轉換**。

### 啟動伺服器
```bash
# 啟動並聆聽在 8080 port
uv run python server.py --host 127.0.0.1 --port 8080 --debug
```

### API 請求範例 (HTTP POST)

**一般對話 (包含 Session Id 以延續歷史對話)：**
```bash
curl -X POST http://127.0.0.1:8080/chat \
    -H "Content-Type: application/json" \
    -d '{"prompt":"記住我的名字是小明", "model":"gemini-3-pro", "session_id": "test_01"}'
```

**文字串流對話 (SSE Stream)：**
```bash
curl -N -X POST http://127.0.0.1:8080/stream \
    -H "Content-Type: application/json" \
    -d '{"prompt":"寫一首長詩", "model":"gemini-3-pro"}'
```

**圖片生成測試：**
```bash
curl -X POST http://127.0.0.1:8080/chat \
    -H "Content-Type: application/json" \
    -d '{"prompt":"畫一隻可愛的貓咪", "model":"gemini-3-pro-image-preview"}'
```
*(伺服器會自動下載生成的貓咪圖片，並回傳類似 `http://127.0.0.1:8080/images/gemini_...png` 的合法本地連結供外部存取。)*
