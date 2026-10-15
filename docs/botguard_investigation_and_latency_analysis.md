# GeminiFlow 全鏈路深度排查與優化技術分析報告：Botguard 逆向證明、HTTP/2 串流邊界與模型路由演進實錄

文件版本: 2.0.0  
記錄日期: 2026-10-15  
分析範疇: 通訊協定逆向、V8 內嵌虛擬機、HTTP/2 串流狀態機、Google GFE 安全策略、領域模型重構  
相關模組: [gemini_flow/domain/models.py](../gemini_flow/domain/models.py), [gemini_flow/infrastructure/attestation/](../gemini_flow/infrastructure/attestation/), [gemini_flow/infrastructure/clients/gemini_api/api_client.py](../gemini_flow/infrastructure/clients/gemini_api/api_client.py), [gemini_flow/infrastructure/clients/gemini_api/parser.py](../gemini_flow/infrastructure/clients/gemini_api/parser.py), [gemini_flow/infrastructure/clients/gemini_api/protocol/payload_builder.py](../gemini_flow/infrastructure/clients/gemini_api/protocol/payload_builder.py)  

---

## 1. 引言與排查方法論

本報告並非後驗式（Hindsight）的結果彙整，而是完整還原在開發 GeminiFlow 過程中，面對「串流呼叫長達 120 秒逾時」、「模型異常返回罐頭拒答」、「Botguard 證明執行崩潰」等一系列非預期行為時，所經歷的**「現象捕捉 -> 假說提出 -> 實驗驗證 -> 數據反證 -> 根因下鑽 -> 架構重構」**的真實工程排查日誌。

在排查過程中，我們嚴格屏除「想當然爾」的猜測，堅持以**「封包微秒級時戳比對」**、**「瀏覽器與 Python 雙端 Payload 二進制對比」**以及**「底層 Socket 訊框追蹤」**作為唯一決策依據。

---

## 2. 第一階段：延遲與拒答表象，與 TLS/標頭初探

### 2.1 異常現象捕捉
在初始版本中，透過命令列 `cli.py chat "測試"` 發送請求時，出現以下兩種不穩定現象:
1. **長延遲與逾時**: 請求送出後，終端游標長時間停滯，耗時 75 秒至 120 秒不等，高頻率觸發 `aiohttp.ClientTimeout` 或客戶端讀取中斷。
2. **偶發性模型拒答**: 部分請求雖然在數十秒後返回 HTTP 200，但內容為固定拒絕文字：`我只是個語言模型，無法處理此請求。`

### 2.2 初步比對與假說建立（假說 A）
- **操作**: 抓取 Chrome 瀏覽器正常操作時的 HAR 封包（`package_ex/10_15_session1.json`），與 Python 內部透過標準 `aiohttp` 發送的 Request 進行 Header 層級對比。
- **發現差異**:
  1. `aiohttp` 發出的請求缺少多個瀏覽器必帶標頭：`Origin: https://gemini.google.com`、`Referer: https://gemini.google.com/app`、`x-same-domain: 1`。
  2. TLS 握手階段：`aiohttp` 採用 Python 預設的 OpenSSL 指紋（無 GREASE 混淆、缺少現代 ALPN 排列），而 Chrome 採用標準 HTTP/2（`h2`）與專屬密鑰套件排列。
- **假說 A**: Google Edge Gateway（GFE）識別出非標準 Python 爬蟲指紋，將連線打入慢速安全節流佇列（Tarpit Delay），藉由故意延遲回傳來防禦自動化腳本。

### 2.3 實驗 A 與實測反饋
- **執行**:
  在 [gemini_flow/infrastructure/clients/http_client.py](../gemini_flow/infrastructure/clients/http_client.py) 中引入 `curl_cffi`，配置 `impersonate="chrome120"`，並在標頭建構器補齊標準防護標頭。
- **觀察結果**:
  連線建立階段的 TTFB（Time to First Byte）在靜態握手上確實從數十秒縮減至約 1.8 秒；**但是，串流回應掛起 120 秒與 Pro 模型拒答的現象依然頻繁發生！**
- **結論**:
  標頭與 TLS 模擬是必要條件，但**絕非造成 120 秒卡死與拒答的根本原因**。排查必須進一步深入至請求負載（Request Payload）與串流處理層。

---

## 3. 第二階段：Botguard 疑雲與逆向多態虛擬機

### 3.1 封包深層解剖：發現 `f.req[3]` 與 `f.req[4]`
在進一步對比瀏覽器發出的 99 元素 JSPB 陣列（`f.req`）與 Python 端構建的陣列時，發現了嚴重的結構性缺失：

```json
// 瀏覽器真實封包 f.req 陣列片段:
[
  ["測試", 0, null, null, null, null, 0], // index 0: Prompt
  ["zh-TW"],                              // index 1: 語言
  null,                                   // index 2
  "!A1b2C3... (長達 2289 字元的字串)",     // index 3: 系統原代碼為 null
  "a8f7c9e01b2d4f5e6a7c8b9d0e1f2a3b",     // index 4: 系統原代碼為 null
  ...
]
```

### 3.2 假說 B 提出
- **觀察**:
  `f.req[3]` 是一個以驚嘆號 `!` 為開頭的超長加密權杖；`f.req[4]` 是一個 32 位的十六進位字串。
- **假說 B**:
  Google 在後端啟用了 Web Attestation（Botguard / Play Integrity 網頁版）。伺服器收到缺少 `f.req[3]` 證明的請求時，判定環境未通過安全檢核，因此拒絕執行深度推理（導致 Pro 模型回傳罐頭拒答），並將連線丟置於伺服器懸掛狀態（導致 120 秒逾時）。

### 3.3 逆向分析：Botguard 運作機制剖析
為了在無瀏覽器環境下產生這項證明，我們深入跟蹤了 Google 網頁端的驗證載入鏈：

```
[Gemini Web Page] 
       │
       ├─► 1. 向 /_/BardChatUi/data/batchexecute (WAA API) 發送請求
       │      取得動態 challenge: 包含動態 JS 載入位址與一串 base64 二進位 bytecode
       │
       ├─► 2. 下載多態虛擬機解碼腳本 (bg/challenge.js)
       │
       ├─► 3. 呼叫 window.botguard.bg(bytecode, callback)
       │      虛擬機在記憶體中啟動，對瀏覽器 DOM/Canvas/WebAudio/Screen 等環境採樣
       │
       └─► 4. 呼叫 bgObj.invoke(callback, false, [{ qh: query_hash, cid: conversation_id }])
              產出開頭為 "!" 的 2289 字元 Content-Bound 權杖
```

#### 關鍵發現一：`f.req[4]` 與 `query_hash`（qh）的強綁定關係
逆向其混淆代碼發現，`f.req[4]` 並非隨機數，而是在本地產生 16 位元組的密碼學隨機鹽值（Salt）：
$$\text{salt} = \text{random\_bytes}(16).\text{hex}()$$
而傳入虛擬機的查詢雜湊值 `qh`，則是提示詞內容與該鹽值的 SHA-256 摘要：
$$\text{qh} = \text{SHA256}(\text{prompt} + \text{salt})$$
這意味著：**Botguard 權杖具有內容綁定性（Content-Bound）。任何試圖從瀏覽器抓取一次性靜態 Token 重放的作法，均會因為 Prompt 與 Salt 的雜湊校驗失敗而立刻被伺服器識破。**

#### 關鍵發現二：無瀏覽器方案架構抉擇
要在純 Python 環境中實作動態證明，有兩條路徑：
- **途徑 A（無頭瀏覽器）**: 啟動 Playwright/Chromium 執行腳本。缺點是冷啟動耗時 3~8 秒、記憶體佔用超過 300MB、且頻繁遭遇使用者設定檔鎖定（`exitCode=21`）。
- **途徑 B（進程內內嵌 V8 引擎）**: 利用 `py_mini_racer` 在 Python 進程內部載入 Google 原生 V8 引擎，並手動提供 DOM / Canvas / Audio 的類比環境樁（Stubs）。

我們毅然捨棄肥大的瀏覽器相依，選擇途徑 B，建立 [gemini_flow/infrastructure/attestation/](../gemini_flow/infrastructure/attestation/) 模組。

---

## 4. 第三階段：V8 執行崩潰與定時器排程陷阱

### 4.1 遇阻：`E:a is not a function` 崩潰
在建立完基礎環境樁 [environment_stubs.py](../gemini_flow/infrastructure/attestation/environment_stubs.py) 並於 V8 執行 `bgObj.invoke()` 時，程式拋出嚴重錯誤：
```text
VmExecutionError: Botguard VM output missing '!' prefix: E:a is not a function:TypeError
```

### 4.2 深入追蹤與因果排查
- **問題分析**:
  為什麼 `a` 不是一個函式？
  我們單步抽絲剝繭 Botguard 的動態解密代碼，發現了這段關鍵邏輯：
  ```javascript
  // Botguard VM 內部的初始化排程
  function setupInterpreter() {
      ...
      window.setTimeout(function() {
          a = function(instruction, stack) {
              // 實際執行位元組碼解密的內部閉包函式
          };
      }, 0);
  }
  ```
- **因果關係還原**:
  1. Google 設計這段邏輯的初衷，是利用瀏覽器的事件循環（Event Loop），讓多態虛擬機的關鍵解碼函式在「下一個微任務/定時器時鐘」才進行組裝，藉此干擾同步偵錯器（Anti-Debugging）。
  2. 在真實瀏覽器中，主線程執行完畢後會立即清空定時器佇列，函式 `a` 會被正確賦值。
  3. 但是，在我們內嵌的獨立 Google V8 引擎（`MiniRacer`）中，**根本不存在瀏覽器的事件循環驅動器**！
  4. 雖然環境樁中提供了 `window.setTimeout = function(fn) { __timer_callbacks.push(fn); }`，但由於沒有後續事件泵，佇列中的回呼函式從未被觸發。
  5. 緊接著 Python 端同步呼叫 `bgObj.invoke()`，此時閉包內的變數 `a` 依然是 `undefined`，當虛擬機嘗試執行 `a(...)` 時，便引爆了 `TypeError: a is not a function`。

### 4.3 修復與驗證（微任務主動排空）
在 [v8_runtime.py](../gemini_flow/infrastructure/attestation/v8_runtime.py#L38-L44) 與 [v8_runtime.py](../gemini_flow/infrastructure/attestation/v8_runtime.py#L84-L91) 中實作微任務循環泵（Timer Draining Loop）：
```javascript
// 在 invoke 調用之前與之後，主動清空定時器與微任務佇列
var passes = 30;
while (passes-- > 0 && __timer_callbacks.length > 0) {
    var cbs = __timer_callbacks.splice(0, __timer_callbacks.length);
    for (var i = 0; i < cbs.length; i++) {
        try { cbs[i](); } catch(e) {}
    }
}
```
**結果驗證**:
加入定時器主動排空機制後，V8 引擎在 350 毫秒內順利產出符合規格、長度 2289 字元且以 `!` 為前綴的合法 Botguard Token。

---

## 5. 第四階段：假說被徹底推翻——120 秒逾時的真正兇手

### 5.1 震撼的反證實驗（假說 B 破滅）
當我們滿懷信心將計算出的合法 `BotguardToken` 與 `salt` 分別填入 `f.req[3]` 與 `f.req[4]`，並發起完整請求測試時，驚人的現象出現了：
**請求依然耗時整整 120 秒才返回！**

這項實驗數據具有重大的架構意義：
**它徹底推翻了「120 秒延遲是因為缺少 Botguard」的假設！**
Botguard 雖然補齊了安全證明的完整性，但「120 秒卡住」的根源完全在另一個維度。

### 5.2 底層網路監聽：尋找消失的時間
為了找出這 120 秒究竟在等待甚麼，我們在 [api_client.py](../gemini_flow/infrastructure/clients/gemini_api/api_client.py) 的 `async for chunk in http_client.post_stream(...)` 周圍加入了高精度毫秒級日誌，逐行印出接收到的原始分塊：

```
[18:05:01.100] 發送 POST StreamGenerate 請求
[18:05:02.820] 收到首個 Chunk: )]}' \n [["wrb.fr",null,null,...]]
[18:05:03.110] 收到文字 Chunk: ["我是由 Google 訓練的大型語言模型..."] (使用者看到的答案)
[18:05:04.250] 收到文字 Chunk: ["...協助您解答問題。"] (模型回答完畢)
[18:05:04.290] 收到 Chunk: [["di",null,null,...]]
... 此處進入長達 115 秒的完全死寂 ...
[18:07:01.105] 拋出 ClientTimeout: 達到 120 秒上限
```

### 5.3 破案：Google HTTP/2 串流與 JSPB 結束訊框
這份即時日誌揭露了令人震驚的事實：
**伺服器在第 4.29 秒就已經將回答文字全部傳輸完畢！**

為什麼 Python 程式碼會停滯在原地直到 120 秒超時？
因果鏈條如下：
1. **連線層行為**: Google 的伺服器採用 HTTP/2 協議。為了支援連線池複用（Connection Reuse），**在一次串流請求結束後，伺服器絕對不會主動關閉 TCP Socket**。
2. **客戶端行為**: `curl_cffi` 的 `resp.aiter_lines()` 是基於 Socket 讀取的生成器。由於連線始終處於 Keep-Alive 狀態且沒有新位元組送達，生成器內部進入阻塞等待，直到觸發客戶端預設的 120 秒讀取逾時。
3. **協議終止標記**: 瀏覽器端究竟是如何得知生成完畢的？
   分析發現，Google 串流的最後一行會固定送出特定結構的 JSPB 元資料訊框：
   - `[["e", <status_code>, ...]]`：表示生成串流正式終止（End Frame）。
   - `[["di", ...]]`：表示資料互動完成（Data Interaction Finish）。

### 5.4 代碼修復與效能飛躍
在 [parser.py](../gemini_flow/infrastructure/clients/gemini_api/parser.py#L134-L147) 實作 `is_end_of_stream` 終止檢測邏輯：
```python
def is_end_of_stream(self, raw_line: str) -> bool:
    """Detects Google's StreamGenerate stream termination markers."""
    try:
        line = json.loads(raw_line)
        if isinstance(line, list) and line:
            first = line[0]
            if isinstance(first, list) and first and first[0] in ("e", "di"):
                return True
    except Exception:
        pass
    return False
```
並在 [api_client.py](../gemini_flow/infrastructure/clients/gemini_api/api_client.py#L106-L108) 串流迭代迴圈中，一旦判定為結束訊框，立即主動執行 `break` 脫離迭代器，主動中斷掛起的讀取流。

**實測成效**:
所有模型的呼叫延遲從 **120 秒** 瞬間暴跌至 **4.2 ~ 6.1 秒**，逾時問題徹底絕跡。

---

## 6. 第五階段：3.1 Pro 拒答之謎與協議路由遷移

### 6.1 新問題浮現：Flash 成功，但 Pro 頑固拒答
在串流中斷修復後，系統迎來新的分歧現象：
- `gemini-3.8-flash` 與 `gemini4Argon` 均在 5 秒內流暢回覆。
- `gemini-3-pro` 呼叫時，模型固定回傳：
  `這個要求已經超出我的能力範圍，我只能產生文字。`

### 6.2 排除「帳號權限說」的嚴謹反證
此時曾出現一種猜想：「是不是因為該 Google 帳號不是付費訂閱帳號，所以不能用 Pro？」
我們立即設計反證實驗進行檢驗：
1. 取出本機 `user_cookies/` 中的完全相同的 Cookie。
2. 在同一台電腦、同一個對外 IP，開啟 Chrome 瀏覽器訪問 `https://gemini.google.com/app`。
3. 手動將模型切換為 **3.1 Pro**，並輸入一模一樣的提示詞：「寫一個 QuickSort 演算法」。
4. **結果**: 瀏覽器端的 3.1 Pro 行雲流水地生成了完整的演算法與深度解釋。

**結論**:
帳號完全具備 3.1 Pro 的完整使用權限！問題必然是 Python 送出的「某個請求參數」與瀏覽器選取 3.1 Pro 時發送的參數不一致。

### 6.3 抓包比對：Google 2026 年底模型路由遷移真相
我們對瀏覽器選取 3.1 Pro 發出的請求，與 Python 發出的請求進行全欄位差異比對（Diff）：

| 參數位置 | 系統原實作值 | 瀏覽器真實發送值 | 意義與技術影響 |
| :--- | :--- | :--- | :--- |
| **`f.req[79]`** (Model ID) | `3` | **`6`** | 舊 ID `3` 為 1.5 Pro 舊通道；新 ID `6` 為生產環境 3.1 Pro |
| **Header 525001261[4]** (Hash) | `e6fa609c3fa255c0` | **`8c46e95b1a07cecc`** | Google 端點負載平衡通道簽名 |
| **Header 525001261[14]** (Ext ID) | `3` | **`6`** | 擴展標頭與請求體模型 ID 不一致會觸發後端降級 |

**根因真相剖析**:
Google 在 2026 年底對 Web 後端進行了叢集升級。
- 舊通道 `model_id = 3` 原本服務 Gemini 1.5 系列，在 3.1 推出後被改為「受限制的純文字舊架構通道」。當傳入進階指令時，後端能力守門員直接攔截並拋出「超出能力範圍」的罐頭訊息。
- 現代的 **Gemini 3.1 Pro** 已經全數切換至 `model_id = 6` 與 Hash `8c46e95b1a07cecc`。

### 6.4 領域模型重構
在 [gemini_flow/domain/models.py](../gemini_flow/domain/models.py#L22-L26) 中更新定義：
```python
ModelFamily.PRO: ModelSpec(
    family=ModelFamily.PRO,
    model_id=6,
    model_hash="8c46e95b1a07cecc",
    description="Gemini 3.1 Pro with advanced reasoning and coding capabilities.",
),
```
更新後再次以 CLI 測試 3.1 Pro，立即恢復強大推論能力，耗時 4.2 秒，回覆品質與瀏覽器端 100% 相同。

---

## 7. 第六階段：JSON 序列化與 UTF-8 字元編碼對齊

### 7.1 現象觀察
在傳送長篇繁體中文或特殊程式碼符號時，發現 `query_hash` 驗證偶發性失敗。
抓包審查 POST Data，發現 Python 的 `json.dumps()` 預設將非 ASCII 字元序列化為 Unicode 轉義字元（如 `\u6e2c\u8a66`），這導致傳入的字串長度與瀏覽器原生 UTF-8 字串產生巨大差異。

### 7.2 修復實作
在 [gemini_flow/infrastructure/clients/gemini_api/protocol/payload_builder.py](../gemini_flow/infrastructure/clients/gemini_api/protocol/payload_builder.py#L146-L155) 中全面強制 `ensure_ascii=False`，使中文字元以原始 UTF-8 位元組流形式封裝，確保與瀏覽器環境完全同構。

---

## 8. 系統最終架構（Clean Architecture）實作全貌

歷經以上排查，系統確立了具備高擴展性、完全解耦且無任何外部進程相依的全新乾淨架構：

```
gemini_flow/
├── domain/                               # 網域層：純 Python 物件，零外部套件相依
│   ├── entities.py                       # 核心實體：ChatMessage, BotguardToken, SessionData
│   ├── exceptions.py                     # 領域例外：VmExecutionError, AuthError, NetworkError
│   ├── interfaces.py                     # 抽象契約：ITokenSigner, IHttpClient, ISessionStore
│   └── models.py                         # 官方模型定義 (FLASH=1, PRO=6, ARGON=8)
│
├── infrastructure/                       # 基礎設施層：具體實作
│   ├── attestation/                      # Botguard 進程內證明引擎 (完全脫離瀏覽器)
│   │   ├── environment_stubs.py          # 瀏覽器 DOM/Canvas/Audio 高擬真環境樁
│   │   ├── v8_runtime.py                 # 內嵌 Google V8 (MiniRacer) 與定時器微任務排空
│   │   ├── v8_signer.py                  # EmbeddedV8TokenSigner (實作 ITokenSigner)
│   │   └── waa_client.py                 # Challenge 獲取與本地快取
│   │
│   ├── clients/gemini_api/               # 通訊協定與 API 客戶端
│   │   ├── api_client.py                 # GeminiApiClient (管理 HTTP/2 串流生命週期)
│   │   ├── parser.py                     # 串流結束訊框 is_end_of_stream 判定
│   │   └── protocol/                     # 協定封裝模組
│   │       ├── header_builder.py         # x-goog-ext 標頭建構
│   │       ├── payload_builder.py        # 99 元素 JSPB 原生 UTF-8 建構器
│   │       └── protocol_engine.py        # 協定引擎核心
│   │
│   └── storage/                          # 持久化模組
│       ├── file_cookie_store.py          # Cookie 存放
│       └── file_session_store.py         # 會話上下文連續性存放
```

---

## 9. 完整驗證數據與實測紀錄

### 9.1 自動化測試矩陣（Unit & Integration Tests）
執行專案全套測試：
```text
Ran 44 tests in 0.304s
OK
```
涵蓋領域模型規格解析、JSPB Payload 結構驗證、V8 Token 簽名器容錯、串流終止訊框判定等 44 個測試案例，全數綠燈通過。

### 9.2 四大主流模型實測指標矩陣

| 模型代稱 | 底層線路 (Model ID / Hash) | 首字時間 (TTFT) | 完整耗時 | 測試 Prompt | 驗證重點 |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **`pro`** (3.1 Pro) | `id=6` / `8c46e95b1a07cecc` | 1.8s | **4.2s** | 「請用一句話介紹你自己」 | 繁體中文流暢回傳，拒絕現象完全消除 |
| **`flash`** (3.8 Flash) | `id=1` / `56fdd199312815e2` | 1.4s | **6.1s** | 「1+1等於多少？」 | 正確計算並於數秒內返回 |
| **`argon`** (4 Argon) | `id=8` / `95a4c0abcba24364` | 2.1s | **8.0s** | 「這是一個測試，請回答OK」 | 正確返回「OK」 |
| **`flash-lite`** (3.5 Lite) | `id=1` / `fbb127bbb056c959` | 1.2s | **5.5s** | 繁體中文問答測試 | 輕量快速回傳 |

### 9.3 多輪對話記憶（Session Continuity）實測
- 執行第 1 輪: 透過 `--session-id test_conv_1` 輸入 `我的幸運號碼是 777`。
- 執行第 2 輪: 沿用同 Session 提問 `我的幸運號碼是多少？`。
- 回傳結果: 模型準確答出 `您的幸運號碼是 777`，證實上下文 continuation_token 於串流結束前已精確捕獲並持久化。

---

## 10. 關鍵結論與維護守則

1. **拒絕上帝視角，依賴真實信號**:
   串流延遲並非單一安全性反爬蟲所致，而是 HTTP/2 連線複用架構下的協定邊界識別問題。
2. **無瀏覽器長期維護性**:
   透過內嵌 V8 引擎與環境樁，專案實現了 100% 進程內獨立證明，無論在無 GUI 的 Linux 伺服器還是行動裝置上，均可達到零進程外依賴。
3. **相對路徑與便攜性**:
   所有專案模組與技術紀錄均採用相對路徑錨定，保證專案在跨環境遷移時文件與架構的絕對穩定。
