from __future__ import annotations

import argparse
import json
import re
from typing import Any

import requests


CONTEXT_JSON_KEY = re.compile(r'"contextJSON"\s*:\s*')


def extract_context_json(html: str) -> dict[str, Any]:
    """Extract and decode Instagram's string-encoded contextJSON object."""
    decoder = json.JSONDecoder()

    for match in CONTEXT_JSON_KEY.finditer(html):
        try:
            # First decode: JSON string literal -> Python str.
            encoded_context, _ = decoder.raw_decode(html, match.end())
            if not isinstance(encoded_context, str):
                continue

            # Second decode: JSON document inside that str -> Python object.
            context = json.loads(encoded_context)
            if isinstance(context, dict):
                return context
        except json.JSONDecodeError:
            continue

    raise ValueError(
        "找不到可解析的 contextJSON；可能拿到登入／錯誤頁，"
        "或 Instagram 已更改頁面格式。"
    )


def fetch_context_json(url: str, timeout: float = 30) -> dict[str, Any]:
    # The tested response worked with requests' default User-Agent.
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return extract_context_json(response.text)


def get_media(context_json: dict[str, Any]) -> dict[str, Any]:
    media = context_json.get("gql_data", {}).get("shortcode_media")
    if not isinstance(media, dict):
        raise KeyError("contextJSON 中找不到 gql_data.shortcode_media")
    return media


def get_caption(media: dict[str, Any]) -> str | None:
    edges = media.get("edge_media_to_caption", {}).get("edges", [])
    for edge in edges:
        text = edge.get("node", {}).get("text")
        if isinstance(text, str):
            return text
    return None


def normalize_media(media: dict[str, Any]) -> dict[str, Any]:
    """Convert shortcode_media into the stable single-post result schema."""
    typename = media.get("__typename")
    media_type_map = {
        "GraphImage": "image",
        "GraphVideo": "video",
        "GraphSidecar": "carousel",
    }
    media_type = media_type_map.get(typename) if isinstance(typename, str) else None
    owner_value = media.get("owner")
    owner: dict[str, Any] = owner_value if isinstance(owner_value, dict) else {}
    is_video = media_type == "video"
    liked_by = media.get("edge_liked_by")
    comments = media.get("edge_media_to_comment")
    return {
        "post_id": media.get("id"),
        "shortcode": media.get("shortcode"),
        "post_url": f"https://www.instagram.com/p/{media.get('shortcode')}/" if media.get("shortcode") else None,
        "caption": get_caption(media),
        "media_type": media_type,
        "product_type": media.get("product_type"),
        "is_video": is_video,
        "like_count": liked_by.get("count") if isinstance(liked_by, dict) else None,
        "comment_count": comments.get("count") if isinstance(comments, dict) else None,
        "video_view_count": media.get("video_view_count") if is_video else None,
        "video_duration": media.get("video_duration") if is_video else None,
        "display_uri": media.get("display_url"),
        "video_url": media.get("video_url") if is_video else None,
        "username": owner.get("username"),
        "user_pk": owner.get("id"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Instagram /embed/ or /embed/captioned/ URL")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Pretty-print the complete decoded contextJSON",
    )
    args = parser.parse_args()

    context_json = fetch_context_json(args.url)

    if args.full:
        print(json.dumps(context_json, ensure_ascii=False, indent=2))
        return

    media = get_media(context_json)
    owner = media.get("owner") if isinstance(media.get("owner"), dict) else {}
    summary = normalize_media(media)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
