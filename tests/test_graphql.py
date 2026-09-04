import gzip
import json
from types import SimpleNamespace

import pytest

from graphql import (
    InstagramGraphQLError,
    capture_request,
    decode_response_body,
    is_target_graphql_request,
    next_payload,
    parse_connection,
    parse_form_payload,
    redact_headers,
)
from models import CapturedRequest
from scraper import InstagramGraphqlScraper


OPERATION = "PolarisLoggedOutDesktopWWWProfilePostsTabContentQuery_connection"


def make_response(posts=None, end_cursor="cursor-2", has_next_page=True, status_code=200, encoding=None):
    posts = posts or [
        {"pk": "1", "id": "POLARIS_1", "code": "image1", "media_type": 1, "user": {"pk": "u1", "username": "demo", "id": "U1"}},
        {"pk": "2", "id": "POLARIS_2", "code": "video2", "media_type": 2, "product_type": "clips", "user": {"username": "demo"}},
        {"pk": "3", "id": "POLARIS_3", "code": "carousel3", "media_type": 8, "carousel_media_count": 3},
    ]
    body = json.dumps({"data": {"node": {"polaris_ordered_timeline_connection": {"edges": [{"node": post, "cursor": f"edge-{post['pk']}"} for post in posts], "page_info": {"end_cursor": end_cursor, "has_next_page": has_next_page}}}}}).encode()
    if encoding == "gzip":
        body = gzip.compress(body)
    return SimpleNamespace(status_code=status_code, body=body, headers={"Content-Encoding": encoding or "identity"})


def make_request(operation=OPERATION, response=None, path="/api/graphql", method="POST"):
    variables = json.dumps({"after": "initial", "first": 12, "id": "user-id"})
    body = f"variables={variables.replace(' ', '')}&doc_id=doc-1&fb_api_req_friendly_name={operation}"
    return SimpleNamespace(method=method, url=f"https://www.instagram.com{path}", body=body.encode(), headers={"X-Fb-Friendly-Name": operation, "Content-Type": "application/x-www-form-urlencoded", "Cookie": "secret"}, response=response or make_response())


def test_form_payload_and_variables_are_decoded():
    payload, variables = parse_form_payload(b"variables=%7B%22after%22%3A%22c%22%2C%22first%22%3A12%7D&doc_id=doc")
    assert payload["doc_id"] == "doc"
    assert variables == {"after": "c", "first": 12}


def test_matcher_rejects_other_graphql_requests():
    assert is_target_graphql_request(make_request(response=make_response(), path="/api/other")) is False
    assert is_target_graphql_request(make_request(operation="OtherOperation")) is True
    assert is_target_graphql_request(make_request(response=make_response(status_code=500))) is False
    assert is_target_graphql_request(make_request(path="/api/graphql", method="GET")) is False


def test_capture_decodes_response_and_preserves_payload_without_secrets_in_debug_view():
    request = make_request(response=make_response(encoding="gzip"))
    captured = capture_request(request, {"csrftoken": "secret-csrf", "sessionid": "secret-session"})
    assert captured.doc_id == "doc-1"
    assert captured.variables["first"] == 12
    assert captured.replay_headers["X-Csrftoken"] == "secret-csrf"
    assert redact_headers(captured.raw_headers)["Cookie"] == "<redacted>"


def test_parse_all_media_types_and_optional_fields():
    posts, _, _ = parse_connection(json.loads(make_response().body))
    assert [post["media_type"] for post in posts] == [1, 2, 8]
    assert posts[1]["is_video"] is True
    assert posts[2]["caption"] is None
    assert posts[2]["user_pk"] is None


def test_parse_counts_and_timestamp_without_guessing_from_accessibility_caption():
    response = json.loads(make_response(posts=[{
        "pk": "1",
        "id": "POLARIS_1",
        "code": "video1",
        "media_type": 2,
        "like_count": 11,
        "edge_media_to_comment": {"count": 4},
        "video_view_count": 99,
        "taken_at_timestamp": 1785067200,
        "accessibility_caption": "Video posted yesterday",
    }]).body)
    posts, _, _ = parse_connection(response)
    assert posts[0]["like_count"] == 11
    assert posts[0]["comment_count"] == 4
    assert posts[0]["video_view_count"] == 99
    assert posts[0]["taken_at_timestamp"] == 1785067200
    assert posts[0]["published_at"].startswith("2026-07-26T")


def test_parse_nested_metrics_when_timeline_returns_them():
    response = json.loads(make_response(posts=[{
        "pk": "1",
        "id": "POLARIS_1",
        "code": "post1",
        "media_type": 1,
        "media": {
            "edge_media_preview_like": {"count": 12},
            "edge_media_to_comment": {"count": 3},
        },
    }]).body)
    posts, _, _ = parse_connection(response)
    assert posts[0]["like_count"] == 12
    assert posts[0]["comment_count"] == 3


def test_end_cursor_comes_from_page_info():
    response = json.loads(make_response(end_cursor="page-info-cursor").body)
    _, cursor, _ = parse_connection(response)
    assert cursor == "page-info-cursor"
    assert cursor != "edge-3"


def test_next_payload_changes_only_after_cursor():
    captured = capture_request(make_request(), {"csrftoken": "csrf"})
    payload = next_payload(captured, "next-cursor")
    assert json.loads(payload["variables"])["after"] == "next-cursor"
    assert payload["doc_id"] == captured.form_payload["doc_id"]


def test_schema_change_has_clear_error():
    with pytest.raises(InstagramGraphQLError, match="polaris_ordered_timeline_connection"):
        parse_connection({"data": {"node": {}}})


def test_first_capture_is_not_replayed_and_duplicate_posts_are_removed():
    scraper = InstagramGraphqlScraper(driver=object())
    first = capture_request(make_request(), {"csrftoken": "csrf"})
    scraper.capture_first_page = lambda username: first
    scraper._request_next_page = lambda cursor: json.loads(make_response(posts=[{"pk": "1", "id": "POLARIS_1", "code": "image1"}, {"pk": "4", "id": "POLARIS_4", "code": "new4"}], end_cursor="next", has_next_page=False).body)
    posts = scraper.get_user_posts("demo", max_pages=2)
    assert [post["post_id"] for post in posts] == ["1", "2", "3", "4"]


def test_repeated_cursor_stops_pagination():
    scraper = InstagramGraphqlScraper(driver=object())
    first = capture_request(make_request(response=make_response(end_cursor="same", has_next_page=True)), {"csrftoken": "csrf"})
    scraper.capture_first_page = lambda username: first
    calls = []
    scraper._request_next_page = lambda cursor: (calls.append(cursor) or json.loads(make_response(end_cursor="same", has_next_page=True).body))
    scraper.get_user_posts("demo", max_pages=5)
    assert calls == ["same"]


def test_empty_response_is_rejected():
    with pytest.raises(InstagramGraphQLError, match="empty"):
        decode_response_body(b"", "identity")
