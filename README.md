# instagram-graphql-scraper

Collects posts from a public Instagram profile by capturing the browser's profile GraphQL request, then replaying subsequent pages through one `requests.Session`.

## Installation

```bash
pip install -r requirements.txt
# or
pip install -e .
```

## Usage

```python
from instagram_graphql_scraper import InstagramGraphqlScraper

scraper = InstagramGraphqlScraper(driver_path="/path/to/chromedriver")
try:
    posts = scraper.get_user_posts("username", max_pages=2, max_posts=24)
finally:
    scraper.close()
```

The browser flow opens the profile, dismisses an optional login dialog, scrolls once, clears Selenium Wire requests, and clicks the dynamic show-more-posts button once. The captured request supplies the URL, headers, cookies, form payload, variables, and `doc_id`; no dynamic GraphQL values are hardcoded.

`days_limit` is accepted for API compatibility but is not applied when the response has no reliable numeric timestamp. Use `max_pages` or `max_posts` for bounded collection.

For bounded asynchronous Embed enrichment:

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

## Tests

```bash
python3 -m pytest -q
```

The manual browser check is intentionally not part of CI:

```bash
python3 manual_integration.py 1989ivyshao --driver-path /path/to/chromedriver --max-pages 2
```

Do not place cookies, CSRF/LSD tokens, or captured payloads in source, fixtures, or logs.

## License

MIT, see [LICENSE](LICENSE).
