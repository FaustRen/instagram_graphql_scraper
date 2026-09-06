"""Public package exports for the Instagram GraphQL scraper."""

from .scraper import InstagramGraphqlScraper
from .embed import InstagramEmbedClient, fetch_posts_embed

__all__ = ["InstagramGraphqlScraper", "InstagramEmbedClient", "fetch_posts_embed"]
