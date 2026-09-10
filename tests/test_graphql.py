"""Sanitized unit tests for GraphQL parsing and Embed enrichment."""

import gzip
import json
import asyncio
from types import SimpleNamespace

import pytest

from graphql import (
    InstagramGraphQLError,
    capture_request,
    decode_response_body,
    extract_preloaded_posts,
    find_profile_document_request,
    is_target_graphql_request,
    next_payload,
    parse_connection,
    parse_form_payload,
    parse_preloaded_posts,
    redact_headers,
    parse_accessibility_date,
)
from models import CapturedRequest
from scraper import InstagramGraphqlScraper
from detail import merge_post_detail, parse_post_detail_html
from embed import InstagramEmbedClient, normalize_embed_html
from instagram_context_json import extract_context_json, normalize_media
import httpx


OPERATION = "PolarisLoggedOutDesktopWWWProfilePostsTabContentQuery_connection"


def make_response(posts=None, end_cursor="cursor-2", has_next_page=True, status_code=200, encoding=None):
    """Build a sanitized timeline response fixture."""
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
    """Build a sanitized Selenium Wire request fixture."""
    variables = json.dumps({"after": "initial", "first": 12, "id": "user-id"})
    body = f"variables={variables.replace(' ', '')}&doc_id=doc-1&fb_api_req_friendly_name={operation}"
    return SimpleNamespace(method=method, url=f"https://www.instagram.com{path}", body=body.encode(), headers={"X-Fb-Friendly-Name": operation, "Content-Type": "application/x-www-form-urlencoded", "Cookie": "secret"}, response=response or make_response())


def test_form_payload_and_variables_are_decoded():
    """Verify form fields and JSON variables are decoded separately."""
    payload, variables = parse_form_payload(b"variables=%7B%22after%22%3A%22c%22%2C%22first%22%3A12%7D&doc_id=doc")
    assert payload["doc_id"] == "doc"
    assert variables == {"after": "c", "first": 12}


def test_matcher_rejects_other_graphql_requests():
    """Verify the matcher rejects wrong paths, methods, and statuses."""
    assert is_target_graphql_request(make_request(response=make_response(), path="/api/other")) is False
    assert is_target_graphql_request(make_request(operation="OtherOperation")) is True
    assert is_target_graphql_request(make_request(response=make_response(status_code=500))) is False
    assert is_target_graphql_request(make_request(path="/api/graphql", method="GET")) is False


def test_capture_decodes_response_and_preserves_payload_without_secrets_in_debug_view():
    """Verify capture preserves request data while redacting debug headers."""
    request = make_request(response=make_response(encoding="gzip"))
    captured = capture_request(request, {"csrftoken": "secret-csrf", "sessionid": "secret-session"})
    assert captured.doc_id == "doc-1"
    assert captured.variables["first"] == 12
    assert captured.replay_headers["X-Csrftoken"] == "secret-csrf"
    assert redact_headers(captured.raw_headers)["Cookie"] == "<redacted>"


def test_parse_all_media_types_and_optional_fields():
    """Verify image, video, carousel, and missing optional fields normalize."""
    posts, _, _ = parse_connection(json.loads(make_response().body))
    assert [post["media_type"] for post in posts] == [1, 2, 8]
    assert posts[1]["is_video"] is True
    assert posts[2]["caption"] is None
    assert posts[2]["user_pk"] is None


def test_parse_counts_and_timestamp_without_guessing_from_accessibility_caption():
    """Verify exact metrics and numeric timestamps are parsed without guessing."""
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
    """Verify nested metric counts are discovered when present."""
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
    """Verify pagination uses page_info.end_cursor rather than edge cursors."""
    response = json.loads(make_response(end_cursor="page-info-cursor").body)
    _, cursor, _ = parse_connection(response)
    assert cursor == "page-info-cursor"
    assert cursor != "edge-3"


def test_next_payload_changes_only_after_cursor():
    """Verify next-page payload changes only the after cursor."""
    captured = capture_request(make_request(), {"csrftoken": "csrf"})
    payload = next_payload(captured, "next-cursor")
    assert json.loads(payload["variables"])["after"] == "next-cursor"
    assert payload["doc_id"] == captured.form_payload["doc_id"]


def test_schema_change_has_clear_error():
    """Verify missing timeline schema raises a readable error."""
    with pytest.raises(InstagramGraphQLError, match="polaris_ordered_timeline_connection"):
        parse_connection({"data": {"node": {}}})


def test_first_capture_is_not_replayed_and_duplicate_posts_are_removed():
    """Verify the first page is retained and duplicate posts are removed."""
    scraper = InstagramGraphqlScraper(driver=object())
    first = capture_request(make_request(), {"csrftoken": "csrf"})
    scraper.capture_first_page = lambda username: first
    scraper._request_next_page = lambda cursor: json.loads(make_response(posts=[{"pk": "1", "id": "POLARIS_1", "code": "image1"}, {"pk": "4", "id": "POLARIS_4", "code": "new4"}], end_cursor="next", has_next_page=False).body)
    posts = scraper.get_user_posts("demo", max_pages=2)
    assert [post["post_id"] for post in posts] == ["1", "2", "3", "4"]


def test_repeated_cursor_stops_pagination():
    """Verify repeated cursors stop pagination."""
    scraper = InstagramGraphqlScraper(driver=object())
    first = capture_request(make_request(response=make_response(end_cursor="same", has_next_page=True)), {"csrftoken": "csrf"})
    scraper.capture_first_page = lambda username: first
    calls = []
    scraper._request_next_page = lambda cursor: (calls.append(cursor) or json.loads(make_response(end_cursor="same", has_next_page=True).body))
    scraper.get_user_posts("demo", max_pages=5)
    assert calls == ["same"]


def test_empty_response_is_rejected():
    """Verify empty GraphQL responses are rejected."""
    with pytest.raises(InstagramGraphQLError, match="empty"):
        decode_response_body(b"", "identity")


def test_accessibility_caption_date_is_parsed_for_days_limit():
    """Verify Photo and Video accessibility dates are parsed."""
    assert parse_accessibility_date("Photo by demo on July 12, 2026.").isoformat() == "2026-07-12"
    assert parse_accessibility_date("Video by demo on June 16, 2026.").isoformat() == "2026-06-16"
    assert parse_accessibility_date("No publication date") is None


def test_days_limit_filters_old_posts_and_signals_pagination_stop():
    """Verify old dated posts are filtered and cutoff is reported."""
    from datetime import date

    posts = [
        {"post_id": "new", "accessibility_caption": "Photo by demo on July 12, 2026."},
        {"post_id": "old", "accessibility_caption": "Photo by demo on June 1, 2026."},
        {"post_id": "unknown", "accessibility_caption": None},
    ]
    filtered, reached_cutoff = InstagramGraphqlScraper._filter_posts_by_days(
        posts, date(2026, 7, 1)
    )
    assert [post["post_id"] for post in filtered] == ["new", "unknown"]
    assert reached_cutoff is True


def _preloaded_profile_html(shortcodes):
    """Build a sanitized profile document fixture with embedded preloaded posts."""
    edges = [
        {
            "node": {
                "pk": f"pk-{code}",
                "id": f"POLARIS_{code}",
                "code": code,
                "media_type": 1,
                "user": {"pk": "u1", "username": "demo", "id": "U1"},
            },
            "cursor": f"edge-{code}",
        }
        for code in shortcodes
    ]
    preloaded = {
        "require": [[
            "RelayPrefetchedStreamCache", "next", [{}, {
                "adp_PolarisLoggedOutDesktopWWWProfilePostsTabContentQueryRelayPreloader_x": {
                    "__bbox": {
                        "complete": True,
                        "result": {
                            "data": {
                                "xig_user_by_username": {
                                    "pk": "u1",
                                    "polaris_ordered_timeline_connection": {
                                        "edges": edges,
                                        "page_info": {"end_cursor": "c1", "has_next_page": True},
                                    },
                                }
                            }
                        },
                    }
                }
            }]
        ]]
    }
    script = json.dumps(preloaded)
    return f'<html><head><script type="application/json" data-sjs>{script}</script></head></html>'


def test_parse_preloaded_posts_extracts_embedded_timeline_edges():
    """Verify preloaded posts embedded in the profile document are parsed."""
    html = _preloaded_profile_html(["a1", "a2"])
    posts = parse_preloaded_posts(html)
    assert [post["shortcode"] for post in posts] == ["a1", "a2"]
    assert posts[0]["post_id"] == "pk-a1"


def test_parse_preloaded_posts_ignores_unrelated_scripts_and_dedupes():
    """Verify unrelated scripts are skipped and duplicate shortcodes are removed."""
    html = _preloaded_profile_html(["a1", "a1"]) + '<script type="application/json" data-sjs>{"other": true}</script>'
    posts = parse_preloaded_posts(html)
    assert [post["shortcode"] for post in posts] == ["a1"]


def test_find_profile_document_request_matches_html_get_by_path():
    """Verify the profile document request is matched by path, method, and content type."""
    html_response = SimpleNamespace(status_code=200, body=b"<html></html>", headers={"Content-Type": "text/html; charset=utf-8"})
    other_path = SimpleNamespace(method="GET", url="https://www.instagram.com/other/", response=html_response)
    wrong_method = SimpleNamespace(method="POST", url="https://www.instagram.com/demo/", response=html_response)
    match = SimpleNamespace(method="GET", url="https://www.instagram.com/demo/", response=html_response)
    assert find_profile_document_request([other_path, wrong_method, match], "demo") is match
    assert find_profile_document_request([other_path, wrong_method], "demo") is None


def test_extract_preloaded_posts_decodes_and_parses_document_response():
    """Verify extract_preloaded_posts decodes the response body and parses posts."""
    html = _preloaded_profile_html(["b1"])
    response = SimpleNamespace(status_code=200, body=html.encode(), headers={"Content-Type": "text/html"})
    request = SimpleNamespace(method="GET", url="https://www.instagram.com/demo/", response=response)
    posts = extract_preloaded_posts([request], "demo")
    assert [post["shortcode"] for post in posts] == ["b1"]


def test_extract_preloaded_posts_returns_empty_when_document_missing():
    """Verify a missing profile document request yields no preloaded posts."""
    assert extract_preloaded_posts([], "demo") == []


def test_merge_preloaded_posts_prepends_and_deduplicates_by_identity():
    """Verify preloaded posts are prepended ahead of paginated posts without duplicates."""
    scraper = InstagramGraphqlScraper(driver=object())
    scraper.preloaded_posts = [
        {"post_id": "p1", "shortcode": "s1"},
        {"post_id": "p2", "shortcode": "s2"},
    ]
    posts = scraper._merge_preloaded_posts([{"post_id": "p2", "shortcode": "s2"}, {"post_id": "p3", "shortcode": "s3"}])
    assert [post["post_id"] for post in posts] == ["p1", "p2", "p3"]


def test_post_detail_html_parses_exact_counts_and_timestamp():
    """Verify HTML detail exact counts and timestamps are normalized."""
    html = '<meta name="description" content="9,961 likes, 65 comments - demo on July 5, 2026">'
    html += '<time datetime="2026-07-05T12:34:56.000Z">July 5</time>'
    detail = parse_post_detail_html(html, "CODE")
    assert detail["like_count"] == 9961
    assert detail["comment_count"] == 65
    assert detail["taken_at_timestamp"] == 1783254896
    assert detail["published_at"] == "2026-07-05T12:34:56+00:00"
    assert detail["like_count_is_approximate"] is False


def test_post_detail_html_marks_rounded_counts_and_reads_video_views():
    """Verify rounded counts are marked approximate and views are parsed."""
    detail = parse_post_detail_html('<meta property="og:description" content="14K likes, 60 comments, 2.5K views">')
    assert detail["like_count"] == 14000
    assert detail["comment_count"] == 60
    assert detail["video_view_count"] == 2500
    assert detail["like_count_is_approximate"] is True


def test_post_embed_html_prefers_exact_anchor_counts_over_rounded_description():
    """Verify exact Embed anchor counts override rounded descriptions."""
    html = '<meta name="description" content="14K likes, 60 comments - demo on July 26, 2026">'
    html += '<a data-log-event="likeCountClick">7,320,872 likes</a>'
    html += '<a data-log-event="captionCommentsClick">View all 62,125 comments</a>'
    detail = parse_post_detail_html(html, "CODE")
    assert detail["like_count"] == 7320872
    assert detail["comment_count"] == 62125
    assert detail["like_count_is_approximate"] is False
    assert detail["detail_source"] == "post_embed_html"


def test_post_embed_html_parses_structured_exact_counts_when_anchor_variant_changes():
    """Verify structured Embed counts work across HTML anchor variants."""
    html = r'''<script>"edge_media_to_comment":{"count":62125},"edge_liked_by":{"count":7320872}</script>'''
    detail = parse_post_detail_html(html, "CODE")
    assert detail["like_count"] == 7320872
    assert detail["comment_count"] == 62125
    assert detail["detail_source"] == "post_embed_html"


def test_post_detail_html_missing_fields_are_none():
    """Verify missing detail fields remain None."""
    detail = parse_post_detail_html("<html><body>No metrics</body></html>")
    assert detail["like_count"] is None
    assert detail["comment_count"] is None
    assert detail["taken_at_timestamp"] is None
    assert detail["published_at"] is None


def test_post_detail_html_uses_date_only_fallback_without_fake_timestamp():
    """Verify date-only fallback does not fabricate a timestamp."""
    detail = parse_post_detail_html('<meta name="description" content="1,797 likes, 13 comments - demo on June 16, 2026">')
    assert detail["published_at"] == "2026-06-16"
    assert detail["taken_at_timestamp"] is None


def test_detail_merge_does_not_overwrite_existing_exact_values():
    """Verify detail merging preserves existing exact post values."""
    post = {"like_count": 10, "comment_count": None, "published_at": "2026-07-05"}
    merge_post_detail(post, {"like_count": 20, "comment_count": 4, "published_at": "2026-07-05T12:34:56+00:00"})
    assert post == {"like_count": 10, "comment_count": 4, "published_at": "2026-07-05"}


def _embed_html(shortcode, typename="GraphVideo"):
    """Build a sanitized contextJSON Embed fixture."""
    media = {
        "__typename": typename,
        "id": f"media-{shortcode}",
        "shortcode": shortcode,
        "edge_media_to_caption": {"edges": [{"node": {"text": "caption"}}]},
        "edge_liked_by": {"count": 12},
        "edge_media_to_comment": {"count": 3},
        "video_view_count": 99,
        "video_duration": 4.5,
        "display_url": "https://example.com/image.jpg",
        "video_url": "https://example.com/video.mp4",
        "product_type": "clips",
        "owner": {"id": "owner-1", "username": "demo"},
    }
    context = {"gql_data": {"shortcode_media": media}}
    return '"contextJSON":' + json.dumps(json.dumps(context))


def test_normalize_media_handles_video_image_and_carousel():
    """Verify normalized media types share a stable schema."""
    raw = extract_context_json(_embed_html("v"))["gql_data"]["shortcode_media"]
    video = normalize_media(raw)
    image = normalize_media(dict(raw, __typename="GraphImage"))
    carousel = normalize_media(dict(raw, __typename="GraphSidecar"))
    assert video["media_type"] == "video"
    assert video["video_view_count"] == 99
    assert image["media_type"] == "image"
    assert image["video_url"] is None
    assert carousel["media_type"] == "carousel"


def test_normalize_media_missing_metrics_and_video_fields_are_none():
    """Verify missing media metrics and video fields remain None."""
    result = normalize_media({"__typename": "GraphImage", "id": "1", "shortcode": "x"})
    assert result["like_count"] is None
    assert result["comment_count"] is None
    assert result["video_view_count"] is None
    assert result["video_duration"] is None
    assert result["video_url"] is None


def test_async_embed_batch_preserves_order_deduplicates_and_bounds_concurrency():
    """Verify async batches preserve order, deduplicate, and bound concurrency."""
    active = 0
    peak = 0
    calls = []

    async def handler(request):
        """Return a delayed sanitized response and track active requests."""
        nonlocal active, peak
        shortcode = request.url.path.split("/")[2]
        calls.append(shortcode)
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.001)
        active -= 1
        return httpx.Response(200, text=_embed_html(shortcode), request=request)

    async def run():
        """Run the bounded async client against a mock transport."""
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            async with InstagramEmbedClient(max_concurrency=2, client=http_client) as client:
                return await client.fetch_many(["a", "b", "a", "c"])

    results = asyncio.run(run())
    assert [item["shortcode"] for item in results] == ["a", "b", "a", "c"]
    assert calls == ["a", "b", "c"]
    assert peak <= 2


def test_async_embed_batch_failure_is_soft_and_keeps_order():
    """Verify one batch failure does not discard successful results."""
    async def handler(request):
        """Return one synthetic 404 and one successful response."""
        if request.url.path.split("/")[2] == "bad":
            return httpx.Response(404, request=request)
        return httpx.Response(200, text=_embed_html("good"), request=request)

    async def run():
        """Run failure-soft batch behavior against a mock transport."""
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            async with InstagramEmbedClient(max_concurrency=2, max_retries=1, client=http_client) as client:
                return await client.fetch_many(["good", "bad"])

    results = asyncio.run(run())
    assert results[0]["like_count"] == 12
    assert results[1]["shortcode"] == "bad"
    assert "error" in results[1]


def test_async_embed_retries_503_but_not_404():
    """Verify transient 503 retries while 404 fails immediately."""
    attempts = {"temporary": 0, "missing": 0}

    async def handler(request):
        """Return a transient failure, permanent failure, or success."""
        shortcode = request.url.path.split("/")[2]
        attempts[shortcode] += 1
        if shortcode == "temporary" and attempts[shortcode] == 1:
            return httpx.Response(503, request=request)
        if shortcode == "missing":
            return httpx.Response(404, request=request)
        return httpx.Response(200, text=_embed_html(shortcode), request=request)

    async def run():
        """Run retry behavior against a mock transport."""
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            async with InstagramEmbedClient(max_retries=1, client=http_client) as client:
                return await client.fetch_many(["temporary", "missing"])

    results = asyncio.run(run())
    assert results[0]["like_count"] == 12
    assert results[1]["error"] == "HTTP 404"
    assert attempts == {"temporary": 2, "missing": 1}


def test_context_json_null_uses_exact_html_metrics_fallback():
    """Verify contextJSON null falls back to exact HTML metrics."""
    html = '<script>contextJSON:null</script>'
    html += '<a data-log-event="likeCountClick">42,318 likes</a>'
    html += '<a data-log-event="captionCommentsClick">View all 190 comments</a>'
    detail = normalize_embed_html(html, "DasJmTqJ_QI")
    assert detail["shortcode"] == "DasJmTqJ_QI"
    assert detail["like_count"] == 42318
    assert detail["comment_count"] == 190
    assert detail["detail_source"] == "post_embed_html"


def test_merge_includes_video_detail_fields():
    """Verify video metrics and URLs are merged into existing posts."""
    post = {"shortcode": "video", "video_view_count": None, "video_duration": None, "video_url": None}
    merge_post_detail(post, {
        "video_view_count": 414739,
        "video_duration": 140.966,
        "video_url": "https://example.com/video.mp4",
    })
    assert post["video_view_count"] == 414739
    assert post["video_duration"] == 140.966
    assert post["video_url"] == "https://example.com/video.mp4"
