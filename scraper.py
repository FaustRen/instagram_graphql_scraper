import logging
import time
from typing import Any

import requests

try:
    from .graphql import (
        InstagramGraphQLError,
        capture_request,
        is_target_graphql_request,
        log_capture,
        next_payload,
        parse_connection,
        request_debug_summary,
    )
    from .models import CapturedRequest
except ImportError:
    from graphql import (
        InstagramGraphQLError,
        capture_request,
        is_target_graphql_request,
        log_capture,
        next_payload,
        parse_connection,
        request_debug_summary,
    )
    from models import CapturedRequest


class InstagramGraphqlScraper:
    def __init__(
        self,
        driver_path: str | None = None,
        open_browser: bool = False,
        driver: Any = None,
        ig_account: str | None = None,
        ig_pwd: str | None = None,
        logger: logging.Logger | None = None,
    ):
        self.logger = logger or logging.getLogger(__name__)
        self._owns_driver = driver is None
        self.driver = driver
        self.driver_path = driver_path
        self.open_browser = open_browser
        self.ig_account = ig_account
        self.ig_pwd = ig_pwd
        self.session = requests.Session()
        self.captured_request: CapturedRequest | None = None

    def _build_driver(self) -> Any:
        if self.driver is not None:
            return self.driver
        try:
            from .base.base import BasePage
        except ImportError:
            from base.base import BasePage
        self.driver = BasePage(self.driver_path, self.open_browser).driver
        return self.driver

    def _prepare_browser(self, username: str) -> None:
        try:
            from .pages.page_optional import PageOptional
        except ImportError:
            from pages.page_optional import PageOptional
        page = PageOptional(self.driver, self.ig_account, self.ig_pwd, self.logger)
        page.open_profile(username)
        page.close_login_prompt()
        page.scroll_window()
        page.clear_requests()
        page.click_display_button(username)

    def capture_first_page(self, username: str, timeout: int = 20) -> CapturedRequest:
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
        del days_limit
        username = str(ig_username_or_userid).strip()
        if not username:
            raise ValueError("ig_username_or_userid must not be empty")
        captured = self.capture_first_page(username)
        posts, cursor, has_next = parse_connection(captured.first_response)
        seen_posts = {post.get("post_id") or post.get("graphql_id") or post.get("shortcode") for post in posts}
        seen_cursors = {cursor} if cursor else set()
        page_count = 1
        while has_next and cursor and (max_pages is None or page_count < max_pages):
            if cursor in seen_cursors - {cursor}:
                self.logger.warning("Stopping pagination because cursor repeated")
                break
            seen_cursors.add(cursor)
            response_json = self._request_next_page(cursor)
            page_posts, next_cursor, has_next = parse_connection(response_json)
            for post in page_posts:
                identity = post.get("post_id") or post.get("graphql_id") or post.get("shortcode")
                if identity not in seen_posts:
                    posts.append(post)
                    seen_posts.add(identity)
            page_count += 1
            if display_progress:
                print(f"Collected {len(posts)} Instagram posts")
            if max_posts is not None and len(posts) >= max_posts:
                return posts[:max_posts]
            if not next_cursor or next_cursor in seen_cursors:
                self.logger.warning("Stopping pagination because end_cursor repeated or is empty")
                break
            cursor = next_cursor
        return posts[:max_posts] if max_posts is not None else posts

    def close(self) -> None:
        if self.driver is not None and self._owns_driver:
            self.driver.quit()
        self.session.close()

    quit = close
