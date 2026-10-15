# GeminiFlow 版本更新與高頻異動架構排查手冊 (Architecture Fragility & Migration Guide)

文件版本: 1.0.0  
記錄日期: 2026-10-15  
適用範疇: Google Gemini Web 端通訊協定更新、版本遷移、端點變更與日常維運排查  
文件定位: 當 Google 網頁端更新導致 API 異常（如 120 秒逾時、罐頭拒答、連線中斷、驗證失敗）時的核心檢核索引與排查指南。

---

## 1. 概述與架構脆弱性矩陣 (Architecture Fragility Matrix)

GeminiFlow 採用純 Python 模擬 Google 網頁端客戶端協定。由於 Google 網頁端並非公開穩定 API，後端叢集與前端腳本頻繁進行 A/B 測試、安全防護升級與模型路由遷移。

在每次 Google 網頁端大版本更新時，系統內部不同模組受影響的機率存在顯著差異。以下為高頻異動項目的脆弱性分級矩陣：

| 異動頻率 | 核心檢查模組 | 關鍵檢查項目 | 典型異常現象 | 對應源碼路徑 |
| :---: | :--- | :--- | :--- | :--- |
| **極高** | **模型路由層** | Model ID、Model Hash、Thinking Level | 模型回傳罐頭拒答（「我只是個語言模型」、「超出能力範圍」） | [models.py](../gemini_flow/domain/models.py) |
| **極高** | **初次交握層** | `SNlM0e`、`server_bl`、`at_token`、`f.sid` | 登入態失效、401/403 錯誤、WAA Challenge 抓取失敗 | [gemini_auth.py](../gemini_flow/infrastructure/auth/gemini_auth.py) |
| **高** | **串流協定解析層** | HTTP/2 結束訊框標記（`di`, `e` 陣列位置） | 請求卡住長達 120 秒直到逾時中斷 | [parser.py](../gemini_flow/infrastructure/clients/gemini_api/parser.py) |
| **高** | **多態虛擬機環境** | DOM/BOM 樁（Stubs）、Iframe 生命週期 | V8 直譯器崩潰（`VmExecutionError`）、`E:... is not a function` | [environment_stubs.py](../gemini_flow/infrastructure/attestation/environment_stubs.py) |
| **中高** | **Web Attestation** | WAA API RPC ID（`koxg5`）、Challenge 結構 | 證明過期無法更新、400 Bad Request、驗證碼取得失敗 | [waa_client.py](../gemini_flow/infrastructure/attestation/waa_client.py) |
| **中** | **JSPB 標頭層** | `x-goog-ext-525001261-jspb`（20 元素陣列） | 標頭校驗失敗、請求被 Google 閘道直接拋棄 | [header_builder.py](../gemini_flow/infrastructure/clients/gemini_api/protocol/header_builder.py) |
| **中** | **99 元素 JSPB 負載** | `f.req` 欄位移位、靜態常數變更 | 後端解析失敗、返回空內容或非預期錯誤 | [payload_builder.py](../gemini_flow/infrastructure/clients/gemini_api/protocol/payload_builder.py) |
| **中低** | **傳輸層指紋** | TLS/JA3 指紋、Chrome 版本模擬、標準標頭 | GFE 閘道 Tarpit Delay（75~170 秒慢速佇列） | [http_client.py](../gemini_flow/infrastructure/clients/http_client.py) |

---

## 2. 核心高頻異動項目深度解析與排查指引

### 2.1 模型路由識別碼與端點雜湊 (Model ID & Model Hash)

#### 項目意義與系統作用
Google 網頁端透過一組雙重識別機制來將使用者的推理請求精確導向對應的伺服器叢集：
1. **Model ID**：整數標記，置於 `f.req[79]` 陣列與 `x-goog-ext-525001261-jspb[14]` 擴展標頭中。
2. **Model Hash**：16 位十六進位字串，置於 `x-goog-ext-525001261-jspb[4]` 擴展標頭中，代表 Google GFE（Google Frontend Edge）負載平衡通道簽名。

#### 異動機制與觸發情境
當 Google 推出新模型（例如由 Gemini 1.5 升級為 3.1 Pro，或更新 3.8 Flash、4 Argon）時，後端通常會指派全新的 ID 與通道 Hash。
- **降級現象**: 若持續發送舊版 ID（如舊版 Pro 的 ID `3` 與 Hash `e6fa609c3fa255c0`），Google 會將請求導向舊版受限通道。當輸入需要深度推理或寫程式碼的任務時，後端安全檢查員會直接攔截並返回罐頭拒答：
  `這個要求已經超出我的能力範圍，我只能產生文字。`
- **對齊標準**: 必須將其更新至現代生產環境值（如 3.1 Pro 改為 ID `6` 與 Hash `8c46e95b1a07cecc`）。

#### 檢查與排查步驟
1. 於 Chrome 瀏覽器開啟 `https://gemini.google.com/app`，開啟 DevTools Network 分頁。
2. 切換至目標模型並發送任意一句測試訊息。
3. 尋找 `StreamGenerate` 請求，檢視 Request Headers 中的 `x-goog-ext-525001261-jspb`:
   - 提取索引 `[4]`（Model Hash）與索引 `[14]`（Model ID）。
4. 檢視 Request Payload 中 `f.req` 陣列解碼後的索引 `[79]`（Model ID）與索引 `[80]`（Thinking Level）。
5. 檢查 [gemini_flow/domain/models.py](../gemini_flow/domain/models.py) 中 `ModelFamily` 的 `model_id` 與 `model_hash` 定義是否吻合。

---

### 2.2 初次交握金鑰與伺服器建置標記 (First Handshake: SNlM0e, at_token, server_bl)

#### 項目意義與系統作用
客戶端要與 Google 後端建立合法會話，必須先向 `https://gemini.google.com` 進行 GET 請求，自 HTML 頁面中提取內嵌於 `WIZ_global_data` 的全域會話金鑰：
1. **`SNlM0e`**: 會話 CSRF 防護金鑰（亦即 `at_token`），所有後續的 batchexecute 與 StreamGenerate 均必須在 Payload 中附帶 `at` 欄位。
2. **`f.sid`**: Google 內部使用者會話識別碼。
3. **`server_bl`**: 伺服器建置版本字串（例如 `boq_gemini-web-uiserver_20261012.19_p1`）。此字串必須與 URL 查詢參數 `bl`、標頭 `525001261[17]` 保持一致，否則會遭到閘道拒絕。

#### 異動機制與觸發情境
1. Google 每次部署前端前端代碼（每日數次），`server_bl` 就會更新。若客戶端使用過期的 `server_bl`，部分新啟用的 RPC 功能將失敗。
2. Google 前端偶爾會重構 `WIZ_global_data` 的序列化格式（例如從傳統的 `window.WIZ_global_data = {...}` 改為閉包變數或基於 JSON 的 `<script nonce>` 標籤），導致正則表達式匹配失敗。

#### 檢查與排查步驟
1. 檢視 [gemini_flow/infrastructure/auth/gemini_auth.py](../gemini_flow/infrastructure/auth/gemini_auth.py) 中的正則解析器。
2. 透過以下命令檢驗目前帳號 Cookie 是否能成功擷取握手憑證：
   ```powershell
   .\.venv\Scripts\python.exe -c "
   import asyncio
   from gemini_flow.config import AppConfig
   from gemini_flow.infrastructure.clients.http_client import HttpClient
   from gemini_flow.infrastructure.storage.file_cookie_store import FileCookieStore
   from gemini_flow.infrastructure.auth.gemini_auth import GeminiAuthService
   from gemini_flow.infrastructure.browser.playwright_browser import PlaywrightWebBrowser

   async def test():
       config = AppConfig.from_env()
       async with HttpClient(proxy=config.proxy) as http:
           browser = PlaywrightWebBrowser(config.cookies_dir / '.pw-profile')
           store = FileCookieStore(config.cookies_dir)
           auth = GeminiAuthService(config.cookies_dir, store, http, browser)
           tokens = await auth.get_auth_session()
           print('SNlM0e:', bool(tokens.snlm0e), 'Length:', len(tokens.snlm0e) if tokens.snlm0e else 0)
           print('server_bl:', tokens.server_bl)
           print('sid:', tokens.sid)

   asyncio.run(test())
   "
   ```
3. 若 `SNlM0e` 或 `server_bl` 為 None，必須重新檢視網頁原始碼中儲存該資訊的最新 HTML 標籤結構。

---

### 2.3 Web Attestation (Botguard) 通訊協定與動態 Challenge

#### 項目意義與系統作用
Google Web Attestation（WAA / Botguard）是用於防止非瀏覽器腳本濫用 API 的核心防禦層。
在發送聊天請求前，客戶端必須向 `/_/BardChatUi/data/batchexecute`（攜帶 RPC ID `koxg5`）發送請求，取得一組包含：
1. **動態虛擬機腳本位址**（如 `https://www.gstatic.com/delight/bg/.../challenge.js`）
2. **多態二進位 Bytecode**（base64 編碼字串）

#### 異動機制與觸發情境
1. **RPC ID 變更**: Google 可能將 `koxg5` 更換為新的 RPC 識別碼。
2. **Response 陣列結構變更**: batchexecute 回應為 JSPB 字串陣列，Challenge 預設解析路徑為 `parsed[0][2]`。若 Google 在外層增加包裝陣列，原解析器將拋出 `IndexError` 或 `KeyError`。
3. **快取過期（TTL）**: Google Challenge 通常具有約 10~15 分鐘的有效期限。過期後伺服器會拒絕使用該 Challenge 生成的 Token。

#### 檢查與排查步驟
1. 檢視 [gemini_flow/infrastructure/attestation/waa_client.py](../gemini_flow/infrastructure/attestation/waa_client.py)。
2. 驗證是否能順利下載 Challenge 並提取 bytecode：
   ```powershell
   .\.venv\Scripts\python.exe -c "
   import asyncio
   from gemini_flow.infrastructure.attestation.waa_client import WaaClient
   async def test():
       client = WaaClient()
       ch = await client.fetch_challenge()
       print('Interpreter Hash:', ch.interpreter_hash)
       print('Bytecode Length:', len(ch.bytecode))
   asyncio.run(test())
   "
   ```

---

### 2.4 V8 引擎多態字節碼直譯與 DOM 樁環境 (Environment Stubs)

#### 項目意義與系統作用
Botguard VM 是一套在 JavaScript 中執行的高混淆虛擬機。為了脫離臃腫的無頭瀏覽器（Playwright），本專案在 Python 進程內透過 `py_mini_racer` 內嵌 Google V8 引擎，並在 [gemini_flow/infrastructure/attestation/environment_stubs.py](../gemini_flow/infrastructure/attestation/environment_stubs.py) 提供全套 DOM、BOM、Screen、Canvas、Audio 等瀏覽器 API 模擬樁（Polyfills）。

#### 異動機制與觸發情境
Google 會頻繁更新 Botguard bytecode 的環境探測指紋以偵測 Node.js / V8 虛擬環境：
1. **原生方法探測**: Google 會以非標準參數調用 DOM 方法，例如 `document.createElement(null)`。若 Polyfill 直接調用 `tag.toUpperCase()`，將拋出 `TypeError` 導致整個 VM 初始化崩潰（`E:tag.toUpperCase is not a fun`）。
2. **非同步事件掛載**: Google 會將動態子直譯器掛載於 `iframe.onload = callback`，若缺少 `onload` setter 與自動觸發，VM 將永久等待事件。
3. **加密與時間指紋**: VM 依賴 `performance.now()`、`crypto.getRandomValues()` 與高解析度時間戳計時來防禦除錯。

#### 檢查與排查步驟
1. 檢視 [gemini_flow/infrastructure/attestation/environment_stubs.py](../gemini_flow/infrastructure/attestation/environment_stubs.py) 與 [gemini_flow/infrastructure/attestation/v8_runtime.py](../gemini_flow/infrastructure/attestation/v8_runtime.py)。
2. 執行內嵌 V8 簽名器冒煙測試：
   ```powershell
   .\.venv\Scripts\python.exe -c "
   import asyncio
   from gemini_flow.infrastructure.attestation.v8_signer import EmbeddedV8TokenSigner
   async def test():
       signer = EmbeddedV8TokenSigner()
       token = await signer.sign('test prompt')
       print('Token Prefix:', token.token[:10])
       print('Token Length:', len(token.token))
       print('Salt:', token.salt)
       assert token.token.startswith('!'), 'Token must start with !'
       print('V8 Botguard Attestation: OK')
   asyncio.run(test())
   "
   ```
3. 若出現 `VmExecutionError`，需檢視錯誤訊息中是否有 `E:...`，判定是哪個 DOM/BOM 樁屬性遺失或拋出例外。

---

### 2.5 內容綁定雜湊演算與鹽值對齊 (Content-Bound Query Hash & Salt)

#### 項目意義與系統作用
Botguard Token 具備強大的**防重放（Anti-Replay）**與**內容綁定（Content-Bound）**特性：
$$\text{salt} = \text{random\_bytes}(16).\text{hex}()$$
$$\text{qh} = \text{SHA256}(\text{effective\_prompt} + \text{salt})$$
- `qh` 與 `cid`（會話 ID）作為參數傳入 V8 虛擬機：`bgObj.invoke(..., [{ qh: qh, cid: cid }])`
- 虛擬機產出加密權杖置於 `f.req[3]`。
- 明文 `salt` 置於 `f.req[4]`。
- 實際發送的文字置於 `f.req[0][0]`。

#### 異動機制與觸發情境
後端收到請求後，利用私鑰解密 `f.req[3]`，並重新計算 `f.req[0][0] + f.req[4]` 的雜湊值進行字元級校驗。
- **脫節隱患**: 若 `effective_prompt` 在領域層、簽名層與封包建構層有任何空格、換行或 System Prompt 格式化不一致，伺服器校驗失敗後將直接拒絕推理或將連線丟入靜默黑洞。

#### 檢查與排查步驟
1. 檢查 [gemini_flow/domain/entities.py](../gemini_flow/domain/entities.py) 的 `ChatRequest.effective_prompt`。
2. 確保 [gemini_flow/infrastructure/clients/gemini_api/api_client.py](../gemini_flow/infrastructure/clients/gemini_api/api_client.py) 與 [gemini_flow/infrastructure/clients/gemini_api/protocol/protocol_engine.py](../gemini_flow/infrastructure/clients/gemini_api/protocol/protocol_engine.py) 均使用該屬性作為唯一真相來源。
3. 執行單元測試：`.\.venv\Scripts\python.exe -m unittest tests/test_domain_models.py`。

---

### 2.6 HTTP/2 串流邊界與結束訊框識別 (Stream Termination Markers)

#### 項目意義與系統作用
Google `StreamGenerate` 介面採用 HTTP/2 雙向串流。Google 伺服器在回答完畢後，**不會主動發送 TCP FIN 訊框關閉連線**，而是發送專門的結束陣列通知客戶端：
- `[["di", null, ...]]`：資料互動結束標記（Data Interaction Finish）
- `[["e", ...]]`：會話結束標記（End Marker）

#### 異動機制與觸發情境
Google 偶爾會更新串流結論訊框的陣列位置（例如從陣列第 0 項移至第 1 項，如 `[["wrb.fr", ...], ["di", null, ...]]`）。
若解析器 `is_end_of_stream` 只檢查 `line[0]`，將會遺漏第 1 項的結束標記，導致客戶端串流迭代器無限掛起等待，直到觸發 120 秒逾時！

#### 檢查與排查步驟
1. 檢視 [gemini_flow/infrastructure/clients/gemini_api/parser.py](../gemini_flow/infrastructure/clients/gemini_api/parser.py) 的 `is_end_of_stream()`。
2. 該方法必須遍歷 `line` 陣列內的所有子項目，一旦發現任何子陣列開頭為 `"di"` 或 `"e"`，立即回傳 `True`。
3. 檢查串流消費迴圈在命中 `is_end_of_stream()` 時是否有顯式 `break` 脫離。

---

### 2.7 99 元素 Protobuf/JSPB 請求體 (`f.req`) 結構

#### 項目意義與系統作用
請求體是以 `f.req=[null, "[99個元素的JSON陣列]"]` 的形式編碼發送。
以下為最常變動的關鍵索引：

| 陣列索引 | 欄位語意 | 格式與範例 | 檢查注意事項 |
| :---: | :--- | :--- | :--- |
| `[0]` | Prompt 區塊 | `[effective_prompt, 0, null, images, null, null, 0]` | 內含提示詞與圖片上傳參考 |
| `[1]` | 語言代碼 | `["zh-TW"]` | 必須與查詢參數 `hl` 一致 |
| `[3]` | Botguard Token | `"!... (2000~3000 字元)"` | 由內嵌 V8 產出之 Attestation Token |
| `[4]` | Botguard Salt | `"32位 hex 隨機鹽值"` | 必須與計算 Token 雜湊時使用的鹽值相同 |
| `[17]` | Turn 索引 | `[[turn_index]]` | 第 0 輪為 `[[0]]`，第 1 輪為 `[[1]]` |
| `[30]` | 客戶端功能特性 | `[4, 16, 19]` | 靜態特性陣列 |
| `[59]` | 請求 UUID | `"<REQ_UUID>"` | 必須與 Header `525005358` 內部的 UUID 完全一致 |
| `[71]` | 會話延續上下文 | `[conv_id, null, null, null, null, null, null, continuation_token]` | 第 0 輪新對話為 `null`；第 1 輪起必須傳入 8 元素陣列 |
| `[79]` | Model ID | `1` / `6` / `8` | 必須與目標模型吻合 |
| `[80]` | Thinking Level | `1` (low) / `4` (medium) / `2` (high) | 思考模式級別 |
| `[96]` | 新會話標記 | `0` (新會話) / `1` (延續會話) | 影響後端對話樹分支判定 |

#### 檢查與排查步驟
1. 檢視 [gemini_flow/infrastructure/clients/gemini_api/protocol/payload_builder.py](../gemini_flow/infrastructure/clients/gemini_api/protocol/payload_builder.py)。
2. 若抓包發現 Google 在 `f.req` 中新增了未知索引或改變了既有結構，需在 `GeminiPayloadBuilder` 定義具名語意常數（`IDX_*`）並更新陣列賦值。

---

### 2.8 傳輸層 TLS 指紋與反爬蟲標頭防護 (Anti-Tarpit & Headers)

#### 項目意義與系統作用
Google GFE 閘道會檢視連線層的 TLS 握手指紋（JA3/JA4）以及 HTTP 標頭。
1. **TLS 指紋**: 標準 Python `aiohttp` 或 `requests` 使用 OpenSSL 預設握手特徵（缺乏 GREASE 擴展、ALPN 缺少 `h2` 優先權），會直接被打入 Tarpit Delay（故意卡住連線 75~170 秒）。專案採用 `curl_cffi` 配合 `impersonate="chrome120"` 解決此問題。
2. **必備防護標頭**:
   - `Origin: https://gemini.google.com`
   - `Referer: https://gemini.google.com/`
   - `x-same-domain: 1`
   - `sec-fetch-dest: empty` / `sec-fetch-mode: cors` / `sec-fetch-site: same-origin`

#### 檢查與排查步驟
1. 檢視 [gemini_flow/infrastructure/clients/http_client.py](../gemini_flow/infrastructure/clients/http_client.py) 中的 `DEFAULT_HTTP_HEADERS`。
2. 確認 `HttpClient` 實例化時是否維持 `impersonate="chrome120"` 或更高版本。

---

## 3. 版本更新標準作業程序 (SOP Checklist)

當遇到 Google 網頁端更新或線上推論異常時，依循以下五步標準程序進行排查：

```
[步驟 1: HAR 封包採集]
       │ 透過 Chrome 開啟 Gemini 並完成一輪完整對話，導出 .har 或 .json 封包
       ▼
[步驟 2: 封包欄位自動比對 (Diffing)]
       │ 比對 f.req 欄位、JSPB Headers (525001261, 525005358) 與 Model ID/Hash
       ▼
[步驟 3: First Handshake 驗證]
       │ 驗證 SNlM0e 與 server_bl 是否能從 HTML 正常解析提取
       ▼
[步驟 4: V8 Botguard 冒煙測試]
       │ 驗證 WAA Challenge 取得與內嵌 V8 能否產出以 "!" 開頭的合法權杖
       ▼
[步驟 5: 端到端 CLI 矩陣測試]
       │ 覆蓋 flash, pro, argon 模型，驗證 TTFT 首字延遲 (3~8 秒內) 與結束訊框識別
```

### 步驟 1: HAR 封包採集
1. 啟動本機 Chrome 瀏覽器，使用登入之帳號訪問 `https://gemini.google.com/app`。
2. 打開 F12 開發者工具 -> 切換至 Network 分頁 -> 勾選 Preserve log。
3. 依序切換 Flash、Pro、Argon 模型，分別輸入一句簡短測試詞（例如「測試」）。
4. 右鍵點擊任一請求 -> 另存為完整 HAR 檔案（存入 `package_ex/` 目錄）。

### 步驟 2: 封包欄位自動比對
執行快速分析腳本，比對最新封包與本機代碼：
```powershell
.\.venv\Scripts\python.exe -c "
import json, glob, urllib.parse

files = sorted(glob.glob('package_ex/*.json'))
if not files: exit('No package found')
latest = files[-1]
print('Analyzing:', latest)

with open(latest, 'r', encoding='utf-8') as f:
    data = json.load(f)

for e in data['log']['entries']:
    url = e['request']['url']
    if 'StreamGenerate' in url:
        for h in e['request']['headers']:
            if '525001261' in h['name']:
                v = json.loads(h['value'])
                print('Found StreamGenerate -> Hash:', v[4], 'ID:', v[14], 'Thinking:', v[15])
                break
"
```
若輸出之 Hash 或 ID 與 [gemini_flow/domain/models.py](../gemini_flow/domain/models.py) 不一致，立即更新領域模型。

### 步驟 3: First Handshake 驗證
確認握手憑證未被前端改版所阻斷：
```powershell
.\.venv\Scripts\python.exe -m unittest tests/test_integration.py
```

### 步驟 4: V8 Botguard 冒煙測試
確認動態 bytecode 與內嵌 V8 樁環境相容：
```powershell
.\.venv\Scripts\python.exe -m unittest tests/test_attestation.py
```

### 步驟 5: 端到端 CLI 矩陣測試
依序執行各模型聊天驗證：
```powershell
# 1. 測試 Flash 模型
.\.venv\Scripts\python.exe cli.py chat "請輸出單詞: OK" -m flash

# 2. 測試 Pro 模型 (驗證 Model ID 6 與 Hash 8c46e95b1a07cecc)
.\.venv\Scripts\python.exe cli.py chat "請用一句話介紹自己" -m pro

# 3. 測試 Argon 模型 (驗證 Thinking Mode 與 Model ID 8)
.\.venv\Scripts\python.exe cli.py chat "1+1等於多少" -m argon
```
所有呼叫必須在 **4 ~ 8 秒內完成串流輸出並正常結束**。

---

## 4. 模組對照與關聯速查表 (Source Code Mapping)

| 系統功能模組 | 主要原始碼檔案 | 主要測試檔案 | 深度技術白皮書 |
| :--- | :--- | :--- | :--- |
| **領域模型與路由** | [models.py](../gemini_flow/domain/models.py)<br>[entities.py](../gemini_flow/domain/entities.py) | [test_domain_models.py](../tests/test_domain_models.py) | [botguard_investigation_and_latency_analysis.md](botguard_investigation_and_latency_analysis.md) |
| **憑證與握手** | [gemini_auth.py](../gemini_flow/infrastructure/auth/gemini_auth.py) | [test_integration.py](../tests/test_integration.py) | [packet_analysis_and_latency_investigation_20261015.md](packet_analysis_and_latency_investigation_20261015.md) |
| **Botguard WAA 客戶端** | [waa_client.py](../gemini_flow/infrastructure/attestation/waa_client.py) | [test_attestation.py](../tests/test_attestation.py) | [botguard_and_payload_attestation_analysis.md](botguard_and_payload_attestation_analysis.md) |
| **內嵌 V8 虛擬機與樁** | [v8_runtime.py](../gemini_flow/infrastructure/attestation/v8_runtime.py)<br>[environment_stubs.py](../gemini_flow/infrastructure/attestation/environment_stubs.py) | [test_attestation.py](../tests/test_attestation.py) | [botguard_and_payload_attestation_analysis.md](botguard_and_payload_attestation_analysis.md) |
| **JSPB 標頭與負載建構** | [payload_builder.py](../gemini_flow/infrastructure/clients/gemini_api/protocol/payload_builder.py)<br>[header_builder.py](../gemini_flow/infrastructure/clients/gemini_api/protocol/header_builder.py)<br>[protocol_engine.py](../gemini_flow/infrastructure/clients/gemini_api/protocol/protocol_engine.py) | [test_protocol_engine.py](../tests/test_protocol_engine.py) | [packet_analysis_and_latency_investigation_20261015.md](packet_analysis_and_latency_investigation_20261015.md) |
| **串流解析與結束識別** | [parser.py](../gemini_flow/infrastructure/clients/gemini_api/parser.py) | [test_integration.py](../tests/test_integration.py) | [botguard_investigation_and_latency_analysis.md](botguard_investigation_and_latency_analysis.md) |
| **傳輸層與 TLS 模擬** | [http_client.py](../gemini_flow/infrastructure/clients/http_client.py) | [fake_http_client.py](../tests/fakes/fake_http_client.py) | [packet_analysis_and_latency_investigation_20261015.md](packet_analysis_and_latency_investigation_20261015.md) |
| **應用層服務協調** | [chat_service.py](../gemini_flow/application/chat_service.py) | [test_integration.py](../tests/test_integration.py) | - |
