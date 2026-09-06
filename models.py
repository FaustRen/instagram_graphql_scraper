"""Data models shared by the Instagram scraper pipeline."""

from dataclasses import dataclass
from typing import Any


@dataclass
class CapturedRequest:
    """Store a browser-captured GraphQL request and its first response."""

    url: str
    operation_name: str | None
    raw_headers: dict[str, str]
    replay_headers: dict[str, str]
    cookies: dict[str, str]
    form_payload: dict[str, str]
    variables: dict[str, Any]
    doc_id: str | None
    first_response: dict[str, Any]
    end_cursor: str | None
    has_next_page: bool
