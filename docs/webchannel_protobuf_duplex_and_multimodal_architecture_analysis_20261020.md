# Google Gemini 2026-10-20 WebChannel 全雙工 Protobuf 通訊協定與多模態架構深度剖析

文件版本: 2.0.0  
記錄日期: 2026-10-20  
分析依據: `package_ex/10_20_session1.json`、`package_ex/10_20_session2.json`、`package_ex/10_20_session1_image.json`  
適用範圍: GeminiFlow 現代化重構架構、Google WebChannel 通訊協定、二進位 Protobuf 串流傳輸、多模態圖片上傳

---

## 1. 架構演進與重大典範轉移 (Architectural Paradigm Shift)

在 2026 年 10 月中旬前，Google Gemini 網頁端主要仰賴基於 HTTP/2 POST 的單向請求-回應或批次串流機制（`batchexecute` 與 `StreamGenerate`），資料結構大量採用 ASCII 字串陣列格式的 JSPB（JavaScript Protocol Buffers）。

於 2026 年 10 月 20 日捕獲的最新生產環境封包顯示，Google 網頁端架構發生了根本性的典範轉移：

```
+---------------------------------------------------------------------------------+
|                               舊版架構 (Legacy)                                 |
| 端點: https://gemini.google.com/_/BardFrontendUi/data/batchexecute              |
| 協定: 單向 HTTP POST 批次執行，以 JSPB (JSON 巢狀陣列) 為主                       |
| 圖片: Scotty 上傳 -> BardFrontendService/ProcessFile (二階段) -> f.req 綁定    |
+---------------------------------------------------------------------------------+
                                       ▼ 典範轉移 (2026-10-20)
+---------------------------------------------------------------------------------+
|                               新版架構 (Modern WebChannel)                      |
| 端點: https://geminiweb-pa.clients6.google.com/v1/processSession                |
| 協定: Google WebChannel 全雙工長連線通道 (Handshake + Downstream GET + Upstream Pushes) |
| 編碼: 核心資料全量轉為純二進位 Protobuf Wire Format (Base64 封裝傳輸)            |
| 圖片: Scotty Push 上傳 -> 直連 WebChannel Metadata (Tag 1.4) 綁定              |
+---------------------------------------------------------------------------------+
```

### 核心演進對比矩陣

| 維度 | 舊版架構 (Legacy batchexecute) | 2026-10-20 最新 WebChannel 架構 |
| :--- | :--- | :--- |
| **主要通訊端點** | `gemini.google.com/_/BardFrontendUi/data/batchexecute` | `geminiweb-pa.clients6.google.com/v1/processSession` |
| **通訊拓撲** | 單次 Request-Response / 簡易 SSE 長輪詢 | 全雙工雙向虛擬通道（Duplex Virtual Channel） |
| **交握機制** | 無獨立交握，每次帶入 `at_token` (`SNlM0e`) | 顯式握手 `count=0`，動態協商 `gsessionid` 與伺服器 `SID` |
| **資料編碼格式** | JSPB 巢狀字串陣列（如 `[[null, "f.req", ...]]`） | 純二進位 Protobuf Wire Format（Base64 編碼傳輸） |
| **多模態圖片流程** | Scotty 上傳 $\to$ `ProcessFile` 生成縮圖 $\to$ 綁定 | Scotty 上傳取得引用 $\to$ 直接於 `ofs=0` Protobuf Tag 1.4 宣告 |
| **控制信令與分幀** | HTTP/2 Chunked 文字換行分行 | 嚴格長度前綴分幀：`<byte_length>\n<json_payload>\n` |
| **錯誤回報機制** | HTTP 狀態碼或 JSON 陣列結尾標記 | 下游長串流中即時回傳 `__sm__.status` 控制幀 |

---

## 2. WebChannel 雙工通道生命週期 (Duplex Channel Lifecycle)

WebChannel 協定模擬了雙向 WebSocket 的行為，但透過標準 HTTP GET 與 POST 穿透各種中介代理與防火牆。整個對話 Turn 經歷四個嚴謹的狀態推進階段：

```mermaid
sequenceDiagram
    autonumber
    participant C as GeminiFlow Client
    participant G as Google WebChannel Gateway
    participant S as Gemini PaLM/Gemini Core

    Note over C,G: 階段 1: 會話握手 (Handshake)
    C->>G: POST /v1/processSession?VER=8&RID=base_rid&CVER=22<br/>(Body: count=0, $httpHeaders: Tunnel Headers)
    G-->>C: 200 OK: [[0, ["c", "<SID>", "gsessionid_token", ...]]]

    Note over C,G: 階段 2: 建立下游監聽通道 (Downstream Long-Polling)
    C->>G: GET /v1/processSession?RID=rpc&SID=<SID>&gsessionid=<gsessionid>&AID=0&CI=0
    activate G

    Note over C,S: 階段 3: 上游步進式推送 (Upstream Pushes)
    par 並行推送
        C->>G: POST /v1/processSession?ofs=0&count=1 (Metadata: Context, Lang, Model, Images)
        G->>S: 轉發會話元數據與多模態規格
    and 步進延遲 (0.5s Pacing)
        C->>G: POST /v1/processSession?ofs=1&count=1 (Prompt Text Message)
        G->>S: 觸發模型實體推理
    end

    Note over G,C: 階段 4: 下游即時串流接收 (Streaming Ingest)
    S-->>G: 增量 Token 與多模態資源生成
    G-->>C: Length-Prefixed Frame 1: [[seq, [conversation_id]]]
    G-->>C: Length-Prefixed Frame 2: [[seq, [protobuf base64 chunk]]]
    G-->>C: Length-Prefixed Frame N: [[seq, [continuation_token, ["close"]]]]
    deactivate G

    Note over C,G: 階段 5: 完成確認 (ACK)
    C->>G: POST /v1/processSession?ofs=2&count=1&AID=<received_chunks> (Ack Payload)
    G-->>C: 200 OK
```

### 詳細階段規範說明

1. **握手階段（Handshake `count=0`）**：
   - 請求參數包含 `VER=8`、`CVER=22`、`RID=<base_rid>`、`$httpHeaders`。
   - 伺服器回傳 `[[0, ["c", "<SID>", "<gsessionid>", ...]]]`。
   - 客戶端必須提取此 `SID` 作為後續所有 GET/POST 的工作識別碼，並透過 `x-http-session-id` 回傳標頭更新 `gsessionid`。
2. **下游監聽通道（Downstream Stream `RID=rpc`）**：
   - 客戶端發送 GET 請求掛起長連線（Chunked 傳輸）。
   - 伺服器主動透過此長連線推送分幀資料。
3. **上游推送信令（Upstream Pushes）**：
   - `ofs=0`：推送對話元數據（會話 ID、模型規格、語言、思考強度、Botguard Attestation 及多模態圖片中繼資料）。
   - **步進延遲（Pacing Delay）**：客戶端必須在此處加入 0.5 秒防抖延遲，確保伺服器端完成會話容器初始化。
   - `ofs=1`：推送使用者輸入的實際提示詞內容（Prompt）。
4. **通道結束與 ACK（Ack `ofs=2`）**：
   - 當下游接收到 `["close"]` 或包含 continuation token 的結束幀時，客戶端發送 `ofs=2`，並附帶實際收到的幀數 `AID=<received_chunks>`，安全完成本次對話回合。

---

## 3. 二進位 Protobuf Wire 格式結構拆解 (Wire Specification)

在 10/20 新版中，所有請求主體與穿透標頭已從舊版明文 JSON 轉為緊湊的二進位 Protobuf 結構。

### 3.1 穿透擴展標頭 (Tunnel Headers)

透過 URL 的 `$httpHeaders` 傳遞以下格式：
```http
Authorization:SAPISIDHASH <timestamp>_<sha1_hash>\r\n
X-Goog-Api-Key:AIzaSyAPW83vB9zFQqfpMup_cMJdELqDQkWvTho\r\n
x-goog-ext-525001261-bin:<base64_encoded_protobuf>\r\n
x-goog-ext-525005358-bin:<base64_encoded_protobuf>\r\n
X-WebChannel-Content-Type:application/x-protobuf\r\n
```

- **`525001261-bin`（模型路由與環境特徵）**：
  - `Tag 1`: Varint `1`
  - `Tag 5`: String `model_hash`（例如 Flash 3.8 為 `56fdd199312815e2`）
  - `Tag 15`: Varint `model_id`（例如 Flash 為 `1`，Pro 為 `3`，Argon 為 `8`）
  - `Tag 16`: Varint `thinking_level`（Low=`1`, Medium=`4`, High=`2`）
  - `Tag 17`: String `session_uuid`（客戶端生成之 UUID4 大寫字串）
  - `Tag 18`: Message $\to$ `Tag 1`: String `server_bl`（伺服器版本建置號）
- **`525005358-bin`（請求追蹤）**：
  - `Tag 1`: String `req_uuid`（本次請求唯一 UUID）
  - `Tag 2`: Varint `1`

---

### 3.2 `ofs=0` 元數據負載 (Session Metadata Payload)

`ofs=0` 的請求資料放置於 `req0___data__`，為經 Base64 編碼的二進位 Protobuf：

```
Outer Envelope:
  Tag 1 (Routing Header Block)
    Tag 1: 1
    Tag 2: <model_hash>
    Tag 3: <language> (e.g. "zh-TW")
    Tag 4: <req_uuid>
  Tag 2: 0
  Tag 8 (Core Envelope)
    Tag 5:
      Tag 1: <Inner Core 99-Tag Message>
      Tag 4: 1
```

#### `<Inner Core 99-Tag Message>` 核心欄位對照表：

| Protobuf Tag | Wire Type | 欄位意義 | 典型值 / 格式說明 |
| :---: | :---: | :--- | :--- |
| **1** | Length-Delimited | **Prompt Container** | 容器包含文字、旗標與多模態圖片（詳見第 4 節） |
| **2** | Length-Delimited | **語言設定** | 包含 `Tag 1: <language>`（如 `"zh-TW"`） |
| **4** | Length-Delimited | **Botguard Attestation** | 密碼學環境驗證簽名（以 `!` 開頭的 Base64 字串） |
| **5** | Length-Delimited | **Botguard Salt** | 32 位元十六進位 Salt 字串 |
| **7** | Length-Delimited | **靜態協議旗標** | 包含 `Tag 1: 0` |
| **8** | Varint | **協議常數** | `1` |
| **11** | Varint | **協議常數** | `1` |
| **12** | Varint | **協議常數** | `0` |
| **18** | Length-Delimited | **Turn Index** | 巢狀訊息：`Tag 1` $\to$ `Tag 1: turn_index`（0, 1, 2...） |
| **19** | Varint | **協議常數** | `0` |
| **28** | Varint | **協議常數** | `1` |
| **31** | Length-Delimited | **Capabilities** | Packed Varints：`[4, 16, 19]` |
| **42** | Length-Delimited | **協議常數** | 包含 `Tag 1: 1` |
| **50** | Varint | **協議常數** | `0` |
| **54** | Varint | **協議常數** | `0` |
| **60** | Length-Delimited | **Request UUID** | 每次請求獨立之 UUID4 字串 |
| **62** | Length-Delimited | **保留位元組** | 空字串 `b""` |
| **68** | Varint | **協議常數** | `0` |
| **69** | Varint | **協議常數** | `1` |
| **72** | Length-Delimited | **對話上下文延續** | 多輪對話專用：`Tag 1: conversation_id`, `Tag 8: continuation_token` |
| **80** | Varint | **Model ID** | 模型路由整數 ID（Flash=`1`, Pro=`3`, Argon=`8`） |
| **81** | Varint | **Thinking Level** | 思考深度整數（Low=`1`, Medium=`4`, High=`2`） |
| **92** | Varint | **協議常數** | `1` |
| **97** | Varint | **新舊會話標記** | 新對話（Turn 0）為 `0`；延續對話（Turn > 0）為 `1` |
| **99** | Varint | **協議常數** | `1` |

---

### 3.3 `ofs=1` 與 `ofs=2` 負載結構

- **`ofs=1`（Prompt 文字訊息）**：
  ```
  Tag 2:
    Tag 1: Varint 1
    Tag 9:
      Tag 1: String <prompt_text>
  ```
- **`ofs=2`（Finalize / Ack 確認訊息）**：
  ```
  Tag 4:
    Tag 1: Varint 1
  ```

---

## 4. 多模態圖片上傳與 Protobuf 綁定架構 (Multimodal Image Ingestion)

依據 2026 年 10 月 20 日錄製之 `10_20_session1_image.json`，完整逆向還原圖片處理全流程。

### 4.1 Scotty 可續傳上傳協定 (Resumable Upload)

圖片資料不上傳至 Google 網頁前端，而是直傳專門的二進位媒體伺服器 `push.clients6.google.com`：

1. **第一階段：建立上傳會話 (Command: `start`)**
   ```http
   POST /upload/ HTTP/1.1
   Host: push.clients6.google.com
   x-goog-upload-command: start
   x-goog-upload-header-content-length: <image_byte_length>
   x-goog-upload-protocol: resumable
   x-tenant-id: bard-storage
   push-id: feeds/mcudyrk2a4khkz
   Content-Type: application/x-www-form-urlencoded;charset=UTF-8

   File name: <filename.jpg>
   ```
   - 伺服器回傳 `200 OK`，並在 Header 中包含：  
     `x-goog-upload-url: https://push.clients6.google.com/upload/?upload_id=<upload_session_id>`

2. **第二階段：推送二進位資料並完成 (Command: `upload, finalize`)**
   ```http
   POST /upload/?upload_id=<upload_session_id> HTTP/1.1
   Host: push.clients6.google.com
   x-goog-upload-command: upload, finalize
   x-goog-upload-offset: 0
   Content-Type: application/x-www-form-urlencoded;charset=UTF-8

   <raw_binary_image_bytes>
   ```
   - 伺服器回傳 `200 OK`，Response Body 即為儲存引用位址：  
     `/contrib_service/ttl_1d/vq4pqn2irm2f5ltjxft6o5bekbxhwn1792445048`

> [!NOTE]
> **冗餘端點排除**：封包中瀏覽器曾呼叫 `BardFrontendService/ProcessFile`，經逆向證實該端點僅為前端產生縮圖預覽快照，非後端 AI 推理所必需。略過該端點可大幅降低網路延遲並提高整體傳輸穩定度。

---

### 4.2 多模態圖片之 Protobuf Tag 1.4 規格

取得 Scotty 引用位址後，客戶端在 `ofs=0` 元數據的 `Tag 1 (Prompt Container)` 中直接宣告圖片關聯：

```protobuf
message PromptContainer { // Tag 1 of Core Message
    bytes prompt = 1;     // Metadata 階段填入空字元 b""
    int32 flag2 = 2;      // 0
    
    // Tag 4: 可重複陣列 (Repeated for each image)
    repeated ImageAttachment attachments = 4;
    
    int32 flag7 = 7;      // 0
}

message ImageAttachment {
    ImageSpec spec = 1;       // Tag 1: 圖片中繼規格
    string filename = 2;      // Tag 2: 圖片原始檔名 (e.g. "receipt.jpg")
}

message ImageSpec {
    string ref_url = 1;       // Tag 1: Scotty 引用位址 (e.g. "/contrib_service/ttl_1d/...")
    int32 upload_source = 2;  // Tag 2: 常數 1
    string mime_type = 4;     // Tag 4: MIME 類型 (e.g. "image/jpeg", "image/png", "image/webp")
    string attachment_uuid = 5; // Tag 5: 客戶端生成的獨立 UUID4 字串
}
```

---

## 5. 系統實作與反脆弱架構設計 (Anti-Fragile Architecture)

為保證系統長期維護性，實作嚴格依據**「不將就、不相容、不保留過渡代碼、避免過度設計」**原則完成。

### 5.1 零相容墊片政策 (Zero-Shim Policy)
- 徹底刪除歷史遺留的代理類別 `GeminiAPIClient` 與 `StreamParser` 檔案。
- 移除領域層的相容別名 `GeminiTokens`。
- 全域僅保留單一權威客戶端 [`GeminiWebChannelClient`](../gemini_flow/infrastructure/clients/gemini_api/webchannel_client.py)。

### 5.2 位元組級串流分幀器 (Byte-Level Stream Framer)
舊版文字串流分幀在收到網路封包時直接執行 `chunk.decode("utf-8")`，在多位元組字元（繁體中文每字 3 位元組、Emoji 每字 4 位元組）跨越 TCP 分包邊界時，會造成 `\ufffd` 亂碼破壞，且因字元數小於位元組數而導致幀長度比對失效。

最新實作改以 `bytearray` 緩衝區進行位元組級精準切片：
```python
buffer = bytearray()
async for chunk in resp.aiter_content():
    buffer.extend(chunk)
    while buffer:
        match = re.search(rb"^(\d+)\s*\n", buffer)
        if match:
            header_len = match.end()
            frame_len = int(match.group(1).decode("ascii"))
            total_needed = header_len + frame_len
            if len(buffer) < total_needed:
                break
            frame_bytes = bytes(buffer[header_len:total_needed])
            buffer = buffer[total_needed:]
            while buffer and buffer[:1] in (b"\r", b"\n"):
                del buffer[0]
            yield frame_bytes.decode("utf-8", errors="replace")
```

### 5.3 Protobuf 解碼器啟發式邊界防禦
在解析下游 Protobuf 串流時，字串 `"image/png"`（9 位元組）恰好為：
- `ord('i') = 105` $\to$ `Tag 13, Wire Type 1 (Fixed64)`
- 剩餘 8 位元組 `b"mage/png"` 剛好組成 64-bit 整數。

這導致解碼器曾將 `"image/png"` 誤判為具備單一欄位的子訊息。最新版加入字串可印判定：
```python
is_printable_ascii = (length > 0) and all(32 <= b <= 126 for b in chunk)
if recursive and length > 0 and not is_printable_ascii:
    # 進行子訊息嚴格遞迴解碼
```
此邏輯成功保留了字串完整性，同時保證了 Protobuf 子訊息的正確遞迴解析。

### 5.4 控制錯誤即時偵測 (Fast-Fail Control Errors)
在長串流監聽中，Google 會以 `[[1, {"__sm__": {"status": [[{"error": {"code": 401, ...}}]]}}]]` 回報錯誤。實作中的 [`check_control_error`](../gemini_flow/infrastructure/clients/gemini_api/webchannel_parser.py) 能在收到訊框的第一時間拋出 `AuthenticationError` 或 `RateLimitError`，立即中斷連線並觸發憑證自動刷新，不再需要耗損 60~120 秒等待網路逾時。

---

## 6. 模型路由與思考模式對照表 (2026/10/20 最新基準)

| 模型識別標稱 | Thinking 深度 | Model ID | Model Hash | Thinking Level | 備註 |
| :--- | :---: | :---: | :--- | :---: | :--- |
| **`gemini-3.8-flash`** | Low | `1` | `56fdd199312815e2` | `1` | 預設極速文字模型 |
| **`gemini-3.8-flash`** | Medium | `1` | `56fdd199312815e2` | `4` | 平衡深度模型 |
| **`gemini-3.8-flash`** | High | `1` | `56fdd199312815e2` | `2` | 深度分析模型 |
| **`gemini-3-pro`** | Low | `3` | `e6fa609c3fa255c0` | `1` | Pro 專業推理模型 |
| **`gemini-3-pro`** | High | `3` | `e6fa609c3fa255c0` | `2` | Pro 深度推理模型 |
| **`gemini-4-argon`** | Low | `8` | `95a4c0abcba24364` | `1` | 4 Argon 新世代模型 |
| **`gemini-4-argon`** | Medium | `8` | `95a4c0abcba24364` | `4` | 4 Argon 均衡推理 |
| **`gemini-4-argon`** | High | `8` | `95a4c0abcba24364` | `2` | 4 Argon 極限推理 |

---

## 7. 驗證記錄與維護檢核 SOP

### 7.1 單元測試覆蓋
全套測試套件涵蓋 Protobuf Wire 編解碼、標頭構建、多模態圖片注入、多輪狀態轉換、位元組分幀、錯誤訊框攔截以及上行非同步異常即時中斷 (Fail-Fast)：
```bash
.venv\Scripts\python.exe -m unittest discover tests
```
> **執行結果**：`Ran 92 tests in 0.516s - OK`（100% 通過）。

### 7.2 線上端到端驗證成果
1. **單輪文字對話**：
   ```bash
   uv run python cli.py chat "你好，請用繁體中文一句話自我介紹"
   ```
   > 正常輸出即時串流回答。
2. **多模態圖片分析**：
   ```bash
   uv run python cli.py chat --image input/1.jpg "請用一句話簡短描述這張圖片的內容"
   ```
   > 成功上傳 Scotty，正確辨識圖片（例如千代田 7-Eleven 收據內容）。
3. **多輪對話跨進程記憶檢驗**：
   - 第一輪：`uv run python cli.py chat --session-id "sess_live_123" "請記住代號：【極光777】。只需回答「已記住」"` $\to$ 儲存 Conversation ID 與 Continuation Token。
   - 第二輪：`uv run python cli.py chat --session-id "sess_live_123" "我剛剛請你記住的代號是什麼？"` $\to$ 準確回答「你剛剛請我記住的代號是：【極光777】。」。

### 7.3 未來版本異動排查檢核表 (Checklist)
若未來 Google 再次更動協定導致異常，依序檢核：
1. **握手回傳結構檢核**：確認 `processSession` 回傳之 `[[0, ["c", "<SID>", ...]]]` 陣列結構是否更動。
2. **`x-goog-ext-525001261-bin` 標頭解碼**：確認 `Tag 5` (Hash) 與 `Tag 15` (ID) 是否發生雜湊值更動。
3. **`ofs=0` Protobuf Tag 97 狀態**：Turn 0 必須為 `0`，Turn > 0 必須為 `1`，且 `Tag 72` 必須同時存在 `Tag 1` (conv_id) 與 `Tag 8` (continuation_token)。
4. **Scotty 上傳回應格式**：確認 `upload, finalize` 是否依然直接返回 `/contrib_service/ttl_1d/...`。

---

## 8. 非同步並發健壯性、狀態機保護與無狀態設計 (Concurrency & State Machine Hardening)

為確保系統具備長期演進的高擴展性、維護性與正確性，架構進一步實施了以下五大工程硬化措施：

### 8.1 上下行雙工非同步競態監控與即時中斷 (Fail-Fast Duplex Concurrency)
在舊版簡單串流中，若上行任務（`_send_upstream_payloads`，發送 `ofs=0` 與 `ofs=1`）因憑證無效或封包參數錯誤被 Google 立即以 HTTP 400/401 拒絕，Google 伺服器**完全不會對下行 GET 串流發送任何資料**。
若單純在下行 chunk 迭代迴圈內部檢查上行異常，程式將在 `stream_gen.__anext__()` 永久懸掛等待 TCP Socket 資料，直到 30~60 秒逾時。

**現代化解法**：在 [`GeminiWebChannelClient`](../gemini_flow/infrastructure/clients/gemini_api/webchannel_client.py) 中採用非同步競態監控：
```python
stream_iter = stream_gen.__aiter__()
while True:
    if next_chunk_task is None:
        next_chunk_task = asyncio.create_task(stream_iter.__anext__())

    if not push_task.done():
        done, _ = await asyncio.wait(
            [next_chunk_task, push_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        if push_task in done:
            push_exc = push_task.exception()
            if push_exc:
                if not next_chunk_task.done():
                    next_chunk_task.cancel()
                raise push_exc  # 0 延遲即時拋出上行失敗
    else:
        # 上行任務已成功完成，回歸正常下行讀取
        push_exc = push_task.exception()
        if push_exc:
            raise push_exc
        await next_chunk_task
```
此機制達成 100% 事件反應式（Reactive）調度，在上行拋出異常的數毫秒內立刻取消下行監聽並向呼叫方拋出具體異常，徹底杜絕懸掛。

### 8.2 領域實體與協議層狀態機保護 (Session Continuation Invariants)
Google 10/20 協定嚴格要求：**只要 `Tag 97` 宣告為延續對話 (`1`)，`Tag 72` 內必須同時存在 `Tag 1` (Conversation ID) 與 `Tag 8` (Continuation Token)**。缺少任何一項均會引發伺服器拒絕 (HTTP 400)。

1. **領域實體約束**：在 [`SessionData`](../gemini_flow/domain/entities.py) 中明確定義：
   ```python
   @property
   def is_continuation(self) -> bool:
       return bool(self.turn_index > 0 and self.conversation_id and self.continuation_token)
   ```
   若前一輪因網路中斷未取得有效 `continuation_token`，`advance_turn` 拒絕無條件推進輪次，避免 Session 進入損壞狀態。
2. **協議構建保護**：在 [`WebChannelPayloadBuilder`](../gemini_flow/infrastructure/clients/gemini_api/protocol/payload_builder.py) 中：
   ```python
   is_continuation = bool(self.turn_index > 0 and self.conversation_id and self.continuation_token)
   if is_continuation:
       tag72_conv = (
           ProtobufBuilder()
           .add_string(1, self.conversation_id)
           .add_string(8, self.continuation_token)
       )
       inner.add_message(72, tag72_conv)

   inner.add_varint(97, 1 if is_continuation else 0)
   ```
   唯有具備完整延續資訊時才輸出 `Tag 72` 與 `Tag 97=1`；若 token 缺失則平滑降級為新對話封包，百分之百保證構建之 Protobuf 結構合規。

### 8.3 協議規劃引擎純無狀態化 (Stateless Protocol Engine)
舊版 `WebChannelProtocolEngine` 曾在實例初始化時生成並綁定固定之 `self.session_uuid`。在長期運行的服務實例中，跨請求復用引擎會導致所有使用者會話共享同一 UUID。
重構後將 `session_uuid` 的生命週期完全限制在 `plan_turn` 調用範圍內（由 `session_data.session_id` 注入或按需單次生成），使 `WebChannelProtocolEngine` 成為純粹的**無狀態規劃器 (Stateless Planner)**，保證線程與非同步安全。

### 8.4 位元組緩衝區就地操作 (In-place Byte Buffering)
在 [`CurlHttpClient.get_stream`](../gemini_flow/infrastructure/clients/http_client.py) 中：
1. 每一輪長度解碼前先行清除開頭殘留之 `\r`, `\n`, `\t` 與空白字元，防止 TCP 邊界切片干擾 `^(\d+)\s*\n` 正則解析。
2. 使用 `del buffer[:total_needed]` 取代 `buffer = buffer[total_needed:]`，在 CPython `bytearray` 內部直接進行原地記憶體位移操作，避免長串流高頻重新分配與垃圾回收開銷。

### 8.5 廢棄接口與過渡別名完全消除
- 自 [`IHttpClient`](../gemini_flow/domain/interfaces.py)、[`CurlHttpClient`](../gemini_flow/infrastructure/clients/http_client.py) 與 [`FakeHttpClient`](../tests/fakes/fake_http_client.py) 徹底刪除已無任何用途的歷史單向 `post_stream` 接口。
- 自 [`webchannel_client.py`](../gemini_flow/infrastructure/clients/gemini_api/webchannel_client.py) 刪除過渡別名 `WebChannelChatProvider`，全面統一名稱為 `GeminiWebChannelClient`。
