# -*- coding: utf-8 -*-
if __package__:
    from . import InstagramGraphqlScraper as ig_graphql_scraper
else:
    from scraper import InstagramGraphqlScraper as ig_graphql_scraper


## Example.1 - without logging in
if __name__ == "__main__":
    instagram_user_name = "love.yuweishao"
    instagram_user_id = "100044253168423"
    days_limit = 100 # Number of days within which to scrape posts
    driver_path = "/Users/hongshangren/Downloads/chromedriver-mac-arm64_136/chromedriver" 
    ig_spider = ig_graphql_scraper(driver_path=driver_path, open_browser=False)
    res = ig_spider.get_user_posts(ig_username_or_userid=instagram_user_id, days_limit=days_limit, display_progress=True)


## Example.2 - login in your Instagram account to collect data
# if __name__ == "__main__":
    # instagram_user_name = "love.yuweishao"
    # instagram_user_id = "100044253168423"
    # ig_account = "instagram_account"
    # ig_pwd = "instagram_password"
    # days_limit = 30 # Number of days within which to scrape posts
    # driver_path = "/Users/hongshangren/Downloads/chromedriver-mac-arm64_136/chromedriver" 
    # ig_spider = ig_graphql_scraper(ig_account=ig_account, ig_pwd=ig_pwd, driver_path=driver_path, open_browser=False)
    # res = ig_spider.get_user_posts(ig_username_or_userid=instagram_user_name, days_limit=days_limit, display_progress=True)
    # print(res)
    
