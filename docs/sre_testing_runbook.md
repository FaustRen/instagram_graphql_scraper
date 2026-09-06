<div align="right">

[English](sre_testing_runbook.en.md) · **繁體中文**

</div>

# SRE Testing Runbook — Instagram GraphQL Scraper

> **文件定位**：本文件是 `instagram-graphql-scraper` 的操作、測試與故障排除手冊。
> **目標讀者**：維護這支爬蟲的工程師、需要驗證或除錯爬蟲行為的 SRE。
> **適用範圍**：`InstagramGraphqlScraper`（`scraper.py`）、`InstagramEmbedClient`（`embed.py`）與其依賴的 `graphql.py`、`detail.py`、`instagram_context_json.py`、瀏覽器層（`base/base.py`、`pages/page_optional.py`、`utils/locator.py`）。
> **驗證版本**：commit `4e31b83`（`feat: implement date-limited Instagram pagination`），Python `3.13.1`，`python3 -m pytest -q` 結果為 `28 passed`（本機執行，執行於本文件撰寫當下）。
> **事實分級**：本文件每一項結論都標記下列其中一種來源：
> - **[原始碼確認]**：直接對照檔案與行號得出。
> - **[測試確認]**：由 `tests/test_graphql.py` 內既有測試涵蓋。
> - **[本機模擬確認]**：以假造的 request/response 物件在本機重現，不連線 Instagram。
> - **[尚未驗證]**：需要實際連線 Instagram 才能確認，本次未執行。
> - **[改善建議]**：目前尚未實作，僅為建議方向。

---

## 一、系統架構與類別圖

### 架構圖

完整原始檔：[system_architecture.mmd](system_architecture.mmd)　渲染圖：

![system architecture](system_architecture.png)

**重點解說**（皆為 **[原始碼確認]**）：

- 呼叫端（`example.py` / `manual_integration.py`）建立 `InstagramGraphqlScraper` 並呼叫 `get_user_posts()`；函式庫本身**沒有** CLI 或常駐服務進入點。
- 第一頁 GraphQL request 是由 Selenium Wire 在瀏覽器點擊「顯示更多貼文」後**攔截**得到的，不是由程式主動組出 payload。
- 後續分頁改用同一個 `requests.Session`，重放攔截到的 headers 與 payload，只替換 `variables.after` 游標。
- 同步補資料（`enrich_posts`）與非同步補資料（`enrich_posts_async` / `InstagramEmbedClient`）都會呼叫 embed 頁與一般貼文頁，但**不是同一段程式碼**，重試與 fallback 規則不完全相同（見第七、八節）。
- 目前**沒有任何持久化儲存**（沒有資料庫、沒有 Redis、沒有檔案快取）；所有「快取」或「去重集合」都只是函式或物件生命週期內的區域變數／實例屬性，詳見第六節。

### 類別圖

完整原始檔：[class_diagram.mmd](class_diagram.mmd)　渲染圖：

![class diagram](class_diagram.png)

**重點解說**（皆為 **[原始碼確認]**）：

- `InstagramGraphqlScraper` 是唯一的協調類別；它在建構子建立並持有 `requests.Session`，但 `PageOptional` 與 `InstagramEmbedClient` 都是「每次呼叫建立新的實例」，不是長期持有的屬性。
- `PageLocators`、`PageText` 是純常數容器，`PageOptional` 只是保存「類別本身」（`self.locator = PageLocators`），從未 `PageLocators()` 實例化。
- `graphql.py`、`detail.py`、`instagram_context_json.py`、`embed.py` 內大量重要邏輯（`capture_request`、`parse_connection`、`normalize_edge`、`merge_post_detail`、`extract_context_json`、`normalize_media`、`normalize_embed_html` 等）都是**模組層級函式**，不是類別方法；類別圖刻意不把它們畫成虛構的 class。

---

## 二、環境需求與依賴安裝

| 項目 | 需求 | 來源 |
|---|---|---|
| Python | `>= 3.10`（型別提示使用 `X \| None` 語法） | `setup.py` `python_requires` |
| `selenium` | `>= 4.20` | `requirements.txt` |
| `selenium-wire` | `>= 5.1` | `requirements.txt` |
| `requests` | `>= 2.31` | `requirements.txt` |
| `brotli` | `>= 1.1` | `requirements.txt` |
| `httpx` | `>= 0.27` | `requirements.txt` |
| Chrome / ChromeDriver | 需與本機 Chrome 版本相容；未提供 `driver_path` 時交給 Selenium Manager 自動解析 | `base/base.py` |

安裝：

```bash
cd instagram_graphql_scraper
pip install -r requirements.txt
# 或
pip install -e .
```

執行測試：

```bash
python3 -m pytest -q
```

---

## 三、執行前確認清單

- [ ] 確認 Python 版本 `>= 3.10`：`python3 --version`
- [ ] 確認依賴已安裝：`python3 -c "import selenium, seleniumwire, requests, httpx, brotli"`
- [ ] 確認 ChromeDriver 可用（若手動指定）：`"$DRIVER_PATH" --version`
- [ ] 確認目標帳號是公開帳號（私人帳號無法用未登入模式取得 timeline，**[尚未驗證]**：本文件未實測私人帳號行為）
- [ ] 確認網路可連線 `instagram.com`（僅在要做「最小可執行範例」或手動整合測試時需要；單元測試不需要網路）

---

## 四、最小可執行範例與資源清理

```python
from instagram_graphql_scraper import InstagramGraphqlScraper

scraper = InstagramGraphqlScraper(
    driver_path="/path/to/chromedriver",  # 可省略，交給 Selenium Manager
    open_browser=False,
)
try:
    posts = scraper.get_user_posts(
        ig_username_or_userid="some_public_username",
        days_limit=30,
        display_progress=True,
        max_pages=2,
    )
    print(len(posts), "posts collected")
finally:
    scraper.close()
```

**[原始碼確認]**（`scraper.py:333-338`）：

- `close()` 必須由呼叫端自行呼叫，`get_user_posts` 內部**不會**自動呼叫它。
- `InstagramGraphqlScraper` 沒有實作 `__enter__` / `__exit__`，不能用 `with` 語法。
- 若建構子有傳入自訂 `driver=`，`close()` 不會呼叫 `driver.quit()`（因為該實例不是自己建立的），只會關閉 `requests.Session`。
- `get_user_posts`、`capture_first_page`、`_request_next_page`、`enrich_posts` 內都沒有 `try/finally`；若這些函式中途拋出例外並往外傳遞，driver 與 session **不會**被自動關閉，清理完全是呼叫端的責任。

已知的 repository 範例（`manual_integration.py`、`example.py`）都用 `try/finally: scraper.close()` 包住呼叫，示範了正確的清理方式。

---

## 五、主要參數、設定位置與預設值

| 參數 | 設定位置 | 預設值 | 邊界行為（**[原始碼確認]**） |
|---|---|---|---|
| `driver_path` | 建構子 | `None` | 未提供時交給 Selenium Manager |
| `open_browser` | 建構子 | `False` | `True` 時停用 headless |
| `driver` | 建構子 | `None` | 提供時 `close()` 不會 `quit()` 它 |
| `ig_account` / `ig_pwd` | 建構子 | `None` | 兩者皆有值才會嘗試登入 |
| `enrich_details` | 建構子 | `True` | 控制 `get_user_posts` 結尾是否自動呼叫 `enrich_posts`（同步） |
| `ig_username_or_userid` | `get_user_posts` | 必填 | `str(...).strip()` 後為空字串會 `raise ValueError`（`scraper.py:176-178`） |
| `days_limit` | `get_user_posts` | `None` | 負數會 `raise ValueError`（`scraper.py:179-180`）；語意見下方說明 |
| `display_progress` | `get_user_posts` | `False` | 只影響 `print`，不影響停止條件 |
| `max_pages` | `get_user_posts` | `None` | 見下方「`max_pages` 是否包含第一頁」 |
| `max_posts` | `get_user_posts` | `None` | 計算「日期篩選後、去重後」的長度，不是原始 edge 數量 |
| `enrich_posts_async` 的 `max_concurrency` | 方法參數 | `10` | 與 `enrich_details` 無關，獨立設定 |
| `enrich_posts_async` 的 `timeout` | 方法參數 | `30`（秒） | — |
| `enrich_posts_async` 的 `max_retries` | 方法參數 | `2` | 總嘗試次數為 `max_retries + 1` |

**`max_pages` 是否包含第一頁？** 是。`page_count` 從 `1` 開始（代表第一頁已完成），迴圈條件是 `page_count < max_pages`（`scraper.py:193`）。因此：

- `max_pages=2` → 第一頁 + 最多再抓 1 頁，總共最多 2 頁。
- `max_pages=0` 與 `max_pages=1` 效果相同：只使用第一頁，不會再送出任何分頁請求（**[原始碼確認]**，因為 `1 < 0` 與 `1 < 1` 皆為假）。

**第一頁已達 `max_posts` 或 `days_limit` 時，是否仍會多抓一頁？**

- `days_limit`：不會。第一頁篩選後若 `reached_cutoff` 為真，`has_next` 直接設為 `False`（`scraper.py:190-193`），迴圈條件立即為假。**[本機模擬確認]**：已用假造的 `_request_next_page` 驗證，觸發 cutoff 後該函式從未被呼叫。
- `max_posts`：第一頁**不會**在迴圈進入前先做 `max_posts` 檢查；只有在進入 `while` 迴圈、抓完下一頁後才會檢查 `len(posts) >= max_posts`（`scraper.py:196-210`）。若第一頁本身已經超過 `max_posts`，`has_next` 為真且 `max_pages` 未限制時仍會多送出一次分頁請求，之後才在函式結尾統一裁切（`scraper.py:218`）。這代表：**單獨依賴 `max_posts` 有可能多打一次不必要的分頁請求**，若要避免，需搭配 `max_pages` 一起使用。

---

## 六、快取、去重與生命週期範圍（全部為 **[原始碼確認]**）

| 名稱 | 位置 | 有效範圍 | 說明 |
|---|---|---|---|
| `seen_posts` | `scraper.py:187` | 單次 `get_user_posts` 呼叫 | 去重鍵為 `post_id or graphql_id or shortcode`，三者皆缺時鍵值為 `None`，可能誤刪不同貼文（見第十一節） |
| `seen_cursors` | `scraper.py:188` | 單次 `get_user_posts` 呼叫 | 用於判斷 `next_cursor` 是否重複 |
| `enrich_posts` 的 `cache` | `scraper.py:244` | 單次 `enrich_posts` 呼叫 | key 為 `shortcode`；失敗時存 `{}`，不是清空整個 cache |
| `InstagramEmbedClient._tasks` | `embed.py:48` | 單一 `InstagramEmbedClient` 實例的存活期間 | 用於避免同一次 `fetch_many` 內重複請求同一個 `shortcode`；`enrich_posts_async` 每次呼叫都會建立新的 `InstagramEmbedClient`，不會跨呼叫共用 |

**沒有任何跨進程、跨呼叫或落地檔案的持久化快取。**

---

## 七、同步詳細資料補齊（`enrich_posts`）

只有 `enrich_details=True`（預設）時，才會在 `get_user_posts` 結尾自動呼叫一次。

**呼叫順序**（**[原始碼確認]**，`scraper.py:241-266`）：

1. 對每篇貼文取 `shortcode`；缺失或空字串直接跳過，不補資料。
2. 若 `shortcode` 已在 `cache`（同次呼叫內快取命中），直接合併，不發送任何請求，也**不影響**連續失敗計數。
3. 否則呼叫 `_get_detail_response(embed_url)`（重試策略見下）取得 embed 頁 HTML，交給 `normalize_embed_html()`：先試 `contextJSON`，失敗才退回 HTML 指標解析（`embed.py:128-137`）。
4. 若補到的 `taken_at_timestamp` 仍是 `None`，**再多發一次**一般貼文頁面的請求，只用來補日期／時間戳，不會重新取得 likes/comments。
5. 成功時 `cache[shortcode]` 存正常結果、連續失敗計數歸零；失敗（`requests.RequestException` 或 `ValueError`）時 `cache[shortcode] = {}`、連續失敗計數 `+1`。
6. 連續失敗達到 `3` 次時，記錄警告並**整個迴圈中斷**；尚未處理到的貼文保留原始 timeline 欄位，不會被丟棄，也不會再被嘗試。

**`_get_detail_response` 重試策略**（`scraper.py:298-323`）：

- 只在「連線層錯誤（無狀態碼）、429、5xx」時重試，最多 3 次嘗試。
- 401 / 403 與其他一般 4xx（例如 404）**立即失敗，不重試**——這與分頁重試的策略不同（分頁對一般 4xx 也會重試，見第八節）。

**合併規則**（`detail.py:158-176`，**[原始碼確認]**）：

- `merge_post_detail` 只在 `post` 對應欄位為 `None` 時才會填入 `detail` 的值，**不會覆蓋**已存在的有效值。
- `video_duration`、`video_url`、`like_count_is_approximate`、`comment_count_is_approximate`、`detail_source` 這幾個欄位，只有在補資料實際提供時才會被加進 `post` dict；補資料未執行或失敗時，這些欄位**可能完全不存在**於回傳的 dict 中（不是「存在但為 `None`」）。

---

## 八、非同步詳細資料補齊（`enrich_posts_async` / `InstagramEmbedClient`）

**不會被 `get_user_posts` 自動呼叫。** 呼叫端必須在 `get_user_posts` 回傳後自行 `await`：

```python
import asyncio

posts = scraper.get_user_posts("username", max_pages=2)
posts = asyncio.run(scraper.enrich_posts_async(posts, max_concurrency=10))
```

或直接使用 `InstagramEmbedClient` / `fetch_posts_embed`（`__init__.py` 有匯出）。

**與同步路徑的差異**（**[原始碼確認]**）：

- 沒有「連續失敗達到門檻即中止」機制；每篇貼文各自獨立嘗試（`embed.py:79-129`）。
- 沒有「`taken_at_timestamp` 缺失時再補抓一般頁面」的邏輯；只對 embed URL 發一次請求（含各自的重試）。
- 併發上限：`asyncio.Semaphore(max_concurrency)` 包住實際 GET 動作（`embed.py:46-48`, `93-95`），限制的是「同時在進行中的 GET 請求數」，不含排隊等待中的 task 建立本身。
- 任務去重：`fetch_post()` 若同一 `shortcode` 已有進行中的 task，直接 `await` 該 task，不重新發送請求（`embed.py:79-87`）；**[測試確認]**：`test_async_embed_batch_preserves_order_deduplicates_and_bounds_concurrency` 驗證了輸入 `["a","b","a","c"]` 只會實際發送 3 次請求。
- 結果順序：`fetch_many` 用 `asyncio.gather(*tasks)`，回傳順序與輸入順序一致，與各任務完成時間無關（同一測試驗證）。
- 個別任務失敗不影響其他任務：`_fetch_post_once` 內部把每種失敗都轉成 `{"shortcode": ..., "error": ...}` 回傳值而不是往外拋例外，`enrich_posts_async` 合併時只是 `continue`（不合併），其餘貼文的合併不受影響；**[測試確認]**：`test_async_embed_batch_failure_is_soft_and_keeps_order`。
- 重試範圍：429/5xx（`httpx.HTTPStatusError`）與逾時／網路層錯誤會重試，最多 `max_retries` 次；401/403/404 立即回傳失敗、不重試；**[測試確認]**：`test_async_embed_retries_503_but_not_404`。

**是否可能與同步補資料重複執行？** 可能。若 `enrich_details=True`（預設）又額外呼叫 `enrich_posts_async`，該次呼叫會對同一批貼文再跑一次 Embed 請求；`merge_post_detail` 本身是「缺值才補」，重複執行不會覆蓋已有的有效值，但仍會產生多餘的網路請求。**建議用法**：需要非同步補資料時，把建構子改成 `enrich_details=False`，避免同步補資料先跑一次。

---

## 九、回傳資料格式

`get_user_posts` 回傳 `list[dict]`。以下欄位由 `normalize_edge`（`graphql.py:144-172`）保證存在（值可能是 `None`，但 **key 一定存在**）：

```text
post_id, graphql_id, shortcode, post_url, caption, accessibility_caption,
typename, media_type, product_type, is_video, display_uri,
carousel_media_count, username, user_pk, user_graphql_id, edge_cursor,
like_count, comment_count, video_view_count, taken_at_timestamp, published_at
```

以下欄位只有在補資料成功合併時才會被加入，**可能完全不存在於 dict 中**：

```text
video_duration, video_url, like_count_is_approximate,
comment_count_is_approximate, detail_source
```

**原地修改行為**：`enrich_posts` 與 `enrich_posts_async` 都是直接修改傳入的 `post` dict（`post[field] = ...`），不會回傳新的物件；`get_user_posts` 回傳的就是同一批被就地修改過的 dict。

---

## 十、測試情境

以下情境優先使用既有自動化測試（`tests/test_graphql.py`）與離線 mock；標示「尚未有自動化測試」的情境，本節提供可重現的手動驗證步驟，**不建議對 Instagram 發送大量請求來刻意觸發限流**。

### 情境 1：基本第一頁擷取與正常分頁

- **目的**：確認第一頁與後續分頁能正確累積、去重，且第一頁不會被重複 replay。
- **前置條件**：無（mock 測試不需要網路）。
- **測試命令**：
  ```bash
  python3 -m pytest tests/test_graphql.py::test_first_capture_is_not_replayed_and_duplicate_posts_are_removed -q
  python3 -m pytest tests/test_graphql.py::test_end_cursor_comes_from_page_info -q
  ```
- **預期結果**：兩者皆 `passed`。
- **實際可觀察輸出**：`1 passed` × 2。
- **通過判定**：`pytest` exit code 為 0。
- **恢復步驟**：無需清理（純記憶體 mock）。
- **狀態**：**[測試確認]**。

### 情境 2：`max_pages` / `max_posts` / `days_limit` 邊界

- **目的**：確認第五節列出的邊界行為（`max_pages` 包含第一頁、`days_limit` 提前停止不多抓一頁、負數 `days_limit` 立即失敗）。
- **前置條件**：無。
- **測試命令**：
  ```bash
  python3 -m pytest tests/test_graphql.py::test_days_limit_filters_old_posts_and_signals_pagination_stop -q
  python3 -m pytest tests/test_graphql.py::test_accessibility_caption_date_is_parsed_for_days_limit -q
  ```
  另有一段**尚未寫成自動化測試**、僅本機模擬過的驗證（第一頁即達 cutoff 時是否還會多抓一頁），可用以下方式手動重現：
  ```bash
  python3 - <<'PY'
  import json
  from types import SimpleNamespace
  from scraper import InstagramGraphqlScraper
  from graphql import capture_request

  OPERATION = "PolarisLoggedOutDesktopWWWProfilePostsTabContentQuery_connection"
  def make_response(posts, end_cursor="c2", has_next_page=True):
      body = json.dumps({"data": {"node": {"polaris_ordered_timeline_connection": {
          "edges": [{"node": p, "cursor": f"e-{i}"} for i, p in enumerate(posts)],
          "page_info": {"end_cursor": end_cursor, "has_next_page": has_next_page},
      }}}}).encode()
      return SimpleNamespace(status_code=200, body=body, headers={"Content-Encoding": "identity"})
  def make_request(response):
      variables = json.dumps({"after": "initial", "first": 12, "id": "user-id"})
      body = f"variables={variables}&doc_id=doc-1&fb_api_req_friendly_name={OPERATION}"
      return SimpleNamespace(method="POST", url="https://www.instagram.com/api/graphql", body=body.encode(),
                              headers={"X-Fb-Friendly-Name": OPERATION, "Content-Type": "application/x-www-form-urlencoded"},
                              response=response)

  scraper = InstagramGraphqlScraper(driver=object())
  scraper.enrich_details = False
  old_post = [{"pk": "1", "id": "P1", "code": "s1", "accessibility_caption": "Photo by demo on January 1, 2020."}]
  first = capture_request(make_request(make_response(old_post, end_cursor="c2", has_next_page=True)), {})
  scraper.capture_first_page = lambda username: first
  called = []
  scraper._request_next_page = lambda cursor: called.append(cursor) or json.loads(make_response([]).body)
  scraper.get_user_posts("demo", days_limit=1)
  print("second_page_requested:", called)  # 預期為空 list
  PY
  ```
- **預期結果**：`test_days_limit_...` 與 `test_accessibility_caption_...` 皆 `passed`；手動重現腳本印出 `second_page_requested: []`。
- **通過判定**：以上皆成立。
- **狀態**：前兩者 **[測試確認]**；「第一頁即達 cutoff 不多抓一頁」為 **[本機模擬確認]**，非 CI 自動化測試。

### 情境 3：空結果、缺少識別欄位、缺少日期、重複貼文

- **目的**：確認缺欄位不會讓程式崩潰，並記錄一個已知的去重邊界問題。
- **測試命令**：
  ```bash
  python3 -m pytest tests/test_graphql.py::test_parse_all_media_types_and_optional_fields -q
  python3 -m pytest tests/test_graphql.py::test_repeated_cursor_stops_pagination -q
  ```
  識別欄位全缺的邊界情況**尚未有自動化測試**，可用以下方式手動重現（與第十一節的已知問題對應）：
  ```bash
  python3 - <<'PY'
  import json
  from types import SimpleNamespace
  from scraper import InstagramGraphqlScraper
  from graphql import capture_request

  OPERATION = "PolarisLoggedOutDesktopWWWProfilePostsTabContentQuery_connection"
  def make_response(posts, end_cursor="c2", has_next_page=True):
      body = json.dumps({"data": {"node": {"polaris_ordered_timeline_connection": {
          "edges": [{"node": p, "cursor": f"e-{i}"} for i, p in enumerate(posts)],
          "page_info": {"end_cursor": end_cursor, "has_next_page": has_next_page},
      }}}}).encode()
      return SimpleNamespace(status_code=200, body=body, headers={"Content-Encoding": "identity"})
  def make_request(response):
      variables = json.dumps({"after": "initial", "first": 12, "id": "user-id"})
      body = f"variables={variables}&doc_id=doc-1&fb_api_req_friendly_name={OPERATION}"
      return SimpleNamespace(method="POST", url="https://www.instagram.com/api/graphql", body=body.encode(),
                              headers={"X-Fb-Friendly-Name": OPERATION, "Content-Type": "application/x-www-form-urlencoded"},
                              response=response)

  scraper = InstagramGraphqlScraper(driver=object())
  scraper.enrich_details = False
  page1 = [{"pk": None, "id": None, "code": None}]
  page2 = [{"pk": None, "id": None, "code": None, "media_type": 99}]
  first = capture_request(make_request(make_response(page1, end_cursor="c2", has_next_page=True)), {})
  scraper.capture_first_page = lambda username: first
  scraper._request_next_page = lambda cursor: json.loads(make_response(page2, end_cursor="c3", has_next_page=False).body)
  posts = scraper.get_user_posts("demo", max_pages=2)
  print("count:", len(posts))  # 已知問題：實際會是 1，不是 2
  PY
  ```
- **預期結果**：前兩個測試 `passed`；手動腳本印出 `count: 1`（**這是已知問題，不是預期的正確行為**，見第十一節第 2 點）。
- **狀態**：前兩者 **[測試確認]**；識別欄位全缺情境為 **[本機模擬確認]**，且證實了一個尚未修正的問題。

### 情境 4：cursor 缺失、重複或循環

- **目的**：確認重複 cursor 會停止分頁，並記錄一段實際上永遠不會觸發的死碼分支。
- **測試命令**：
  ```bash
  python3 -m pytest tests/test_graphql.py::test_repeated_cursor_stops_pagination -q
  ```
- **預期結果**：`1 passed`；`calls == ["same"]`（只呼叫一次 `_request_next_page` 就停止）。
- **狀態**：**[測試確認]**。另外 **[本機模擬確認]**：迴圈開頭的 `if cursor in seen_cursors - {cursor}` 這個判斷式在數學上恆為 `False`（見第十一節第 1 點），真正生效的是迴圈尾端的 `next_cursor in seen_cursors` 檢查，本測試驗證的就是後者。

### 情境 5：逾時、連線失敗、429、5xx、不可重試錯誤

- **目的**：確認分頁與詳細頁面請求的重試策略符合第七、八節描述。
- **測試命令**：
  ```bash
  python3 -m pytest tests/test_graphql.py::test_async_embed_retries_503_but_not_404 -q
  ```
- **預期結果**：`1 passed`；503 會重試一次成功，404 立即回傳 `error` 且只嘗試 1 次（`attempts == {"temporary": 2, "missing": 1}`）。
- **狀態**：**[測試確認]**（此測試涵蓋非同步路徑）。同步路徑的 `_request_next_page` 與 `_get_detail_response` 重試策略**沒有專屬的自動化測試**，本節第七、八節的描述為 **[原始碼確認]**，尚未有對應測試。

### 情境 6：HTTP 成功但內容無效、JSON／GraphQL／HTML 解析失敗

- **目的**：確認 200 回應但 schema 不符時會產生明確錯誤，而不是靜默視為成功。
- **測試命令**：
  ```bash
  python3 -m pytest tests/test_graphql.py::test_schema_change_has_clear_error -q
  python3 -m pytest tests/test_graphql.py::test_empty_response_is_rejected -q
  python3 -m pytest tests/test_graphql.py::test_matcher_rejects_other_graphql_requests -q
  ```
- **預期結果**：三者皆 `passed`。
- **狀態**：**[測試確認]**。

### 情境 7：詳細資料補齊成功、fallback、快取命中、失敗

- **目的**：確認 `contextJSON` 解析失敗時會退回 HTML 指標解析，且快取命中不重複發送請求。
- **測試命令**：
  ```bash
  python3 -m pytest tests/test_graphql.py::test_context_json_null_uses_exact_html_metrics_fallback -q
  python3 -m pytest tests/test_graphql.py::test_detail_merge_does_not_overwrite_existing_exact_values -q
  ```
  `enrich_posts` 本身（快取命中與連續失敗計數）**沒有直接測試**，可用以下方式手動重現：
  ```bash
  python3 - <<'PY'
  import requests
  from scraper import InstagramGraphqlScraper

  scraper = InstagramGraphqlScraper(driver=object())
  attempts = []
  def fake_get(url, retries=3):
      attempts.append(url)
      raise requests.RequestException("boom")
  scraper._get_detail_response = fake_get

  posts = [
      {"shortcode": "a", "media_type": 1, "like_count": None},
      {"shortcode": "a", "media_type": 1, "like_count": None},
      {"shortcode": "b", "media_type": 1, "like_count": None},
      {"shortcode": "c", "media_type": 1, "like_count": None},
      {"shortcode": "d", "media_type": 1, "like_count": None},
  ]
  scraper.enrich_posts(posts)
  print("network_attempts:", attempts)  # 預期只有 a, b, c 三次（"a" 第二次是快取命中）
  print("post_d_untouched:", posts[-1])  # 預期完全沒有補資料欄位
  PY
  ```
- **預期結果**：前兩個測試 `passed`；手動腳本印出 `network_attempts` 只含 `a, b, c`（3 次，不含重複的 `a`），且 `d` 完全未被處理。
- **狀態**：`context_json` 與 `merge` 相關測試為 **[測試確認]**；`enrich_posts` 快取／連續失敗計數為 **[本機模擬確認]**（見第十一節第 7 點：`enrich_posts` 本身缺乏直接測試）。

### 情境 8：非同步併發上限、任務去重、結果順序、個別工作失敗

- **目的**：確認 `InstagramEmbedClient` 的併發上限、去重、順序保留與 fail-soft 行為。
- **測試命令**：
  ```bash
  python3 -m pytest tests/test_graphql.py::test_async_embed_batch_preserves_order_deduplicates_and_bounds_concurrency -q
  python3 -m pytest tests/test_graphql.py::test_async_embed_batch_failure_is_soft_and_keeps_order -q
  ```
- **預期結果**：兩者皆 `passed`；第一個測試以 `httpx.MockTransport` 驗證輸入 `["a","b","a","c"]` 只送出 3 次請求、結果順序與輸入一致、同時進行中的請求數不超過 `max_concurrency=2`。
- **狀態**：**[測試確認]**。

### 情境 9：正常結束、例外、中斷後的資源清理

- **目的**：確認分頁失敗時已收集的資料如何處理，以及 `close()` 的呼叫責任。
- **測試命令**：無對應自動化測試；以下為手動重現分頁失敗後資料遺失的行為：
  ```bash
  python3 - <<'PY'
  import json
  from types import SimpleNamespace
  from scraper import InstagramGraphqlScraper
  from graphql import capture_request, InstagramGraphQLError

  OPERATION = "PolarisLoggedOutDesktopWWWProfilePostsTabContentQuery_connection"
  def make_response(posts, end_cursor="c2", has_next_page=True):
      body = json.dumps({"data": {"node": {"polaris_ordered_timeline_connection": {
          "edges": [{"node": p, "cursor": f"e-{i}"} for i, p in enumerate(posts)],
          "page_info": {"end_cursor": end_cursor, "has_next_page": has_next_page},
      }}}}).encode()
      return SimpleNamespace(status_code=200, body=body, headers={"Content-Encoding": "identity"})
  def make_request(response):
      variables = json.dumps({"after": "initial", "first": 12, "id": "user-id"})
      body = f"variables={variables}&doc_id=doc-1&fb_api_req_friendly_name={OPERATION}"
      return SimpleNamespace(method="POST", url="https://www.instagram.com/api/graphql", body=body.encode(),
                              headers={"X-Fb-Friendly-Name": OPERATION, "Content-Type": "application/x-www-form-urlencoded"},
                              response=response)

  scraper = InstagramGraphqlScraper(driver=object())
  scraper.enrich_details = False
  first = capture_request(make_request(make_response([{"pk": "1", "id": "P1", "code": "s1"}], end_cursor="c2", has_next_page=True)), {})
  scraper.capture_first_page = lambda username: first
  scraper._request_next_page = lambda cursor: (_ for _ in ()).throw(InstagramGraphQLError("boom"))
  try:
      scraper.get_user_posts("demo", max_pages=5)
      print("returned normally (unexpected)")
  except InstagramGraphQLError as e:
      print("raised as expected; first-page posts are lost to caller:", str(e))
  PY
  ```
- **預期結果**：印出 `raised as expected; first-page posts are lost to caller: boom`，代表已收集的第一頁貼文不會被回傳。
- **通過判定**：`InstagramGraphQLError` 被拋出，且沒有任何 `posts` 被回傳給呼叫端。
- **恢復步驟**：呼叫端必須自行 `try/finally: scraper.close()`（本文件未針對「例外路徑是否也需要清理」提供自動化測試，這一段是 **[本機模擬確認]** + **[原始碼確認]** 的組合：程式碼本身沒有處理清理，責任在呼叫端）。
- **狀態**：**[本機模擬確認]** + **[原始碼確認]**；沒有對應的自動化測試。

---

## 十一、已知限制、已確認問題與尚未實作的改善方向

以下皆為 **[原始碼確認]** 或 **[本機模擬確認]**，本次未修改任何執行邏輯：

1. **分頁迴圈開頭的重複 cursor 檢查是死碼。** `scraper.py:194`：`if cursor in seen_cursors - {cursor}` 在集合運算上恆為 `False`（先減去自己再判斷是否存在，必然不存在）。目前有迴圈尾端的 `next_cursor in seen_cursors`（`scraper.py:215`）作為有效的安全網，此死碼目前無實際風險，但維護時容易誤判為已生效的保護機制。**[改善建議]**：移除或修正為 `cursor in seen_cursors`（需在 `.add()` 之前檢查）。
2. **識別欄位全缺時，去重邏輯可能誤刪不同貼文。** `scraper.py:187, 202-205`：去重鍵為 `post_id or graphql_id or shortcode`，三者皆缺時鍵值為 `None`；第二筆同樣缺欄位的貼文會被視為重複而遺失（情境 3 已模擬重現：2 篇變 1 篇）。**[改善建議]**：識別鍵全缺時改用 `edge_cursor` 或記錄警告並保留。
3. **分頁重試與詳細頁面重試對「哪些狀態碼可重試」定義不一致。** 分頁（`scraper.py:128-155`）對一般 4xx（含 404）仍會重試到滿 3 次嘗試；詳細頁面（`scraper.py:298-323`）只在無狀態碼／429／5xx 才重試，一般 4xx 立即失敗。**[改善建議]**：統一重試判斷邏輯。
4. **`days_limit` 不會因補資料取得更精確時間戳而重新篩選。** 篩選發生在分頁階段（依賴 timeline 的 `accessibility_caption`），補資料發生在分頁結束後；即使補資料取得了精確 `taken_at_timestamp`，也不會回頭重新評估是否符合 `days_limit`。**[改善建議]**：若需要精確篩選，須調整補資料時機或加入二次篩選。
5. **`days_limit` 提前停止假設嚴格新到舊排序，未處理置頂貼文。** 若某頁包含比 cutoff 更舊的置頂貼文，即使該頁其餘貼文仍較新，也會在該頁結束後停止抓取下一頁，可能漏抓下一頁原本存在的較新貼文。**[改善建議]**：需要排除置頂旗標後再判斷 cutoff；目前原始碼沒有處理置頂貼文的欄位。
6. **分頁失敗沒有部分成功回傳路徑。** 只要任何一次分頁請求重試耗盡仍失敗，整個 `get_user_posts` 呼叫會拋出例外、不回傳任何貼文，即使已經收集了多頁資料（情境 9 已重現）。這與 `enrich_posts` 的「單篇補資料失敗不影響其他貼文」設計不一致。**[改善建議]**：視需求評估是否改為記錄警告並回傳目前已收集的貼文。
7. **`enrich_posts` 與 `enrich_posts_async` 本身缺乏直接的自動化測試。** 目前測試只涵蓋它們呼叫的底層函式（`parse_post_detail_html`、`normalize_media`、`InstagramEmbedClient`），沒有針對這兩個方法本身（快取、連續失敗計數、提早中止、合併時機）的測試。本文件情境 7、9 提供的手動重現腳本可作為未來測試的雛形。**[改善建議]**：補上以 mock 的 `_get_detail_response` / `InstagramEmbedClient` 驗證這兩個方法整體行為的測試。
8. **私人帳號、登入態行為、以及 Instagram 頁面版型變動後的穩定性，本次沒有實際連線驗證。** **[尚未驗證]**。

---

## 十二、驗證紀錄與 Mermaid 渲染方式

**已執行的驗證**（本次撰寫文件時實際執行）：

```bash
python3 -m pytest -q
# 28 passed
```

- 9 個測試情境中，情境 1、2（部分）、3（部分）、4、5（部分）、6、7（部分）、8 有對應的既有自動化測試，已重新執行並確認 `passed`。
- 情境 2、3、7、9 中標示「尚未有自動化測試」的部分，已用本機模擬腳本重現（不連線 Instagram），並記錄實際輸出。
- 沒有對 `instagram.com` 執行任何實際連線測試；瀏覽器層（`close_login_prompt`、`click_display_button` 等 Selenium 定位器）在目前真實 Instagram 頁面上是否仍然有效，本次**未驗證**。

**Mermaid 渲染紀錄**：

- 工具：`@mermaid-js/mermaid-cli` `11.17.0`（透過 `npx --yes @mermaid-js/mermaid-cli`）。
- 指令：
  ```bash
  npx --yes @mermaid-js/mermaid-cli -i system_architecture.mmd -o system_architecture.png -b white -w 1800 -H 1400 --scale 2
  npx --yes @mermaid-js/mermaid-cli -i class_diagram.mmd -o class_diagram.png -b white -w 1600 -H 1600 --scale 2
  ```
- 兩張 PNG 皆已實際產生並以圖片檢視工具開啟確認：文字沒有裁切、節點沒有重疊到無法辨識的程度。`class_diagram.png` 因說明性 note 較長，畫布偏寬、文字相對較小，但放大後仍可辨識；如需更高解析度，可調整 `--scale` 參數重新渲染。
