# Sample Output

Two runs against the same public profile (`1989ivyshao`), using the two usage patterns documented in [README.md](../README.md). Long CDN query strings are truncated with `...` for readability; the JSON structure and field names are otherwise unmodified.

## Run 1 — `max_pages=2, max_posts=24` (list-repr output)

```python
from instagram_graphql_scraper import InstagramGraphqlScraper

driver_path = "/path/to/chromedriver"
scraper = InstagramGraphqlScraper(driver_path=driver_path, open_browser=False)
try:
    posts = scraper.get_user_posts("1989ivyshao", max_pages=2, max_posts=24)
finally:
    scraper.close()
```

First 3 of 24 returned posts:

```python
[{'post_id': '3949676966589363019',
  'graphql_id': 'POLARIS_3949676966589363019',
  'shortcode': 'DbQEkZbGfNL',
  'post_url': 'https://www.instagram.com/p/DbQEkZbGfNL/',
  'caption': '突然發現IG又改版驚呼連連的我...',
  'accessibility_caption': 'Photo by 邵雨薇IvyShao on July 26, 2026.',
  'typename': 'XIGPolarisCarouselMedia',
  'media_type': 8,
  'product_type': 'carousel_container',
  'is_video': False,
  'display_uri': 'https://scontent.cdninstagram.com/v/t51.82787-15/753990711_18607453426018122_467452374283430873_n.jpg?...',
  'carousel_media_count': 20,
  'username': '1989ivyshao',
  'user_pk': '370962121',
  'user_graphql_id': '17841400543635796',
  'edge_cursor': 'AQHTN9xdTop1rHuIV1i-DlyUuhYCZ54tN12tb9ppfoZ4Tm9cG0jrB1nnrfXAqxdOY6VQXI_2F7EoxQbCqeFwSV_beQ',
  'like_count': 14437,
  'comment_count': 60,
  'video_view_count': None,
  'taken_at_timestamp': None,
  'published_at': '2026-07-26',
  'detail_source': 'post_embed_html'},
 {'post_id': '3947450270221964863',
  'graphql_id': 'POLARIS_3947450270221964863',
  'shortcode': 'DbIKRs1GZY_',
  'post_url': 'https://www.instagram.com/p/DbIKRs1GZY_/',
  'caption': '穿上它，連身體都鬆了一口氣...',
  'accessibility_caption': 'Photo by 邵雨薇IvyShao on July 23, 2026.',
  'typename': 'XIGPolarisCarouselMedia',
  'media_type': 8,
  'product_type': 'carousel_container',
  'is_video': False,
  'display_uri': 'https://scontent.cdninstagram.com/v/t51.82787-15/753738990_18606456187018122_8138225491780542893_n.jpg?...',
  'carousel_media_count': 3,
  'username': '1989ivyshao',
  'user_pk': '370962121',
  'user_graphql_id': '17841400543635796',
  'edge_cursor': 'AQHTVUVKLjumCRDQ7CWYt2dH4HtqId8J6QNxH8of3-R3dipGzOyohdmXpvl3BmwMDXtK2tgu83MAb0MtPJL3v6pR6Q',
  'like_count': 16844,
  'comment_count': 50,
  'video_view_count': None,
  'taken_at_timestamp': None,
  'published_at': '2026-07-23',
  'detail_source': 'post_embed_html'},
 {'post_id': '3944524103676449812',
  'graphql_id': 'POLARIS_3944524103676449812',
  'shortcode': 'Da9w8X3mdQU',
  'post_url': 'https://www.instagram.com/p/Da9w8X3mdQU/',
  'caption': 'I need 😺',
  'accessibility_caption': 'Photo by 邵雨薇IvyShao on July 18, 2026.',
  'typename': 'XIGPolarisCarouselMedia',
  'media_type': 8,
  'product_type': 'carousel_container',
  'is_video': False,
  'display_uri': 'https://scontent.cdninstagram.com/v/t51.82787-15/749892035_18605205028018122_1498735102623456007_n.jpg?...',
  'carousel_media_count': 3,
  'username': '1989ivyshao',
  'user_pk': '370962121',
  'user_graphql_id': '17841400543635796',
  'edge_cursor': 'AQHT7ewVphJMUqZ-CH-wY6AMotb8hIdbiCAlZmesmyAq1ke2ERyV9mPL7wY7gBQX5KM_hcNprpTv55B-y4o975497w',
  'like_count': 18405,
  'comment_count': 69,
  'video_view_count': None,
  'taken_at_timestamp': 1784443940,
  'published_at': '2026-07-19T06:52:20+00:00',
  'detail_source': 'post_embed_html'},
 # ... 21 more posts, same schema, down to 2026-05-06
]
```

A post where enrichment found no usable data at all (all detail fields remain `None`, no `detail_source` key):

```python
{'post_id': '3934585244703755993',
 'graphql_id': 'POLARIS_3934585244703755993',
 'shortcode': 'DaadG8JD47Z',
 'post_url': 'https://www.instagram.com/p/DaadG8JD47Z/',
 'caption': '四點要看好期待的一場世足\n晚安',
 'accessibility_caption': 'Photo by 邵雨薇IvyShao on July 05, 2026. 可能是一或多人、瀏海和文字的自拍照.',
 'typename': 'XIGPolarisImageMedia',
 'media_type': 1,
 'product_type': 'feed',
 'is_video': False,
 'display_uri': 'https://scontent.cdninstagram.com/v/t51.82787-15/736456388_18601042336018122_4462052081569775015_n.jpg?...',
 'carousel_media_count': None,
 'username': '1989ivyshao',
 'user_pk': '370962121',
 'user_graphql_id': '17841400543635796',
 'edge_cursor': 'AQHTX0IR9dpy6ds8jIqdGQhuuq0CuBhhpioynnxT8Mpbn1kECa3HQZNHNnjRN-tSew0ryAk7abrdQUrwV8FAwN-iqg',
 'like_count': None,
 'comment_count': None,
 'video_view_count': None,
 'taken_at_timestamp': None,
 'published_at': None}
```

A video post, with `video_duration`/`video_url` present because enrichment succeeded:

```python
{'post_id': '3920731336125719587',
 'shortcode': 'DZpPGCVhCQj',
 'typename': 'XIGPolarisVideoMedia',
 'media_type': 2,
 'product_type': 'clips',
 'is_video': True,
 'like_count': 1800,
 'comment_count': 13,
 'video_view_count': 8142,
 'taken_at_timestamp': None,
 'published_at': '2026-06-16',
 'video_duration': 24.3,
 'video_url': 'https://instagram.fkhh1-2.fna.fbcdn.net/o1/v/t2/f2/m86/AQPjzbmXbT1RXZDmiz67BBdbmp7EpO3-9QnbQXWnGue3GwrIPcvjRNy20j89uvpiZ_lVk3w__nGtW_BOceKEZc5M3JNOywXfPFNMNro.mp4?...',
 'detail_source': 'post_embed_html'}
```

## Run 2 — same profile and parameters, printed with `pprint` (alphabetized keys)

The second run used the identical usage pattern but printed the result with `pprint`, which sorts dict keys alphabetically — the field set and values are otherwise the same schema.

```python
[{'accessibility_caption': 'Photo by 邵雨薇IvyShao on July 26, 2026.',
  'caption': '突然發現IG又改版驚呼連連的我...',
  'carousel_media_count': 20,
  'comment_count': 60,
  'detail_source': 'post_embed_html',
  'display_uri': 'https://scontent.cdninstagram.com/v/t51.82787-15/753990711_18607453426018122_467452374283430873_n.jpg?...',
  'edge_cursor': 'AQHTyRW9su5dOZ5ClyAhcWt-Y6G69wju1g_CKotAajn8gXcJbzXglajgC9C-i0LaPESx97Nkh32FdbFKLDmAA3qzTw',
  'graphql_id': 'POLARIS_3949676966589363019',
  'is_video': False,
  'like_count': 14437,
  'media_type': 8,
  'post_id': '3949676966589363019',
  'post_url': 'https://www.instagram.com/p/DbQEkZbGfNL/',
  'product_type': 'carousel_container',
  'published_at': '2026-07-26T09:30:11+00:00',
  'shortcode': 'DbQEkZbGfNL',
  'taken_at_timestamp': 1785058211,
  'typename': 'XIGPolarisCarouselMedia',
  'user_graphql_id': '17841400543635796',
  'user_pk': '370962121',
  'username': '1989ivyshao',
  'video_view_count': None},
 # ... 23 more posts, same schema
]
```

**Important observed inconsistency**: for the exact same post (`shortcode='DbQEkZbGfNL'`), Run 1 returned `taken_at_timestamp: None` / `published_at: '2026-07-26'` (coarse date, from `accessibility_caption` fallback), while Run 2 returned `taken_at_timestamp: 1785058211` / `published_at: '2026-07-26T09:30:11+00:00'` (exact timestamp). This is not a caching bug in this library — each run creates a fresh `enrich_posts` cache and re-fetches the Embed/post pages over the network, so a precise timestamp is only present when Instagram's response for that request happened to include a parseable one at that moment. Do not rely on `taken_at_timestamp` being present or absent consistently across runs for the same post.

`edge_cursor` values also differ between the two runs — this is expected: Instagram issues a new opaque pagination cursor for the same edge on each fresh GraphQL request, and it is not a stable identifier.
