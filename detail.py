"""Instagram post HTML detail parsing and fail-soft merge helpers."""

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any


class PostDetailParser(HTMLParser):
    """Collect metadata, timestamps, and exact count anchors from post HTML."""

    def __init__(self):
        """Initialize parser state for one Instagram detail response."""
        super().__init__()
        self.meta: dict[str, str] = {}
        self.times: list[str] = []
        self._count_anchor: str | None = None
        self._count_text: list[str] = []
        self.exact_counts: dict[str, int] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Capture relevant metadata from an opening HTML tag.

        Args:
            tag: HTML tag name.
            attrs: Parsed HTML attributes.
        """
        attributes = dict(attrs)
        if tag == "meta":
            key = attributes.get("name") or attributes.get("property")
            content = attributes.get("content")
            if key and content and key in {"description", "og:description"}:
                self.meta[key] = content
        elif tag == "time" and attributes.get("datetime"):
            datetime_value = attributes.get("datetime")
            if datetime_value:
                self.times.append(datetime_value)
        elif tag == "a":
            event = attributes.get("data-log-event")
            if event in {"likeCountClick", "captionCommentsClick"}:
                self._count_anchor = event
                self._count_text = []

    def handle_data(self, data: str) -> None:
        """Collect text belonging to an exact count anchor."""
        if self._count_anchor:
            self._count_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        """Finalize an exact count when its anchor closes."""
        if tag == "a" and self._count_anchor:
            text = "".join(self._count_text)
            match = re.search(r"\d[\d,\s]*", text.strip())
            if match:
                count = int(re.sub(r"[^\d]", "", match.group()))
                field = "like_count" if self._count_anchor == "likeCountClick" else "comment_count"
                self.exact_counts[field] = count
            self._count_anchor = None
            self._count_text = []


def _parse_count(description: str, label: str) -> tuple[int | None, bool]:
    """Parse a displayed count and report whether it uses a rounded suffix.

    Args:
        description: Post description metadata text.
        label: Metric label such as ``likes`` or ``comments``.

    Returns:
        A tuple containing the parsed count and an approximation flag.
    """
    match = re.search(rf"([\d,.]+)\s*([KMB])?\s+{label}\b", description, re.IGNORECASE)
    if not match:
        return None, False
    number = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").upper()
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix]
    return int(number * multiplier), bool(suffix)


def _parse_embedded_count(html: str, field_name: str) -> int | None:
    """Extract an exact count from embedded Instagram structured data."""
    pattern = rf'\\?"{field_name}\\?"\s*:\s*\\?\{{\\?"count\\?"\s*:\s*(\d+)'
    match = re.search(pattern, html)
    return int(match.group(1)) if match else None


def _parse_datetime(value: str | None) -> tuple[int | None, str | None]:
    """Convert an ISO timestamp to UTC Unix and ISO-8601 values."""
    if not value:
        return None, None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    return int(parsed.timestamp()), parsed.isoformat()


def _parse_description_date(description: str) -> str | None:
    """Extract a date-only fallback from an English description."""
    match = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})\b", description)
    if not match:
        return None
    try:
        return datetime.strptime(" ".join(match.groups()), "%B %d %Y").date().isoformat()
    except ValueError:
        return None


def parse_post_detail_html(html: str, shortcode: str | None = None) -> dict[str, Any]:
    """Normalize metrics and publication metadata from post HTML.

    Args:
        html: HTML returned by an Instagram post or Embed page.
        shortcode: Optional shortcode associated with the response.

    Returns:
        Normalized detail fields with ``None`` for unavailable values.
    """
    parser = PostDetailParser()
    parser.feed(html)
    description = parser.meta.get("description") or parser.meta.get("og:description") or ""
    embedded_like_count = _parse_embedded_count(html, "edge_liked_by")
    embedded_comment_count = _parse_embedded_count(html, "edge_media_to_comment")
    metadata_like_count, likes_approximate = _parse_count(description, "likes")
    metadata_comment_count, comments_approximate = _parse_count(description, "comments")
    like_count = embedded_like_count
    comment_count = embedded_comment_count
    if like_count is None:
        like_count = metadata_like_count
    else:
        likes_approximate = False
    if comment_count is None:
        comment_count = metadata_comment_count
    else:
        comments_approximate = False
    used_anchor_count = False
    if like_count is None and "like_count" in parser.exact_counts:
        like_count, likes_approximate = parser.exact_counts["like_count"], False
        used_anchor_count = True
    if comment_count is None and "comment_count" in parser.exact_counts:
        comment_count, comments_approximate = parser.exact_counts["comment_count"], False
        used_anchor_count = True
    video_view_count, _ = _parse_count(description, "views")
    if video_view_count is None:
        video_view_count, _ = _parse_count(description, "plays")
    timestamp, published_at = _parse_datetime(parser.times[0] if parser.times else None)
    if published_at is None:
        published_at = _parse_description_date(description)
    return {
        "shortcode": shortcode,
        "like_count": like_count,
        "comment_count": comment_count,
        "video_view_count": video_view_count,
        "taken_at_timestamp": timestamp,
        "published_at": published_at,
        "like_count_is_approximate": likes_approximate,
        "comment_count_is_approximate": comments_approximate,
        "detail_source": "post_embed_html" if used_anchor_count or embedded_like_count is not None or embedded_comment_count is not None else ("post_html_metadata" if description or parser.times else None),
        "detail_shortcode": shortcode,
    }


def merge_post_detail(post: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    """Merge missing detail fields without replacing existing post values.

    Args:
        post: Existing normalized timeline post.
        detail: Normalized Embed or detail response.

    Returns:
        The updated post dictionary.
    """
    for field in (
        "like_count", "comment_count", "video_view_count", "video_duration",
        "video_url", "display_uri", "product_type", "media_type", "is_video",
        "taken_at_timestamp", "published_at",
    ):
        if post.get(field) is None and detail.get(field) is not None:
            post[field] = detail[field]
    for field in ("like_count_is_approximate", "comment_count_is_approximate", "detail_source"):
        if detail.get(field) is not None:
            post[field] = detail[field]
    return post
