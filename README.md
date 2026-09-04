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
