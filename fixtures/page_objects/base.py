from selenium.webdriver.common.by import By

from sentry.testutils.pytest.selenium import Browser


class BasePage:
    """Base class for PageObjects"""

    def __init__(self, browser: Browser):
        self.browser = browser

    @property
    def driver(self):
        return self.browser.driver

    def wait_until_loaded(self):
        self.browser.wait_until_not('[data-test-id="loading-indicator"]')


class BaseElement:
    def __init__(self, element):
        self.element = element


class ButtonElement(BaseElement):
    label_attr = "aria-label"
    disabled_attr = "aria-disabled"

    @property
    def disabled(self):
        return self.element.get_attribute(self.disabled_attr)

    @property
    def label(self):
        return self.element.get_attribute(self.label_attr)

    def click(self):
        self.element.click()


class ButtonWithIconElement(ButtonElement):
    @property
    def icon_href(self):
        return self.element.find_element(by=By.TAG_NAME, value="use").get_attribute("href")


class TextBoxElement(BaseElement):
    pass


class ModalElement(BaseElement):
    pass
