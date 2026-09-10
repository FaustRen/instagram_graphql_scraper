# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-09-10

### Added
- Extract posts preloaded in the initial profile page HTML (before the GraphQL
  pagination request fires) and merge them ahead of the paginated timeline,
  recovering posts that were previously missing from the front of the feed.
- Unit tests covering preloaded-post parsing, document request matching, and
  merge/deduplication behavior.

### Fixed
- Preserve the original "response body is empty" error message after the
  response-decoding helper was refactored to share logic with HTML decoding.

## [0.1.0] - 2026-09-04

### Added
- Initial Instagram GraphQL scraper: browser capture, GraphQL request matcher, response parser, and pagination.
- Anonymous unit tests for parsing, matching, deduplication, and stop conditions.
- Manual (non-CI) browser integration entry point.
