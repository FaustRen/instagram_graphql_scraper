"""Selenium Wire browser bootstrap helpers."""

# -*- coding:utf-8 -*-
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service
from typing import Optional

class BasePage:
    """Create and configure the Selenium Wire Chrome driver."""

    def __init__(self, driver_path: Optional[str] = None, open_browser: bool = False):
        """Initialize a Chrome driver.

        Args:
            driver_path: Optional path to the ChromeDriver executable.
            open_browser: Whether to show the browser instead of using headless mode.
        """
        chrome_options = self._build_options(open_browser)
        service = Service(driver_path) if driver_path else Service()
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        if open_browser:
            self.driver.maximize_window()
        else:
            self.driver.set_window_size(1920, 1080)

    @staticmethod
    def _build_options(open_browser: bool) -> webdriver.ChromeOptions:
        """Build Chrome options used by the scraper browser.

        Args:
            open_browser: Whether headless mode should be disabled.

        Returns:
            Configured Selenium Chrome options.
        """
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        if not open_browser:
            options.add_argument("--headless=new")
        options.add_argument("--blink-settings=imagesEnabled=false")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        return options
