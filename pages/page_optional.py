# -*- coding: utf-8 -*-
from typing import Any, Optional

try:
    from ..utils.locator import PageLocators, PageText
except ImportError:
    from utils.locator import PageLocators, PageText
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import logging


class PageOptional(object):
    def __init__(self, driver: Any = None, ig_account: Optional[str] = None, ig_pwd: Optional[str] = None, logger=None):
        self.locator = PageLocators
        self.page_text = PageText
        self.driver = driver
        self.ig_account = ig_account
        self.ig_pwd = ig_pwd
        self.logger = logger or logging.getLogger(__name__)

        # Loggin account
        if self.ig_account and self.ig_pwd:
            login_page_url = "https://www.instagram.com/accounts/login/"
            self.driver.get(url=login_page_url)
            self.login_page()

    def login_page(self):
        try:
            assert self.ig_account is not None
            assert self.ig_pwd is not None
            self.login_account(user=self.ig_account,
                               password=self.ig_pwd,
            )
            time.sleep(5)
        except Exception as e:
            print(f"Login faield, message: {e}")

    def open_profile(self, username: str):
        self.driver.get(f"https://www.instagram.com/{username.strip('/')}/")

    def clear_requests(self):
        try:
            del self.driver.requests
        except Exception as e:
            self.logger.debug("Could not clear Selenium Wire requests: %s", e)

    clean_requests = clear_requests

    def login_account(self, user: str, password: str):
        user_element = self.driver.find_element(By.NAME, "username")
        user_element.send_keys(user)
        password_element = self.driver.find_element(By.NAME, "password")
        password_element.send_keys(password)
        password_element.send_keys(Keys.ENTER)

    def scroll_window(self):
        self.driver.execute_script(
            "window.scrollTo(0,document.body.scrollHeight)")

    def scroll_window_with_parameter(self, parameter_in: str):
        self.driver.execute_script(f"window.scrollBy(0, {parameter_in});")

    def set_browser_zoom_percent(self, zoom_percent: int):
        zoom_value = str(zoom_percent)
        self.driver.execute_script(
            f"document.body.style.zoom='{zoom_value}%'")

    def move_to_element(self, element_in):
        ActionChains(self.driver).move_to_element(element_in).perform()

    def load_next_page(self, url: str, clear_limit: int = 20):
        self.clear_requests()
        self.driver.get(url=url)

    def close_login_prompt(self):
        for locator in (self.locator.LOGIN_DIALOG_CLOSE, self.locator.LOGIN_CLOSE_FALLBACK):
            try:
                button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(locator)
                )
                try:
                    button.click()
                except Exception as error:
                    if "intercept" not in str(error).lower():
                        raise
                    self.driver.execute_script("arguments[0].click();", button)
                return True
            except Exception as error:
                self.logger.debug("Instagram login close locator did not match: %s", error)
        self.logger.debug("Instagram login prompt close button was not found")
        return False

    def click_display_button(self, username: str = ""):
        button = WebDriverWait(self.driver, 15).until(
            EC.element_to_be_clickable(self.locator.SHOW_MORE_PROFILE_POSTS)
        )
        self.move_to_element(element_in=button)
        try:
            button.click()
        except Exception as error:
            if "intercept" not in str(error).lower():
                raise
            self.driver.execute_script("arguments[0].click();", button)

    def click_display_button2(self):
        return self.click_display_button()

    def click_reject_login_button(self):
        try:
            self.close_login_prompt()
        except Exception as e:
            short_message = getattr(e, "msg", str(e)).split("Stacktrace:")[0].strip()
            print(f"Click reject button skipped, message: {short_message}")

    def quit_driver(self):
        self.driver.quit()

    def close_driver(self):
        self.driver.close()
