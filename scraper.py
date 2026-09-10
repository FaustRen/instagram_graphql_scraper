"""Public Instagram timeline scraper and detail enrichment orchestration."""

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

try:
    from .embed import InstagramEmbedClient, normalize_embed_html
except ImportError:
    from embed import InstagramEmbedClient, normalize_embed_html

try:
    from .detail import merge_post_detail, parse_post_detail_html
except ImportError:
    from detail import merge_post_detail, parse_post_detail_html

try:
    from .graphql import (
        InstagramGraphQLError,
        capture_request,
        extract_preloaded_posts,
        is_target_graphql_request,
        log_capture,
        next_payload,
        parse_connection,
        parse_accessibility_date,
        request_debug_summary,
    )
    from .models import CapturedRequest
except ImportError:
    from graphql import (
        InstagramGraphQLError,
        capture_request,
        extract_preloaded_posts,
        is_target_graphql_request,
        log_capture,
        next_payload,
        parse_connection,
        parse_accessibility_date,
        request_debug_summary,
    )
    from models import CapturedRequest


class InstagramGraphqlScraper:
    """Scrape Instagram profile timelines and enrich posts from Embed pages."""
    def __init__(
        self,
        driver_path: str | None = None,
        open_browser: bool = False,
        driver: Any = None,
        ig_account: str | None = None,
        ig_pwd: str | None = None,
        logger: logging.Logger | None = None,
        enrich_details: bool = True,
    ):
        """Initialize browser, session, and enrichment settings.

        Args:
            driver_path: Optional ChromeDriver executable path.
            open_browser: Whether to run Chrome visibly.
            driver: Optional externally managed Selenium driver.
            ig_account: Optional Instagram login username.
            ig_pwd: Optional Instagram login password.
            logger: Optional logger instance.
            enrich_details: Whether sync Embed enrichment runs automatically.
        """
        self.logger = logger or logging.getLogger(__name__)
        self._owns_driver = driver is None
        self.driver = driver
        self.driver_path = driver_path
        self.open_browser = open_browser
        self.ig_account = ig_account
        self.ig_pwd = ig_pwd
        self.session = requests.Session()
        self.captured_request: CapturedRequest | None = None
        self.enrich_details = enrich_details
        self.preloaded_posts: list[dict[str, Any]] = []

    def _build_driver(self) -> Any:
        """Create the Selenium Wire driver when one was not supplied."""
        if self.driver is not None:
            return self.driver
        try:
            from .base.base import BasePage
        except ImportError:
            from base.base import BasePage
        self.driver = BasePage(self.driver_path, self.open_browser).driver
        return self.driver

    def _prepare_browser(self, username: str) -> None:
        """Open a profile and trigger the browser timeline request."""
        try:
            from .pages.page_optional import PageOptional
        except ImportError:
            from pages.page_optional import PageOptional
        page = PageOptional(self.driver, self.ig_account, self.ig_pwd, self.logger)
        page.open_profile(username)
        try:
            self.preloaded_posts = extract_preloaded_posts(self.driver.requests, username)
        except Exception as error:
            self.logger.debug("Could not extract preloaded profile posts: %s", error)
            self.preloaded_posts = []
        page.close_login_prompt()
        page.scroll_window()
        page.clear_requests()
        page.click_display_button(username)

    def capture_first_page(self, username: str, timeout: int = 20) -> CapturedRequest:
        """Capture and store the first profile timeline GraphQL response."""
        driver = self._build_driver()
        self._prepare_browser(username)
        from selenium.webdriver.support.ui import WebDriverWait
        try:
            request = WebDriverWait(driver, timeout).until(
                lambda current_driver: next(
                    (item for item in current_driver.requests if is_target_graphql_request(item, self.logger)),
                    False,
                )
            )
        except Exception as error:
            raise InstagramGraphQLError(
                "Timed out waiting for Instagram profile posts GraphQL response; "
                f"{request_debug_summary(driver.requests)}"
            ) from error
        cookies = {item["name"]: item["value"] for item in driver.get_cookies()}
        self.captured_request = capture_request(request, cookies)
        self.session.cookies.update(cookies)
        self.session.headers.update(self.captured_request.replay_headers)
        log_capture(self.logger, self.captured_request)
        return self.captured_request

    def _request_next_page(self, cursor: str, retries: int = 3) -> dict[str, Any]:
        """Replay one timeline page using the captured request template."""
        if self.captured_request is None:
            raise InstagramGraphQLError("First GraphQL response must be captured before pagination")
        payload = next_payload(self.captured_request, cursor)
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                response = self.session.post(
                    self.captured_request.url,
                    data=payload,
                    headers=self.captured_request.replay_headers,
                    timeout=30,
                )
                if response.status_code in (401, 403):
                    raise InstagramGraphQLError(f"Instagram pagination rejected with HTTP {response.status_code}")
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError, InstagramGraphQLError) as error:
                last_error = error
                if isinstance(error, InstagramGraphQLError) and "rejected" in str(error):
                    break
                if attempt + 1 < retries:
                    time.sleep(2**attempt)
        raise InstagramGraphQLError(f"Instagram pagination request failed: {last_error}") from last_error

    def get_user_posts(
        self,
        ig_username_or_userid: str,
        days_limit: int | None = None,
        display_progress: bool = False,
        max_pages: int | None = None,
        max_posts: int | None = None,
    ) -> list[dict[str, Any]]:
        """Collect, paginate, deduplicate, and optionally enrich profile posts.

        Args:
            ig_username_or_userid: Public Instagram username or compatible ID.
            days_limit: Keep posts newer than this many days when dates are known.
            display_progress: Print collection progress after each page.
            max_pages: Optional maximum number of timeline pages.
            max_posts: Optional maximum number of returned posts.

        Returns:
            Posts in timeline order.
        """
        username = str(ig_username_or_userid).strip()
        if not username:
            raise ValueError("ig_username_or_userid must not be empty")
        if days_limit is not None and days_limit < 0:
            raise ValueError("days_limit must be non-negative")
        cutoff_date = (
            datetime.now(timezone.utc).date() - timedelta(days=days_limit)
            if days_limit is not None else None
        )
        captured = self.capture_first_page(username)
        posts, cursor, has_next = parse_connection(captured.first_response)
        posts = self._merge_preloaded_posts(posts)
        seen_posts = {post.get("post_id") or post.get("graphql_id") or post.get("shortcode") for post in posts}
        seen_cursors = {cursor} if cursor else set()
        page_count = 1
        posts, reached_cutoff = self._filter_posts_by_days(posts, cutoff_date)
        if reached_cutoff:
            has_next = False
        while has_next and cursor and (max_pages is None or page_count < max_pages):
            if cursor in seen_cursors - {cursor}:
                self.logger.warning("Stopping pagination because cursor repeated")
                break
            seen_cursors.add(cursor)
            response_json = self._request_next_page(cursor)
            page_posts, next_cursor, has_next = parse_connection(response_json)
            page_posts, reached_cutoff = self._filter_posts_by_days(page_posts, cutoff_date)
            for post in page_posts:
                identity = post.get("post_id") or post.get("graphql_id") or post.get("shortcode")
                if identity not in seen_posts:
                    posts.append(post)
                    seen_posts.add(identity)
            page_count += 1
            if display_progress:
                print(f"Collected {len(posts)} Instagram posts")
            if max_posts is not None and len(posts) >= max_posts:
                posts = posts[:max_posts]
                break
            if reached_cutoff:
                self.logger.info("Stopping pagination at days_limit=%s", days_limit)
                break
            if not next_cursor or next_cursor in seen_cursors:
                self.logger.warning("Stopping pagination because end_cursor repeated or is empty")
                break
            cursor = next_cursor
        posts = posts[:max_posts] if max_posts is not None else posts
        if self.enrich_details:
            self.enrich_posts(posts)
        return posts

    def _merge_preloaded_posts(self, posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Prepend posts embedded in the initial profile page, deduplicated."""
        if not self.preloaded_posts:
            return posts
        seen_posts = set()
        merged = []
        for post in [*self.preloaded_posts, *posts]:
            identity = post.get("post_id") or post.get("graphql_id") or post.get("shortcode")
            if identity in seen_posts:
                continue
            seen_posts.add(identity)
            merged.append(post)
        return merged

    @staticmethod
    def _filter_posts_by_days(
        posts: list[dict[str, Any]], cutoff_date: date | None
    ) -> tuple[list[dict[str, Any]], bool]:
        """Filter old dated posts and report whether the cutoff was reached."""
        if cutoff_date is None:
            return posts, False
        filtered = []
        reached_cutoff = False
        for post in posts:
            post_date = parse_accessibility_date(post.get("accessibility_caption"))
            if post_date is not None and post_date < cutoff_date:
                reached_cutoff = True
                continue
            filtered.append(post)
        return filtered, reached_cutoff

    def enrich_posts(self, posts: list[dict[str, Any]]) -> None:
        """Synchronously enrich posts while preserving fail-soft behavior."""
        cache: dict[str, dict[str, Any]] = {}
        consecutive_failures = 0
        for post in posts:
            shortcode = post.get("shortcode")
            if not shortcode:
                continue
            if shortcode not in cache:
                try:
                    detail_path = "reel" if post.get("media_type") == 2 else "p"
                    embed_url = f"https://www.instagram.com/{detail_path}/{shortcode}/embed/captioned/"
                    response = self._get_detail_response(embed_url)
                    cache[shortcode] = normalize_embed_html(response.text, shortcode)
                    if cache[shortcode].get("taken_at_timestamp") is None:
                        page_url = f"https://www.instagram.com/{detail_path}/{shortcode}/"
                        page_detail = parse_post_detail_html(self._get_detail_response(page_url).text, shortcode)
                        for field in ("taken_at_timestamp", "published_at"):
                            if cache[shortcode].get(field) is None:
                                cache[shortcode][field] = page_detail.get(field)
                    consecutive_failures = 0
                except (requests.RequestException, ValueError) as error:
                    self.logger.warning("Post detail enrichment failed for shortcode=%s: %s", shortcode, error)
                    cache[shortcode] = {}
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        self.logger.warning("Post detail enrichment disabled for remaining posts")
                        break
            merge_post_detail(post, cache[shortcode])

    async def enrich_posts_async(
        self,
        posts: list[dict[str, Any]],
        max_concurrency: int = 10,
        timeout: float = 30,
        max_retries: int = 2,
    ) -> list[dict[str, Any]]:
        """Asynchronously enrich posts with bounded Embed concurrency.

        Args:
            posts: Existing normalized timeline posts.
            max_concurrency: Maximum simultaneous Embed requests.
            timeout: Per-request timeout in seconds.
            max_retries: Number of transient retries.

        Returns:
            The same posts list with available detail fields merged in order.
        """
        async with InstagramEmbedClient(max_concurrency, timeout, max_retries) as client:
            details = await client.fetch_many(posts)
        details_by_shortcode = {
            detail.get("shortcode"): detail
            for detail in details
            if detail.get("shortcode")
        }
        for post in posts:
            detail = details_by_shortcode.get(post.get("shortcode"))
            if not detail or detail.get("error"):
                continue
            merge_post_detail(post, detail)
        return posts

    def _get_detail_response(self, url: str, retries: int = 3) -> requests.Response:
        """GET one detail page with safe headers and transient retries."""
        last_error: requests.RequestException | None = None
        detail_headers = {
            key: value
            for key, value in self.session.headers.items()
            if key.lower() not in {
                "content-type", "x-fb-friendly-name", "x-fb-lsd",
                "x-csrftoken", "fb_api_req_friendly_name",
            }
        }
        detail_headers["Accept"] = "text/html,application/xhtml+xml"
        for attempt in range(retries):
            try:
                response = self.session.get(url, headers=detail_headers, timeout=30)
                if response.status_code in (401, 403):
                    response.raise_for_status()
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                return response
            except requests.RequestException as error:
                last_error = error
                status_code = getattr(error.response, "status_code", None)
                if attempt + 1 < retries and (status_code is None or status_code == 429 or status_code >= 500):
                    time.sleep(2**attempt)
                else:
                    break
        raise last_error or requests.RequestException("Instagram detail request failed")

    def close(self) -> None:
        """Close the owned browser and requests session."""
        if self.driver is not None and self._owns_driver:
            self.driver.quit()
        self.session.close()

    quit = close
