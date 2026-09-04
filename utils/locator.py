# -*- coding: utf-8 -*-
from selenium.webdriver.common.by import By


class PageText(object):
    SHOW_MORE_PROFILE_POSTS_PREFIX = "顯示更多"
    SHOW_MORE_PROFILE_POSTS_SUFFIX = "的貼文"


class PageRoleValue(object):
    BUTTON = "button"


class PageLocators(object):
    SHOW_MORE_PROFILE_POSTS = (
        By.XPATH,
        (
            f"//div[@role='{PageRoleValue.BUTTON}' and @tabindex='0']"
            f"[.//span["
            f"starts-with(normalize-space(.), "
            f"'{PageText.SHOW_MORE_PROFILE_POSTS_PREFIX}') "
            f"and contains(normalize-space(.), "
            f"'{PageText.SHOW_MORE_PROFILE_POSTS_SUFFIX}')"
            f"]]"
        )
    )