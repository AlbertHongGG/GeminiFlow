# GeminiFlow

GeminiFlow 是基於 Google Gemini 網頁端通訊協定逆向之高效能 Python 客戶端與 RESTful 伺服器，支援內嵌 V8 Web Attestation（Botguard）自動證明、HTTP/2 原生串流（Streaming）、多輪對話會話（Session）與多模態圖片生成/下載。

---

## 1. 快速開始 (Quick Start)

### 1.1 安裝相依環境
專案使用 `uv` 進行套件與環境管理：
```bash
uv sync
uv run playwright install chromium
```

### 1.2 環境變數配置
複製設定範本並檢視設定：
```bash
cp .env.example .env
```

### 1.3 認證與安全性注意事項
系統於 Cookie 失效時會透過 Playwright 自動啟動無頭瀏覽器更新。
- **嚴禁手動開啟鎖定設定檔**：絕不可在程式執行期間，手動啟動 `chrome.exe` 並將 `--user-data-dir` 指向 `user_cookies/.pw-profile`，否則將觸發設定檔鎖定（Profile Lock）與 Playwright `exitCode=21` 錯誤。

---

## 2. 支援模型與思考模式 (Supported Models)

系統支援透過名稱簡稱或完整識別碼自動解析：

| 模型簡稱 | 完整模型名稱 | Model ID | 特性說明 |
| :--- | :--- | :---: | :--- |
| `flash-lite` | `gemini-3.5-flash-lite` | 1 | 回覆最快、極速輕量化通道 |
| `flash` | `gemini-3.8-flash` | 1 | 預設模型、全方位協助、高吞吐量 |
| `pro` | `gemini-3-pro` / `3.1 Pro` | 6 | 深度推論、進階程式碼生成與複雜邏輯分析 |
| `argon` | `gemini4Argon` / `4 Argon` | 8 | 次世代旗艦推論模型、複雜任務 |

**思考模式等級（Thinking Level）**：
- `low`（預設，值為 1）：標準快速回應。
- `medium`（值為 4）：中等深度推論。
- `high`（值為 2）：最大深度推理（適合複雜演算法與長鏈思考）。

---

## 3. CLI 命令列模式 (CLI Usage)

入口檔案為 `cli.py`，子命令 `chat` 用於終端即時串流互動。

### 3.1 參數清單
```text
python cli.py chat <prompt> [選項]

位置參數:
  prompt                 使用者輸入提示詞 (必填)

選用參數:
  -m, --model            模型名稱 (預設: gemini-3.8-flash，支援 flash, pro, argon, flash-lite)
  -t, --thinking         思考模式等級 (low, medium, high，預設: low)
  --image                附加本機圖片路徑 (可重複傳入多次，例如: --image a.png --image b.jpg)
  --lang                 語言代碼 (預設: zh-TW)
  --session-id           指定對話會話識別碼 (維持多輪上下文歷史)
  --system-prompt        設定系統提示詞 (約束回覆風格與角色設定)
  --debug                啟用詳細除錯日誌輸出
```

### 3.2 常見指令範例

**基本對話 (預設 Flash 模型):**
```bash
uv run python cli.py chat "你好，請用一句話介紹你自己"
```

**指定 3.1 Pro 進行進階程式設計:**
```bash
uv run python cli.py chat "寫出一個 Python 非同步連線池範例" -m pro
```

**啟用 Argon 高強度思考模式:**
```bash
uv run python cli.py chat "請嚴謹證明根號2是無理數" -m argon -t high
```

**延續會話歷史 (多輪對話):**
```bash
# 第一輪：記住資訊
uv run python cli.py chat "我的代號是 Falcon-9" --session-id "sess_001"

# 第二輪：延續上下文提問
uv run python cli.py chat "我的代號是什麼？" --session-id "sess_001"
```

**帶圖多模態提問:**
```bash
uv run python cli.py chat "描述這張架構圖的核心組件" --image ./architecture.png
```

**指定系統提示詞與繁體中文語系:**
```bash
uv run python cli.py chat "請評估此方案優缺點" --system-prompt "你是一位具備 20 年經驗的分散式系統架構師" --lang zh-TW
```

---

## 4. Server 伺服器模式 (Server Usage)

入口檔案為 `server.py`，提供符合 RESTful 與 Server-Sent Events (SSE) 標準之 HTTP API 服務。

### 4.1 啟動參數
```text
python server.py [選項]

選用參數:
  --host                 伺服器監聽 IP (預設: 127.0.0.1)
  --port                 伺服器監聽連接埠 (預設: 5000)
  --debug                啟用除錯模式日誌
```

啟動指令範例：
```bash
uv run python server.py --host 0.0.0.0 --port 5000
```

### 4.2 HTTP API 端點規範

#### 端點一：健康檢查
- **路徑**: `GET /health`
- **回傳**: `{"ok": true}`

#### 端點二：同步對話 (`POST /chat`)
等待模型完整生成完畢後回傳完整 JSON。

**請求體 JSON 欄位規格:**
| 欄位名稱 | 型態 | 必填 | 預設值 | 說明 |
| :--- | :---: | :---: | :---: | :--- |
| `prompt` | string | 是 | - | 提示詞內容 |
| `model` | string | 否 | `gemini-3.8-flash` | 模型名稱 (`flash`, `pro`, `argon` 等) |
| `thinking` | string | 否 | `low` | 思考模式 (`low`, `medium`, `high`) |
| `system_prompt` | string | 否 | null | 系統提示詞 |
| `session_id` | string | 否 | null | 會話 ID，指定時可維持多輪歷史紀錄 |
| `language` | string | 否 | `zh-TW` | 回應語言 |
| `images` | array | 否 | [] | 圖片 Base64 字串陣列 (上限 50MB) |
| `auto_refresh_cookies` | bool | 否 | true | Cookie 失效時是否自動啟動無頭瀏覽器刷新 |

**cURL 呼叫範例:**
```bash
curl -X POST http://127.0.0.1:5000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "請比較 REST 與 GraphQL 的適用場景",
    "model": "pro",
    "session_id": "session_api_demo"
  }'
```

**回傳 JSON 範例:**
```json
{
  "text": "REST 與 GraphQL 適用於不同維度的系統架構需求...",
  "images": []
}
```

#### 端點三：SSE 串流對話 (`POST /stream`)
基於 Server-Sent Events（SSE）之即時字元串流。

**請求體 JSON 欄位規格:**
與 `POST /chat` 完全一致。

**cURL 呼叫範例:**
```bash
curl -N -X POST http://127.0.0.1:5000/stream \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "寫一則快速排序法 (QuickSort) 的 Python 實作",
    "model": "flash"
  }'
```

**SSE 事件格式:**
- `event: text`：文字片段，資料內容為 `{"chunk": "文字"}`。
- `event: image`：生成的圖片 URL，資料內容為 `{"url": "http://127.0.0.1:5000/images/gemini_...png"}`。
- `event: done`：生成完畢通知，資料內容為 `{}`。
- `event: error`：錯誤通知，資料內容為 `{"error": "錯誤描述", "status": 401}`。

#### 端點四：靜態圖片存取
- **路徑**: `GET /images/<filename>`
- **說明**: 當模型生成圖片時，伺服器會自動下載高解析度原圖（`=s0-d`）存於本機輸出目錄，並映射為此靜態路由供外部下載。

---

## 5. 自動化測試 (Testing)

執行全套單元測試與協定整合測試：
```bash
uv run python -m unittest discover tests
```

---

## 6. 技術文檔與架構白皮書 (Documentation)

詳細的逆向分析日誌、通訊協定規範與架構遷移手冊收錄於 `docs/` 目錄：
- [docs/README.md](docs/README.md)：版本更新與高頻異動架構排查手冊（Botguard、V8 Stubs、Model ID/Hash 異動 SOP）。
- [docs/botguard_investigation_and_latency_analysis.md](docs/botguard_investigation_and_latency_analysis.md)：全鏈路延遲排查、HTTP/2 串流邊界與 3.1 Pro 路由遷移實錄。
- [docs/botguard_and_payload_attestation_analysis.md](docs/botguard_and_payload_attestation_analysis.md)：Botguard Web Attestation 逆向工程、Content-Bound 雜湊演算與內嵌 V8 引擎架構白皮書。
- [docs/packet_analysis_and_latency_investigation_20261015.md](docs/packet_analysis_and_latency_investigation_20261015.md)：瀏覽器封包模式對齊分析技術報告。
