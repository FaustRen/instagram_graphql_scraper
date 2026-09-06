# Instagram GraphQL Scraper

Collects posts from a public Instagram profile by capturing the browser's profile GraphQL request, then replaying subsequent pages through one `requests.Session`.

## Install

```bash
pip install -r requirements.txt
# or
pip install -e .
```

## Requirements

```text
selenium>=4.20
selenium-wire>=5.1
requests>=2.31
brotli>=1.1
httpx>=0.27
```

# Support Me

If you enjoy this project and would like to support me, please consider donating 🙌
Your support will help me continue developing this project and working on other exciting ideas!

## 💖 Ways to Support:

- **PayPal**: [https://www.paypal.me/faustren1z](https://www.paypal.me/faustren1z)
- **Buy Me a Coffee**: [https://buymeacoffee.com/faustren1z](https://buymeacoffee.com/faustren1z)

Thank you for your support!! 🎉

### Usage

You can choose between two methods to collect user posts data.
- **Please set up the driver path first**
- **Without logging in**: works for any public profile; this is the default and recommended mode.
- **Logging in with your account credentials**: pass `ig_account`/`ig_pwd`; the browser attempts to log in before opening the profile.
- **Difference**: logging in may reduce extra login prompts Instagram shows to anonymous visitors, but this program only automates a normal browser session — it does not guarantee your account will avoid being blocked or challenged.

```python
# -*- coding: utf-8 -*-
from instagram_graphql_scraper import InstagramGraphqlScraper


## Example.1 - without logging in
if __name__ == "__main__":
    instagram_user_name = "1989ivyshao"
    days_limit = 120  # Number of days within which to scrape posts
    driver_path = "/path/to/chromedriver"

    ig_spider = InstagramGraphqlScraper(driver_path=driver_path, open_browser=False)
    try:
        res = ig_spider.get_user_posts(
            ig_username_or_userid=instagram_user_name,
            days_limit=days_limit,
            display_progress=True,
        )
        # print(res)
    finally:
        ig_spider.close()


## Example.2 - log in to your Instagram account to collect data
# if __name__ == "__main__":
    # instagram_user_name = "1989ivyshao"
    # ig_account = "instagram_account"
    # ig_pwd = "instagram_password"
    # days_limit = 30  # Number of days within which to scrape posts
    # driver_path = "/path/to/chromedriver"
    # ig_spider = InstagramGraphqlScraper(
    #     ig_account=ig_account, ig_pwd=ig_pwd, driver_path=driver_path, open_browser=False
    # )
    # try:
    #     res = ig_spider.get_user_posts(
    #         ig_username_or_userid=instagram_user_name, days_limit=days_limit, display_progress=True
    #     )
    #     # print(res)
    # finally:
    #     ig_spider.close()
```

Or bound collection by page/post count instead of date, using a context-manager style:

```python
from instagram_graphql_scraper import InstagramGraphqlScraper

scraper = InstagramGraphqlScraper(driver_path="/path/to/chromedriver")
try:
    posts = scraper.get_user_posts("username", max_pages=2, max_posts=24)
finally:
    scraper.close()
```

The browser flow opens the profile, dismisses an optional login dialog, scrolls once, clears Selenium Wire requests, and clicks the dynamic show-more-posts button once. The captured request supplies the URL, headers, cookies, form payload, variables, and `doc_id`; no dynamic GraphQL values are hardcoded.

For bounded asynchronous Embed enrichment (opt-in, not run automatically by `get_user_posts`):

```python
import asyncio
from instagram_graphql_scraper import InstagramEmbedClient

async def enrich(posts):
    async with InstagramEmbedClient(max_concurrency=10) as client:
        return await client.fetch_many(posts)

details = asyncio.run(enrich(posts))
```

The batch client preserves input order, deduplicates shortcodes per run, and returns a per-post error result instead of failing the whole batch. The single-post normalized CLI remains available:

```bash
python3 instagram_context_json.py "https://www.instagram.com/p/SHORTCODE/embed/captioned/"
python3 instagram_context_json.py "https://www.instagram.com/p/SHORTCODE/embed/captioned/" --full
```

### Optional parameters

- **display_progress**:
  A boolean value (`True` or `False`).
  If set to `True`, the scraper prints `Collected N Instagram posts` after each timeline page is fetched, so progress is visible while pagination continues.

- **open_browser**:
  If set to `True`, the scraper launches a visible Chrome window instead of running headless.
  This is mainly useful for debugging when scraping fails or behaves unexpectedly; it does not by itself unlock additional data.

- **driver_path**:
  Path to your local ChromeDriver executable. Required unless you pass an already-created `driver=` instance.

- **driver**:
  An externally managed Selenium WebDriver instance. When supplied, `close()` will not quit it for you.

- **ig_username_or_userid**:
  The public Instagram username (or compatible ID) to scrape posts from.

- **days_limit**:
  Keep posts newer than this many days, counting backwards from today, using each post's `accessibility_caption` date. Pagination stops early once older posts are reached; posts without a parseable date are kept rather than dropped.

- **max_pages**:
  Optional maximum number of timeline pages to fetch (the first page counts as page 1).

- **max_posts**:
  Optional maximum number of posts to return; trims the collected list after the last fetched page.

- **ig_account**:
  Your Instagram account username, used only if you want to scrape while logged in.

- **ig_pwd**:
  Your Instagram account password, used only if you want to scrape while logged in. Login failures are caught and logged rather than raised.

- **enrich_details**:
  A boolean value (`True` by default). When `True`, `get_user_posts` automatically fetches each post's Embed page afterward to fill in `like_count`, `comment_count`, `taken_at_timestamp`, and related fields.

## Result example

Each post is a `dict` with a guaranteed schema (see `normalize_edge` in [graphql.py](graphql.py)); enrichment adds a few optional fields only when available:

```python
{
    'post_id': '3949676966589363019',
    'graphql_id': 'POLARIS_3949676966589363019',
    'shortcode': 'DbQEkZbGfNL',
    'post_url': 'https://www.instagram.com/p/DbQEkZbGfNL/',
    'caption': '突然發現IG又改版驚呼連連的我...',
    'accessibility_caption': 'Photo by 邵雨薇IvyShao on July 26, 2026.',
    'typename': 'XIGPolarisCarouselMedia',
    'media_type': 8,
    'product_type': 'carousel_container',
    'is_video': False,
    'display_uri': 'https://scontent.cdninstagram.com/v/t51.82787-15/753990711_...jpg',
    'carousel_media_count': 20,
    'username': '1989ivyshao',
    'user_pk': '370962121',
    'user_graphql_id': '17841400543635796',
    'edge_cursor': 'AQHTN9x...',
    'like_count': 14437,
    'comment_count': 60,
    'video_view_count': None,
    'taken_at_timestamp': None,
    'published_at': '2026-07-26',
    'detail_source': 'post_embed_html',
}
```

Notes on the fields above:

- `taken_at_timestamp` and `published_at` are populated only when enrichment can parse an exact timestamp; when it cannot, `published_at` falls back to the coarse `accessibility_caption` date (e.g. `'2026-07-26'` instead of an ISO datetime), and this fallback is not guaranteed to be identical across separate runs of the same post since enrichment re-fetches over the network each time.
- Posts where enrichment failed keep only the original timeline fields (`like_count`, `comment_count`, `taken_at_timestamp`, `published_at` all `None`, and no `detail_source` key at all).
- Video posts additionally carry `video_duration` and `video_url` when enrichment succeeds.

The full sample result for both usage patterns above is saved in [docs/sample_output.md](docs/sample_output.md) for reference.

## Tests

```bash
python3 -m pytest -q
```

The manual browser check is intentionally not part of CI:

```bash
python3 manual_integration.py 1989ivyshao --driver-path /path/to/chromedriver --max-pages 2
```

## Documentation

See [docs/](docs/) for the system architecture diagram, class diagram, and a bilingual ([繁體中文](docs/sre_testing_runbook.md) / [English](docs/sre_testing_runbook.en.md)) SRE testing runbook covering environment setup, parameter boundaries, and known issues.


Do not place cookies, CSRF/LSD tokens, or captured payloads in source, fixtures, or logs.

## License

MIT, see [LICENSE](LICENSE).
