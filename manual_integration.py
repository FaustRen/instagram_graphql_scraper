"""Manual browser integration entry point for public Instagram profiles."""

import argparse
import json

from scraper import InstagramGraphqlScraper


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manual Instagram browser integration check")
    parser.add_argument("username", nargs="?", default="1989ivyshao")
    parser.add_argument("--driver-path")
    parser.add_argument("--max-pages", type=int, default=2)
    args = parser.parse_args()

    scraper = InstagramGraphqlScraper(driver_path=args.driver_path, open_browser=False)
    try:
        print(json.dumps(scraper.get_user_posts(args.username, max_pages=args.max_pages), ensure_ascii=False, indent=2))
    finally:
        scraper.close()
