# -*- coding: utf-8 -*-
from selenium.webdriver.common.by import By


class PageText(object):
    SHOW_MORE_PROFILE_POSTS_PREFIX = "顯示更多"
    SHOW_MORE_PROFILE_POSTS_SUFFIX = "的貼文"
    SHOW_MORE_POSTS_ENGLISH = "Show more posts"


class PageRoleValue(object):
    BUTTON = "button"


class PageLocators(object):
    LOGIN_DIALOG = (By.XPATH, "//div[@role='dialog']")
    LOGIN_DIALOG_CLOSE = (
        By.XPATH,
        "//div[@role='dialog']//svg[@aria-label='關閉' or @aria-label='Close']"
        "[.//title[normalize-space()='關閉' or normalize-space()='Close'] or @aria-label]"
        "/ancestor::div[@role='button'][1]",
    )
    LOGIN_CLOSE_FALLBACK = (
        By.XPATH,
        "//svg[@aria-label='關閉' or @aria-label='Close' or "
        ".//title[normalize-space()='關閉' or normalize-space()='Close']]"
        "/ancestor::div[@role='button'][1]",
    )
    SHOW_MORE_PROFILE_POSTS = (
        By.XPATH,
        "//div[@role='button' and .//span["
        "(starts-with(normalize-space(.), '顯示更多') and "
        "contains(normalize-space(.), '的貼文')) or "
        "contains(normalize-space(.), 'Show more posts')]]",
    )