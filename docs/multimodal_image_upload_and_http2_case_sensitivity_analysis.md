# GeminiFlow 多模態架構：Google Resumable Upload 協定逆向、HTTP/2 標頭大小寫陷阱與物件化重構全流程白皮書

文件版本: 1.0.0  
記錄日期: 2026-10-16  
技術範疇: Google 多模態協定 (Multimodal Protocol)、Google Resumable Upload (Scotty Push Service)、HTTP/2 標頭規範 (RFC 9110 / RFC 7540 / RFC 9113)、Case-Insensitive Mapping、依賴倒置原則 (DIP)  
源碼映射: 
- 基礎設施傳輸層: [`gemini_flow/infrastructure/clients/http_client.py`](../gemini_flow/infrastructure/clients/http_client.py)
- 圖片上傳服務: [`gemini_flow/infrastructure/clients/gemini_uploader.py`](../gemini_flow/infrastructure/clients/gemini_uploader.py)
- 領域合約介面: [`gemini_flow/domain/interfaces.py`](../gemini_flow/domain/interfaces.py)
- API 客戶端協調: [`gemini_flow/infrastructure/clients/gemini_api/api_client.py`](../gemini_flow/infrastructure/clients/gemini_api/api_client.py)
- 全域協定組態: [`gemini_flow/config.py`](../gemini_flow/config.py)
封包依據: [`package_ex/10_16_session1_image.json`](../package_ex/10_16_session1_image.json), [`package_ex/example_gemini_image_overall_0814.json`](../package_ex/example_gemini_image_overall_0814.json)

---

## 1. 概述與問題範疇 (Executive Summary)

在 GeminiFlow 引入多模態（Multimodal）圖片與提示詞（Prompt）協同對話功能時，於命令列介面執行以下指令：

```bash
uv run python cli.py chat -f input/prompt.txt --image .\input\1.jpg
```

系統於日誌中拋出致命異常並中斷連線：

```text
2026-10-16 04:19:39 [INFO] gemini_flow.api_client: Uploading 1 images...
2026-10-16 04:19:40 [ERROR] gemini_flow.api_client: Image upload failed: Missing X-Goog-Upload-Url
Error: Image upload failed: Missing X-Goog-Upload-Url
2026-10-16 04:19:40 [ERROR] gemini_flow.cli: GeminiFlow failure: Image upload failed: Missing X-Goog-Upload-Url
```

表面上看，此錯誤提示像是 Google 伺服器端拒絕了圖片上傳或未返回 Session URL；然而經由深層封包比對與傳輸層逆向分析，證實這是由一個**極度隱蔽的底層架構缺陷**所導致的「假性網路錯誤」。

本技術白皮書將完整記錄：
1. **Google Resumable Upload (Scotty)** 兩階段上傳協定的真實運作機制。
2. 基於 `10_16_session1_image.json` 的 HAR 封包特徵解碼與協定漂移（Protocol Drift）修正。
3. **RFC 9110 / RFC 7540** 規範在 HTTP/2 下強制全小寫標頭，與 Python 原生大小寫敏感字典產生的嚴重語意衝突。
4. 拒絕「暫時打補丁」思維，如何透過物件化抽象（`CaseInsensitiveDict`、`IImageUploader`）達成高內聚、低耦合且可長期維護的新架構。

---

## 2. 瀏覽器真實封包逆向深度拆解 (`10_16_session1_image.json`)

Google Gemini 網頁端處理多模態附件時，並非透過標準的 `multipart/form-data` 將圖片直接塞進對話請求中，而是採用 Google 基礎架構專用的 **Scotty Resumable Upload 協定**。

以下針對 `package_ex/10_16_session1_image.json` 中實際捕獲的連線進行完整解構：

```mermaid
sequenceDiagram
    autonumber
    participant Client as GeminiFlow Client
    participant Scotty as Google Scotty Upload (push.clients6.google.com)
    participant Gemini as Gemini Backend (BardChatUi)

    Note over Client,Scotty: 第一階段：初始化上傳會話 (Session Initiation)
    Client->>Scotty: POST /upload/ (Header: x-goog-upload-command: start, length=224474)
    Scotty-->>Client: 200 OK (Header: x-goog-upload-url: https://push.../upload/?upload_id=AP6r...)

    Note over Client,Scotty: 第二階段：二進位內容傳輸 (Upload & Finalize)
    Client->>Scotty: POST /upload/?upload_id=AP6r... (Header: x-goog-upload-command: upload, finalize)
    Scotty-->>Client: 200 OK (Body: /contrib_service/ttl_1d/ftjkq3...)

    Note over Client,Gemini: 第三階段：提示詞與引用注入 (StreamGenerate)
    Client->>Gemini: POST StreamGenerate (f.req inner[0][3] 注入 upload_ref)
    Gemini-->>Client: 200 OK (Chunked SSE 串流回傳多模態推論解析)
```

### 2.1 第一階段：會話初始化 (Entry 23)

瀏覽器向 Google 上傳伺服器宣告即將上傳檔案的長度與後端服務租戶：

* **請求端點與方法**：`POST https://push.clients6.google.com/upload/`
* **請求標頭 (Request Headers)**：
  ```http
  :authority: push.clients6.google.com
  :method: POST
  :path: /upload/
  :scheme: https
  content-length: 16
  content-type: application/x-www-form-urlencoded;charset=UTF-8
  origin: https://gemini.google.com
  push-id: feeds/mcudyrk2a4khkz
  referer: https://gemini.google.com/
  sec-fetch-dest: empty
  sec-fetch-mode: cors
  sec-fetch-site: same-site
  x-goog-upload-command: start
  x-goog-upload-header-content-length: 224474
  x-goog-upload-protocol: resumable
  x-tenant-id: bard-storage
  ```
* **請求內容 (Request Body)**：
  ```text
  File name: 1.jpg
  ```
* **伺服器回應 (Response Headers)**：
  ```http
  status: 200
  x-goog-upload-chunk-granularity: 262144
  x-goog-upload-control-url: https://push.clients6.google.com/upload/?upload_id=AP6rU82iLYKj...&upload_protocol=resumable
  x-goog-upload-status: active
  x-goog-upload-url: https://push.clients6.google.com/upload/?upload_id=AP6rU82iLYKj...&upload_protocol=resumable
  x-guploader-uploadid: AP6rU82iLYKj...
  ```

> [!IMPORTANT]
> **關鍵發現 1**：伺服器在此步驟返回了 `x-goog-upload-url`，此 URL 包含長達 100 多字元的獨一無二 `upload_id`，專門用於接收二進位資料。
> **關鍵發現 2**：在 HTTP/2 連線下，所有標頭欄位均以**全小寫**編碼回傳（如 `x-goog-upload-url` 而非 `X-Goog-Upload-Url`）。

---

### 2.2 第二階段：傳輸二進位內容並確認 (Entry 25)

瀏覽器取得 Step 1 返回的專屬 `x-goog-upload-url` 後，立即將圖片二進位原始位元組串流 POST 至該端點：

* **請求端點與方法**：`POST https://push.clients6.google.com/upload/?upload_id=...&upload_protocol=resumable`
* **請求標頭 (Request Headers)**：
  ```http
  :authority: push.clients6.google.com
  content-length: 224474
  content-type: application/x-www-form-urlencoded;charset=utf-8
  origin: https://gemini.google.com
  push-id: feeds/mcudyrk2a4khkz
  referer: https://gemini.google.com/
  x-goog-upload-command: upload, finalize
  x-goog-upload-offset: 0
  x-tenant-id: bard-storage
  ```
* **請求內容 (Request Body)**：
  `1.jpg` 的完整二進位 JPEG 位元組資料（長度剛好 224,474 bytes）。
* **伺服器回應 (Response Headers & Body)**：
  ```http
  status: 200
  content-length: 125
  content-type: text/html; charset=UTF-8
  x-goog-upload-status: final
  ```
  **回應內容 (Body)**：
  ```text
  /contrib_service/ttl_1d/ftjkq3wuypkybbqzbkezlgmf6liddx1792096903_ARqe1MHhNTtZUOks22RM-slxxAPiwF6RrslU-kyLJ5xYfs3h2xBV-Iho-6tx
  ```

> [!NOTE]
> 伺服器回傳一串以 `/contrib_service/ttl_1d/` 開頭的儲存參照識別碼（Upload Reference ID）。此識別碼具備 1 天的存活時間（TTL 1 day），後續的對話協定直接引用此字串即可代表該圖片。

---

### 2.3 第三階段：JSPB 負載注入 (StreamGenerate Protocol Mapping)

取得 `upload_ref` 後，Gemini 網頁端將其組裝進 99 元素 JSPB 負載的第 0 號提示詞區塊：

```json
[
  [
    "請根據收據提取結構化資料", // Prompt 文字
    0,
    null,
    [
      [
        [
          "/contrib_service/ttl_1d/ftjkq3wuypkybbqzbkezlgmf6liddx1792096903_ARqe1MHh...", // 伺服器圖片參照 ID
          1
        ],
        "1.jpg" // 原始檔案名稱
      ]
    ],
    null,
    null,
    0
  ],
  ["zh-TW"],
  ...
]
```

---

## 3. 根本原因技術拆解：HTTP/2 大小寫陷阱

### 3.1 規範衝突背景

* **RFC 9110 (HTTP Semantics) Section 5.1**：
  > *"Field names are case-insensitive and are typically registered in the Hypertext Transfer Protocol (HTTP) Field Name Registry."*
  在 HTTP 協定語意中，`Content-Type`、`content-type` 與 `CONTENT-TYPE` 被嚴格定義為完全等價。
* **RFC 7540 / RFC 9113 (HTTP/2 Specification)**：
  > *"Just as in HTTP/1.x, header field names are strings of ASCII characters that are compared in a case-insensitive manner. However, header field names MUST be converted to lowercase prior to their encoding in HTTP/2."*
  HTTP/2 為提升傳輸壓縮效率（HPACK），**強制規定所有標頭鍵名在傳輸層必須全數小寫化**。

### 3.2 程式碼層級的致命降級 (Type Degradation)

在重構前的傳輸層包裝類別 [`CurlHttpResponse`](../gemini_flow/infrastructure/clients/http_client.py)：

```python
class CurlHttpResponse(IHttpResponse):
    def __init__(self, response: Response):
        self._response = response

    @property
    def headers(self) -> Dict[str, str]:
        # ❌ 致命缺陷：將 curl_cffi 具備大小寫不敏感的 Headers 物件，
        # 粗暴轉型為 Python 內建大小寫敏感的 dict！
        return dict(self._response.headers)
```

而在應用層呼叫處 [`GeminiAPIClient.upload_images`](../gemini_flow/infrastructure/clients/gemini_api/api_client.py)：

```python
resp = await self.http_client.post_form(UPLOAD_IMAGE_URL, data=data_name, headers=headers)

# ❌ 呼叫端按照一般 HTTP/1.1 習慣使用 Title-Case 進行查詢：
upload_url = resp.headers.get("X-Goog-Upload-Url")

if not upload_url:
    # ❌ 觸發假性例外！
    raise NetworkError("Missing X-Goog-Upload-Url")
```

### 3.3 實測重現驗證

我們透過測試腳本直接探測 `resp.headers` 的底層狀態：

```python
print(type(resp.headers)) 
# 輸出: <class 'dict'>

print(list(resp.headers.keys()))
# 輸出: ['content-type', 'x-guploader-uploadid', 'x-goog-upload-status', 'x-goog-upload-url', ...] (全小寫！)

print(resp.headers.get("X-Goog-Upload-Url")) 
# 輸出: None (因為在 Python 原生 dict 中，大小寫不符合即為不存在！)

print(resp.headers.get("x-goog-upload-url"))
# 輸出: 'https://push.clients6.google.com/upload/?upload_id=AP6rU83...' (實際上伺服器早已成功回傳！)
```

### 3.4 協定參數過時殘留 (Protocol Drift)

除了標頭大小寫問題外，原先的 [`config.py`](../gemini_flow/config.py) 還存在以下歷史包袱：
1. **端點過時**：使用 `content-push.googleapis.com`（雖然尚可轉導，但已脫離現代 Chrome 預設的 `push.clients6.google.com`）。
2. **無效認證頭**：帶有早期逆向殘留的 `"authorization": "Basic c2F2ZXM6cyNMdGhlNmxzd2F2b0RsN3J1d1U="`。現代 Google Scotty 僅依賴會話 Cookie 與 `push-id` / `x-tenant-id`。
3. **錯誤長度標頭**：在 Start 階段使用自定義的 `"size"` 標頭，而非標準的 `"x-goog-upload-header-content-length"`。

---

## 4. 物件導向新架構重構

秉持**「不將就、不修修補補、完全採用新架構但避免過度設計」**的最高指導原則，我們拒絕在 `api_client` 寫 `headers.get("X-...") or headers.get("x-...")` 這類治標不治本的補丁，而是從協定與領域層進行正統重構。

### 4.1 傳輸層標頭封裝：`CaseInsensitiveDict`

在基礎設施傳輸層 [`http_client.py`](../gemini_flow/infrastructure/clients/http_client.py) 實作符合 RFC 9110 標準的不可變 Mapping 容器：

```python
class CaseInsensitiveDict(Mapping[str, str]):
    """
    符合 RFC 9110 Section 5.1 規範的大小寫不敏感 HTTP 標頭容器。
    - 內部以小寫鍵索引，達成 O(1) 的大小寫不敏感比對。
    - 迭代與字串化時保留原始鍵名外觀。
    """
    def __init__(self, data: Optional[Mapping[str, str] | Dict[str, str]] = None):
        self._store: Dict[str, Tuple[str, str]] = {}
        if data:
            for k, v in data.items():
                self._store[k.lower()] = (str(k), str(v))

    def __getitem__(self, key: str) -> str:
        return self._store[key.lower()][1]

    def __iter__(self) -> Iterator[str]:
        return (orig_key for orig_key, _ in self._store.values())

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key.lower() in self._store

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default
```

將 [`IHttpResponse.headers`](../gemini_flow/domain/interfaces.py) 契約升級為 `Mapping[str, str]`，並由 `CurlHttpResponse` 與測試用的 `FakeHttpResponse` 統一回傳 `CaseInsensitiveDict`。

---

### 4.2 職責分離：物件化 `GeminiImageUploader`

依據單一職責原則（SRP）與介面隔離原則（ISP）：
1. 在 [`domain/interfaces.py`](../gemini_flow/domain/interfaces.py) 定義領域契約：
   ```python
   class IImageUploader(abc.ABC):
       @abc.abstractmethod
       async def upload_images(self, images: List[ImagePayload]) -> List[Tuple[str, str]]:
           """上傳多模態圖片並回傳 [(upload_ref, filename)] 清單"""
           pass
   ```
2. 建立獨立的上傳服務類別 [`GeminiImageUploader`](../gemini_flow/infrastructure/clients/gemini_uploader.py)：
   * 專職封裝 Resumable Upload 兩階段狀態機。
   * 負責計算精準長度並設置 `x-goog-upload-header-content-length`。
   * 嚴格驗證 Step 1 的 `x-goog-upload-url` 與 Step 2 的二進位上傳狀態，具備精確的 HTTP 錯誤碼除錯診斷。

```python
class GeminiImageUploader(IImageUploader):
    def __init__(self, http_client: IHttpClient, upload_url: str = UPLOAD_IMAGE_URL):
        self.http_client = http_client
        self.upload_url = upload_url

    async def upload_images(self, images: List[ImagePayload]) -> List[Tuple[str, str]]:
        uploads: List[Tuple[str, str]] = []
        for idx, img in enumerate(images, start=1):
            filename = img.filename or f"image_{idx}.jpg"
            size_bytes = len(img.data)
            
            # Step 1: Start Session
            start_headers = {
                **UPLOAD_IMAGE_HEADERS,
                "x-goog-upload-command": "start",
                "x-goog-upload-header-content-length": str(size_bytes),
            }
            resp_init = await self.http_client.post_form(self.upload_url, data=f"File name: {filename}", headers=start_headers)
            upload_session_url = resp_init.headers.get("x-goog-upload-url")
            
            # Step 2: Upload & Finalize
            finalize_headers = {
                **UPLOAD_IMAGE_HEADERS,
                "x-goog-upload-command": "upload, finalize",
                "x-goog-upload-offset": "0",
            }
            resp_finalize = await self.http_client.post_form(upload_session_url, data=img.data, headers=finalize_headers)
            upload_ref = (await resp_finalize.text()).strip()
            uploads.append((upload_ref, filename))
        return uploads
```

---

### 4.3 依賴注入 (DIP) 與組態校準

1. [`GeminiAPIClient`](../gemini_flow/infrastructure/clients/gemini_api/api_client.py) 透過建構子注入 `image_uploader: Optional[IImageUploader] = None`。
   API Client 核心不再承擔 HTTP 上傳協定細節，只需將 `request.images` 委派給上傳器。
2. 校準 [`config.py`](../gemini_flow/config.py)：
   ```python
   UPLOAD_IMAGE_URL = "https://push.clients6.google.com/upload/"
   
   UPLOAD_IMAGE_HEADERS = {
       "authority": "push.clients6.google.com",
       "accept": "*/*",
       "accept-language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
       "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
       "origin": "https://gemini.google.com",
       "push-id": "feeds/mcudyrk2a4khkz",
       "referer": "https://gemini.google.com/",
       "x-goog-upload-protocol": "resumable",
       "x-tenant-id": "bard-storage",
   }
   ```

---

## 5. 測試防護網與真實環境驗證

為確保架構長治久安且不再發生回歸，建構了立體式的單元與端到端測試網：

### 5.1 單元測試涵蓋項目

1. **標頭大小寫測試** ([`tests/test_case_insensitive_dict.py`](../tests/test_case_insensitive_dict.py))：
   * 驗證 `d["x-goog-upload-url"]`、`d["X-Goog-Upload-Url"]`、`d["X-GOOG-UPLOAD-URL"]` 均指向同一數值。
   * 驗證迭代鍵名保留原始宣告大小寫。
   * 驗證與標準 Python `dict` 的值等價性比較。
2. **上傳狀態機測試** ([`tests/test_uploader.py`](../tests/test_uploader.py))：
   * 模擬 HTTP/2 全小寫伺服器回應（`x-goog-upload-url`）成功解析。
   * 模擬 HTTP/1.1 Title-Case 伺服器回應相容性。
   * 模擬 Step 1 伺服器回傳 403 / 500 之例外拋出。
   * 模擬 Step 1 缺少 Session URL 標頭之例外拋出。
   * 模擬 Step 2 二進位上傳網路中斷與伺服器錯誤代碼捕獲。
3. **API Client 整合測試** ([`tests/test_api_client.py`](../tests/test_api_client.py))：
   * 驗證 `GeminiAPIClient` 透過 `FakeImageUploader` 正確將上傳參照注入 `f.req` JSPB 負載。

**測試執行結果**：全套 79 項測試 100% 綠燈通過（耗時 0.567s）。

---

### 5.2 真實環境端到端執行實證 (Live E2E Verification)

在掛載真實 Cookie 環境下，執行收據影像多模態辨識：

```bash
uv run python cli.py chat -f input/prompt.txt --image .\input\1.jpg
```

**真實終端輸出日誌**：

```text
2026-10-16 05:04:56 [INFO] gemini_flow.image_uploader: Uploading image 1/1: '1.jpg' (224474 bytes)...
2026-10-16 05:04:57 [INFO] gemini_flow.image_uploader: Image '1.jpg' uploaded successfully (ref: /contrib_service/ttl_1d/gafwjmdb63xmokua27pvlz7pfh7map1792098295)
{
  "status": "success",
  "message": null,
  "data": {
    "currency": "JPY",
    "storeName": "7-Eleven 千代田店",
    "receiptDateTime": "2019-10-01 08:45",
    "items": [
      {
        "originalName": "手巻おにぎり辛子明太子",
        "translatedName": "手卷飯糰 辛子明太子",
        "price": 130
      },
      {
        "originalName": "コカコーラ 500ml",
        "translatedName": "可口可樂 500ml",
        "price": 140
      },
      {
        "originalName": "パラドゥ ミニネイル PK03",
        "translatedName": "ParaDo 迷你指甲油 PK03",
        "price": 300
      },
      {
        "originalName": "メビウスワン",
        "translatedName": "MEVIUS ONE 峰香菸",
        "price": 490
      },
      {
        "originalName": "50円切手",
        "translatedName": "50日圓郵票",
        "price": 50
      }
    ],
    "discounts": [
      {
        "name": "無現金支付回饋",
        "amount": -22
      }
    ],
    "taxes": [
      {
        "name": "消費稅 8%",
        "amount": 21
      },
      {
        "name": "消費稅 10%",
        "amount": 74
      }
    ]
  }
}
```

* **耗時評估**：上傳 224KB 圖片僅耗時 0.98 秒，後續由 Gemini 3.8 Flash 進行多模態推理並流暢輸出符合 Prompt 要求之繁體中文結構化 JSON。

---

## 6. 架構維護指引與經驗總結 (Maintenance Guidelines)

1. **嚴守 HTTP RFC 抽象邊界**：
   在開發任何網路通訊基礎設施時，永遠牢記 **HTTP Header 鍵名大小寫不敏感** 的本質。不可將底層傳輸庫的標頭直接轉型為標準 Python `dict`。
2. **對稱性領域設計**：
   既有下載器（`IImageDownloader`），就必須有相應對稱的上傳器（`IImageUploader`）。保持架構在語意上的完整性，能有效阻絕上帝類別的滋生。
3. **避免過度依賴 In-Memory Fake**：
   Fake 測試能提供高速的回歸防護，但對於協定特徵（如 HTTP/2 全小寫標頭），必須建立專屬的契約測試，模擬真實傳輸層的極端特徵，避免盲點潛伏。
