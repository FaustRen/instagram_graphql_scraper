"""Instagram timeline GraphQL request, response, and normalization helpers."""

import gzip
import json
import logging
import re
import zlib
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlparse

try:
    from .models import CapturedRequest
except ImportError:
    from models import CapturedRequest

OPERATION_NAME = "PolarisLoggedOutDesktopWWWProfilePostsTabContentQuery_connection"
GRAPHQL_PATH = "/api/graphql"
SENSITIVE_HEADERS = {"authorization", "cookie", "x-csrftoken", "x-fb-lsd"}
TRANSPORT_HEADERS = {
    "content-length", "host", "connection", "accept-encoding", ":authority",
    ":method", ":path", ":scheme", "cookie",
}


class InstagramGraphQLError(ValueError):
    """Raised when an Instagram GraphQL request or response is invalid."""

    pass


def _headers(request: Any) -> dict[str, str]:
    """Copy request headers into a regular string dictionary."""
    return {str(key): str(value) for key, value in getattr(request, "headers", {}).items()}


def _header(headers: Mapping[str, str], name: str) -> str | None:
    """Find a header case-insensitively."""
    name = name.lower()
    return next((value for key, value in headers.items() if key.lower() == name), None)


def parse_form_payload(body: bytes | str | None) -> tuple[dict[str, str], dict[str, Any]]:
    """Decode form-urlencoded request data and its JSON variables.

    Args:
        body: Raw request body as bytes or text.

    Returns:
        Complete form payload and decoded variables dictionary.
    """
    if body is None:
        raise InstagramGraphQLError("GraphQL request has an empty body")
    text = body.decode("utf-8") if isinstance(body, bytes) else body
    payload = dict(parse_qsl(text, keep_blank_values=True))
    if not payload:
        raise InstagramGraphQLError("GraphQL request body is not form-urlencoded")
    if "variables" not in payload:
        raise InstagramGraphQLError("GraphQL request payload has no variables")
    try:
        variables = json.loads(payload["variables"])
    except json.JSONDecodeError as error:
        raise InstagramGraphQLError("GraphQL variables are not valid JSON") from error
    if not isinstance(variables, dict):
        raise InstagramGraphQLError("GraphQL variables must be a JSON object")
    return payload, variables


def decode_response_body(body: bytes | str | None, encoding: str | None) -> dict[str, Any]:
    """Decode compressed response bytes and parse the JSON object."""
    if not body:
        raise InstagramGraphQLError("GraphQL response body is empty")
    raw = body.encode("utf-8") if isinstance(body, str) else body
    content_encoding = (encoding or "identity").lower().strip()
    try:
        if content_encoding not in {"identity", ""}:
            try:
                from seleniumwire.utils import decode
                raw = decode(raw, content_encoding)
                content_encoding = "identity"
            except (ImportError, OSError, ValueError):
                pass
        if content_encoding == "gzip":
            raw = gzip.decompress(raw)
        elif content_encoding == "deflate":
            raw = zlib.decompress(raw)
        elif content_encoding == "br":
            import brotli
            raw = brotli.decompress(raw)
        value = json.loads(raw.decode("utf-8"))
    except (ImportError, OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InstagramGraphQLError("GraphQL response is not valid JSON") from error
    if not isinstance(value, dict):
        raise InstagramGraphQLError("GraphQL response JSON must be an object")
    return value


def request_debug_summary(requests: Any) -> str:
    """Return safe request diagnostics without exposing secrets or bodies."""
    summaries = []
    for request in requests:
        parsed_url = urlparse(str(getattr(request, "url", "")))
        if parsed_url.path != GRAPHQL_PATH:
            continue
        response = getattr(request, "response", None)
        headers = _headers(request)
        operation = _header(headers, "x-fb-friendly-name")
        status = getattr(response, "status_code", "no-response") if response else "no-response"
        encoding = _header(getattr(response, "headers", {}), "content-encoding") if response else None
        schema = False
        if response:
            try:
                schema = _connection(decode_response_body(response.body, encoding)) is not None
            except Exception:
                pass
        summaries.append(f"status={status}, operation={operation or '<none>'}, encoding={encoding or 'identity'}, timeline_schema={schema}")
    return f"graphql_requests={len(summaries)} [{'; '.join(summaries[-10:])}]"


def _connection(response_json: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the profile timeline connection from a GraphQL response."""
    try:
        connection = response_json["data"]["node"]["polaris_ordered_timeline_connection"]
        edges = connection["edges"]
        page_info = connection["page_info"]
    except (KeyError, TypeError) as error:
        raise InstagramGraphQLError(
            "GraphQL response missing data.node.polaris_ordered_timeline_connection"
        ) from error
    if not isinstance(connection, Mapping) or not isinstance(edges, list) or not isinstance(page_info, Mapping):
        raise InstagramGraphQLError("Instagram timeline connection has an invalid schema")
    return connection


def parse_connection(response_json: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str | None, bool]:
    """Parse timeline edges and return posts, end cursor, and next-page state."""
    connection = _connection(response_json)
    posts = [normalize_edge(edge) for edge in connection["edges"]]
    page_info = connection["page_info"]
    return posts, page_info.get("end_cursor"), bool(page_info.get("has_next_page", False))


def normalize_edge(edge: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one timeline edge into the public post schema."""
    node = edge.get("node") if isinstance(edge, Mapping) else None
    if not isinstance(node, Mapping):
        raise InstagramGraphQLError("Instagram timeline edge has no node")
    shortcode = node.get("code")
    user_value = node.get("user")
    user = user_value if isinstance(user_value, Mapping) else {}
    taken_at_timestamp = _first_value(
        node,
        "taken_at_timestamp",
        "taken_at",
        "timestamp",
        "created_time",
    )
    if not isinstance(taken_at_timestamp, (int, float)) or isinstance(taken_at_timestamp, bool):
        taken_at_timestamp = None
    return {
        "post_id": node.get("pk"),
        "graphql_id": node.get("id"),
        "shortcode": shortcode,
        "post_url": f"https://www.instagram.com/p/{shortcode}/" if shortcode else None,
        "caption": (node.get("caption") or {}).get("text") if isinstance(node.get("caption"), Mapping) else None,
        "accessibility_caption": node.get("accessibility_caption"),
        "typename": node.get("__typename"),
        "media_type": node.get("media_type"),
        "product_type": node.get("product_type"),
        "is_video": node.get("media_type") == 2,
        "display_uri": node.get("display_uri"),
        "carousel_media_count": node.get("carousel_media_count"),
        "username": user.get("username"),
        "user_pk": user.get("pk"),
        "user_graphql_id": user.get("id"),
        "edge_cursor": edge.get("cursor"),
        "like_count": _count_value(node, "like_count", "likes", "edge_media_preview_like"),
        "comment_count": _count_value(node, "comment_count", "comments", "edge_media_to_comment"),
        "video_view_count": _count_value(node, "video_view_count", "view_count", "play_count", "video_play_count"),
        "taken_at_timestamp": taken_at_timestamp,
        "published_at": (
            datetime.fromtimestamp(taken_at_timestamp, tz=timezone.utc).isoformat()
            if taken_at_timestamp is not None else None
        ),
    }


def parse_accessibility_date(value: str | None):
    """Parse a date from Instagram's Photo/Video accessibility caption."""
    if not isinstance(value, str):
        return None
    match = re.search(
        r"\b(?:Photo|Video) by .*? on "
        r"(January|February|March|April|May|June|July|August|September|October|November|December) "
        r"(\d{1,2}), (\d{4})\b",
        value,
        re.IGNORECASE,
    )
    if not match:
        return None
    try:
        return datetime.strptime(" ".join(match.groups()), "%B %d %Y").date()
    except ValueError:
        return None


def _first_value(value: Mapping[str, Any], *keys: str) -> Any:
    """Return the first non-null value found under the supplied keys."""
    for key in keys:
        if key in value and value[key] is not None:
            return value[key]
    return None


def _count_value(node: Mapping[str, Any], *keys: str) -> Any:
    """Find a direct or nested metric count in a media node."""
    value = _first_value(node, *keys)
    if value is None:
        value = _find_nested_value(node, set(keys))
    if isinstance(value, Mapping):
        value = value.get("count")
    return value


def _find_nested_value(value: Any, keys: set[str]) -> Any:
    """Recursively find the first non-null value for any target key."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in keys and child is not None:
                return child
            nested = _find_nested_value(child, keys)
            if nested is not None:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = _find_nested_value(child, keys)
            if nested is not None:
                return nested
    return None


def replay_headers(raw_headers: Mapping[str, str], cookies: Mapping[str, str]) -> dict[str, str]:
    """Build headers safe for replaying a captured GraphQL request."""
    csrf = cookies.get("csrftoken")
    result = {}
    for key, value in raw_headers.items():
        lower_key = key.lower()
        if lower_key in TRANSPORT_HEADERS:
            continue
        result[key] = value
    if csrf:
        result["X-Csrftoken"] = csrf
    return result


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Redact cookies, tokens, and authorization values from headers."""
    return {
        key: "<redacted>" if key.lower() in SENSITIVE_HEADERS or re.search("token|cookie|authorization", key, re.I) else value
        for key, value in headers.items()
    }


def is_target_graphql_request(request: Any, logger: logging.Logger | None = None) -> bool:
    """Check whether a Selenium Wire request is the profile timeline query."""
    headers = _headers(request)
    parsed_url = urlparse(str(getattr(request, "url", "")))
    if str(getattr(request, "method", "")).upper() != "POST" or parsed_url.path != GRAPHQL_PATH:
        return False
    response = getattr(request, "response", None)
    if response is None or not 200 <= int(getattr(response, "status_code", 0)) < 300:
        return False
    try:
        payload, _ = parse_form_payload(getattr(request, "body", None))
        operation = _header(headers, "x-fb-friendly-name") or payload.get("fb_api_req_friendly_name")
        response_json = decode_response_body(getattr(response, "body", None), _header(response.headers, "content-encoding"))
        _connection(response_json)
    except InstagramGraphQLError:
        return False
    if operation == OPERATION_NAME:
        return True
    if logger:
        logger.warning("Accepted GraphQL request with schema match but unexpected operation name")
    return True


def capture_request(request: Any, cookies: Mapping[str, str]) -> CapturedRequest:
    """Capture a validated browser GraphQL request and its first response."""
    if not is_target_graphql_request(request):
        raise InstagramGraphQLError("Request does not match the Instagram profile posts GraphQL request")
    raw_headers = _headers(request)
    form_payload, variables = parse_form_payload(request.body)
    response = request.response
    response_json = decode_response_body(response.body, _header(response.headers, "content-encoding"))
    posts, end_cursor, has_next_page = parse_connection(response_json)
    operation = _header(raw_headers, "x-fb-friendly-name") or form_payload.get("fb_api_req_friendly_name")
    return CapturedRequest(
        url=request.url,
        operation_name=operation,
        raw_headers=raw_headers,
        replay_headers=replay_headers(raw_headers, cookies),
        cookies=dict(cookies),
        form_payload=form_payload,
        variables=variables,
        doc_id=form_payload.get("doc_id"),
        first_response=response_json,
        end_cursor=end_cursor,
        has_next_page=has_next_page,
    )


def next_payload(captured: CapturedRequest, cursor: str) -> dict[str, str]:
    """Create the next-page payload by replacing only the after cursor."""
    payload = dict(captured.form_payload)
    variables = dict(captured.variables)
    variables["after"] = cursor
    payload["variables"] = json.dumps(variables, separators=(",", ":"))
    return payload


def log_capture(logger: logging.Logger, captured: CapturedRequest) -> None:
    """Log safe metadata for a captured request."""
    logger.debug("Captured Instagram GraphQL request operation=%s doc_id=%s headers=%s", captured.operation_name, captured.doc_id, redact_headers(captured.raw_headers))
