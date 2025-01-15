import asyncio
import logging
import random
import shutil
import string
import sys
import traceback
from argparse import ArgumentParser
from asyncio import sleep
from pathlib import Path
from typing import List

from selenium.common.exceptions import (ElementClickInterceptedException,
                                        ElementNotInteractableException,
                                        NoSuchElementException,
                                        StaleElementReferenceException,
                                        TimeoutException)
from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import (NoSuchElementException,
                                                  WebElement)
from selenium_driverless.utils.utils import safe_wrap_fut

try:
    from selenium.webdriver import ChromeOptions
except ImportError:
    import sys

    packages_path = Path.cwd() / "env" / "Lib" / "site-packages"
    sys.path.insert(0, f"{packages_path}")

    from selenium.webdriver import ChromeOptions
async def type_with_random_delay(element, text, min_delay=0.2, max_delay=0.4):
    await element.clear()
    logger.info(f"Typing: {text}")
    texttoadd = ""
    for char in text:
        if char == " ":
            texttoadd = " "
            continue
        await element.write(texttoadd + char, click_on=False)
        await asyncio.sleep(random.uniform(min_delay, max_delay))
        texttoadd = ""


async def send_PAGE_DOWN_key(el):
    await el.execute_cdp_cmd(
        "Input.dispatchKeyEvent",
        {
            "type": "keyDown",  # Use 'keyDown' to press the key
            "code": "PageDown",  # Physical key code name
            "key": "PageDown",  # Key name
            "windowsVirtualKeyCode": 34,  # Virtual key code for PAGE_DOWN
            "modifiers": 0,  # No modifiers
        },
    )


async def send_ENTER_key(el):
    # Send keyDown event for ENTER
    await el.execute_cdp_cmd(
        "Input.dispatchKeyEvent",
        {
            "type": "keyDown",
            "code": "Enter",
            "key": "Enter",
            "windowsVirtualKeyCode": 13,
            "modifiers": 0,
        },
    )


async def send_HOME_key(el):
    home_key_event = {
        "type": "keyDown",  # Use 'keyDown' to press the key
        "code": "Home",  # Key code name
        "key": "Home",  # Key name
        "windowsVirtualKeyCode": 36,  # Virtual key code for HOME
        "modifiers": 0,  # Modifiers, 0 if none are pressed
    }

    # Send the key event to the browser
    await el.execute_cdp_cmd("Input.dispatchKeyEvent", home_key_event)


async def send_CONTROL_key(el):
    await el.execute_cdp_cmd(
        "Input.dispatchKeyEvent",
        {
            "type": "keyDown",
            "code": "ControlLeft",
            "key": "Control",
            "windowsVirtualKeyCode": 17,
            "modifiers": 0,
        },
    )


async def send_CONTROL_key_up(el):
    await el.execute_cdp_cmd(
        "Input.dispatchKeyEvent",
        {
            "type": "keyUp",  # Change type to 'keyUp' for releasing the key
            "code": "ControlLeft",
            "key": "Control",
            "windowsVirtualKeyCode": 17,
            "modifiers": 0,
        },
    )


AdList = list[tuple[WebElement, str, str]]
logger = logging.getLogger("Adslog")


def get_proxies(proxy_file: Path) -> list[str]:
    """Get proxies from file

    :type proxy_file: Path
    :param proxy_file: File containing proxies
    """

    filepath = Path(proxy_file)

    if not filepath.exists():
        raise SystemExit(f"Couldn't find proxy file: {filepath}")

    with open(filepath, encoding="utf-8") as proxyfile:
        proxies = [
            proxy.strip().replace("'", "").replace('"', "")
            for proxy in proxyfile.read().splitlines()
        ]

    return proxies


async def send_key_event(driver, key, keycode, modifiers=0):
    await driver.execute_cdp_cmd(
        "Input.dispatchKeyEvent",
        {
            "type": "keyDown",
            "code": key,
            "key": key,
            "windowsVirtualKeyCode": keycode,  # Convert key to virtual key code
            "modifiers": modifiers,
        },
    )
    await driver.execute_cdp_cmd(
        "Input.dispatchKeyEvent",
        {
            "type": "keyUp",
            "code": key,
            "key": key,
            "windowsVirtualKeyCode": keycode,  # Convert key to virtual key code
            "modifiers": modifiers,
        },
    )

async def wait_for_page_load(driver:webdriver.Chrome, timeout=30):
    if not driver.current_target._page_enabled:
        await (await driver.get_target()).execute_cdp_cmd("Page.enable")

    # wait for download or loadEventFired
    wait = asyncio.ensure_future(asyncio.wait([
        safe_wrap_fut(driver.current_target.wait_for_cdp("Page.loadEventFired", timeout=None)),
        safe_wrap_fut(driver.current_target.wait_download(timeout=None))
    ], timeout=timeout, return_when=asyncio.FIRST_COMPLETED))
    await driver.refresh()
    await wait
class SearchController:
    """Search controller for ad clicker

    :type driver: selenium.webdriver
    :param driver: Selenium Chrome webdriver instance
    :type query: str
    :param query: Search query
    :type max_scroll_limit: int
    :param max_scroll_limit: Number of maximum scrolls on the search results page
    :type excludes: str
    :param excludes: Words to exclude ads containing them in url or title
    """

    URL = "https://www.google.com/?hl=fr"

    SEARCH_INPUT = (By.NAME, "q")
    RESULTS_CONTAINER = (By.ID, "appbar")
    COOKIE_DIALOG_BUTTON = (By.TAG_NAME, "button")
    TOP_ADS_CONTAINER = (By.ID, "tads")
    PRODUCTS_ADS_CONTAINER = (By.CSS_SELECTOR, ".top-pla-group-inner > div")
    BOTTOM_ADS_CONTAINER = (By.ID, "tadsb")
    AD_RESULTS = (By.CSS_SELECTOR, "div > a")
    AD_TITLE = (By.CSS_SELECTOR, "div[role='heading']")

    def __init__(
        self,
        driver: webdriver.Chrome,
        query: str,
        max_scroll_limit: int,
        excludes: str | None = None,
        is_mobile: bool = False,
    ) -> None:
        self._driver = driver
        self._max_scroll_limit = max_scroll_limit
        self._search_query, self._filter_words = self._process_query(query)
        self._exclude_list = None
        self.is_mobile = is_mobile

        if excludes:
            self._exclude_list = [item.strip() for item in excludes.split(",")]
            logger.debug(f"Words to be excluded: {self._exclude_list}")

    @staticmethod
    def setup_logger(log_file=None, level=logging.INFO, print_to_console=False):
        """
        Set up a logger with the specified name and log file.

        :param name: Name of the logger.
        :param log_file: File to write log messages to.
        :param level: Logging level (default: logging.INFO).
        """
        # Create a logger

        logger.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        if log_file:
            # Create a file handler
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)

            # Create a console handler

            # Create a formatter and set it for both handlers

            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        if print_to_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        # Add handlers to the logger

    async def search_for_ads(self) -> AdList:
        """Start search for the given query and return ads if any

        :rtype: list
        :returns: List of (ad, ad_link, ad_title) tuples
        """

        logger.info(f"Starting search for '{self._search_query}'")
        await sleep(1)

        await self._close_cookie_dialog()

        search_input_box = await self._driver.find_element(*self.SEARCH_INPUT)
        logger.debug("Search box found.")
        #await search_input_box.send_keys(self._search_query)
        
        await type_with_random_delay(search_input_box,self._search_query)
        logger.info("Sending Enter Key...")
        await send_ENTER_key(search_input_box.__target__)

        # sleep after entering search keyword by randomly selected amount
        # between 0.5 and 3 seconds
        logger.info("Sleeping randomly.")

        await asyncio.sleep(random.choice([2,3]))
        await self._driver.current_target._on_loaded()
        self._driver.current_context
        await wait_for_page_load(self._driver)
        ad_links = []

        try:
            # check f results loaded, if not raise error.
            if not self.is_mobile:
                await self._driver.find_element(*self.RESULTS_CONTAINER, timeout=5)
            logger.info("Google results loaded. Searching for ads...")
            
            await wait_for_page_load(self._driver)
            max_retries = 5
            for retry in range(max_retries):
                ad_links = await self._get_ad_links()
                
                if not ad_links:
                    logger.info(f"No add link was found. Refreshing... ({retry+1}/{max_retries} retries.)")
                    await self._driver.refresh()
                    await self._driver.wait_for_cdp("Page.domContentEventFired",timeout=120)
                    await sleep(0.5)
                    await send_HOME_key(
            (await self._driver.find_element(By.TAG_NAME, "body")).__target__
        )
                    await sleep(1)
                    
                else:
                    break
        except TimeoutException:
            logger.error("Timed out waiting for results!")
            await self.end_search()
            raise SystemExit()
        logger.info(f"{len(ad_links)} ads will be clicked.")
        return ad_links

    async def click_ads(self, ads: AdList) -> None:
        """Click ads found

        :type ads: AdList
        :param ads: List of (ad, ad_link, ad_title) tuples
        """

        # scroll to the top of the page
        logger.debug("Scrolling to the top of the page.")
        await send_HOME_key(
            (await self._driver.find_element(By.TAG_NAME, "body")).__target__
        )
        await sleep(1)

        # store the ID of the original window
        original_window_handle = self._driver.current_window_handle
        paged = False
        for index,ad in enumerate(ads):
            """if index <8:
                continue"""
            try:
                ad_link_element = ad[0]
                ad_link = ad[1]
                ad_title = ad[2]
                #logger.info(f"Clicking to [{ad_title}]({ad_link})...")

                # open link in a different tab
                async def actions_perform(driver:webdriver.Chrome,ad_link_element_fun,btn="middle",new_page=True,name="",max_retries=3):
                    pointer = driver.current_pointer
                    rect = await ad_link_element_fun.rect
                    # Extract coordinates
                    x = rect['left'] + (rect['width'] / 2)
                    y = rect['top'] + (rect['height'] / 2)
                   
                    i=0
                    while len((await driver.window_handles)) != 2:
                        i+=1
                        logger.debug(f"Clicking on {name}. ({i}/{max_retries})")
                        await pointer.move_to(x, y,total_time=1)
                        
                        await sleep(2)
                        await pointer.click(x,y,click_kwargs={"button": btn})
                        await sleep(1)
                        
                        if i ==max_retries or not new_page:
                            break
                    else:
                        logger.debug("A new window is opened succesfully.")
                await actions_perform(self._driver,ad_link_element,name=ad_title)
                await sleep(0.5)

                if len((await self._driver.window_handles)) != 2:
                    logger.debug("Couldn't click on element, trying to click next button.")
                    try:
                        if paged:
                            logger.debug("Retry failed, continuing....")
                            paged=False
                            continue
                        elbtnright = await self._driver.find_element(By.CSS_SELECTOR,"g-scrolling-carousel g-right-button")
                        if not elbtnright.is_clickable():
                            raise NoSuchElementException
                        logger.debug("Next button found! CLicking on it...")
                        await self._driver.execute_script('document.querySelector("g-scrolling-carousel g-right-button").click()')
                        ads.insert(index + 1, ad) 
                        paged=True
                        await sleep(1.5)
                        logger.debug("Retrying to click on ad...")
                        continue
                    except NoSuchElementException:
                        pass
                    
                    logger.debug("Next button not found! Scrolling element into view...")

                    await self._driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", ad_link_element
                    )
                    ads.insert(index + 1, ad) 
                    paged=True
                    
                    
                else:
                    paged=False
                    logger.debug("Opened link in a new tab. Switching to tab...")

                for window_handle in await self._driver.window_handles:
                    if window_handle.id != original_window_handle:
                        await self._driver.switch_to.window(
                            window_handle.id, activate=True
                        )
                        await sleep(1)
                        await wait_for_page_load(self._driver)
                        await sleep(random.choice(range(4, 9)))

                        logger.debug(
                            f"Current url on new tab: {await self._driver.current_url}"
                        )

                        await self._driver.close()
                        break

                # go back to original window
                await self._driver.switch_to.window(original_window_handle)
                await sleep(1)

                # scroll the page to avoid elements remain outside of the view
                logger.debug("Scrolling the page to avoid elements remain outside of the view.")
                await self._driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", ad_link_element
                ) 

            except StaleElementReferenceException:
                logger.debug(
                    f"Ad element [{ad_title}] has changed. Skipping scroll into view..."
                )

    async def end_search(self) -> None:
        """Close the browser"""

        if self._driver:
            logger.info("Closing the browser...")

            try:
                await self._driver.delete_all_cookies()
                await self._driver.close()

            except OSError as exp:
                logger.debug(exp)

    async def _get_ad_links(self) -> AdList:
        """Extract ad links to click

        :rtype: AdList
        :returns: List of (ad, ad_link, ad_title) tuples
        """

        logger.info("Getting ad links...")

        ads: List[WebElement] = []

        scroll_count = 0

        logger.debug(f"Max scroll limit: {self._max_scroll_limit}")
        products_ads: List[WebElement] = []
        try:
            products_ads_containers = await self._driver.find_elements(
                *self.PRODUCTS_ADS_CONTAINER,
            ) or await self._driver.find_elements(
                By.CSS_SELECTOR,".commercial-unit-desktop-rhs  div.pla-unit"
            )
            logger.info(f"Found a {len(products_ads_containers)} possible ad.")
            for ad_container in products_ads_containers:
                try:

                    el: WebElement = (await ad_container.find_element(
                    By.XPATH, './/a[@aria-label and @data-merchant-id]'
                )) 
            
                except NoSuchElementException:
                    logger.debug(f"An element was not qualified as an ad: `{await ad_container.text}`")
                    continue


                if (
                    await ad_container.is_displayed()
                    and (await el.get_attribute("target")) == "_blank"
                ):

                    """ d = await el.get_attribute("href"), "\n\n"
                    print(*d) """
                    products_ads.append(el)
                else:
                    logger.debug(f"This element didn't meet ad HTML requiremeents: {await ad_container.text}")

        except NoSuchElementException:
            logger.debug("Could not found products ads!")

        while not await self._is_scroll_at_the_end():
            try:
                top_ads_containers = await self._driver.find_elements(
                    *self.TOP_ADS_CONTAINER
                )
                for ad_container in top_ads_containers:
                    ads.extend((await ad_container.find_elements(*self.AD_RESULTS)))

            except NoSuchElementException:
                logger.debug("Could not found top ads!")

            try:
                bottom_ads_containers = await self._driver.find_elements(
                    *self.BOTTOM_ADS_CONTAINER
                )
                for ad_container in bottom_ads_containers:
                    ads.extend(await ad_container.find_elements(*self.AD_RESULTS))

            except NoSuchElementException:
                logger.debug("Could not found bottom ads!")

            if self._max_scroll_limit > 0 and scroll_count == self._max_scroll_limit:
                logger.debug("Reached to max scroll limit! Ending scroll...")
                break

            await send_PAGE_DOWN_key(
                (await self._driver.find_element(By.TAG_NAME, "body")).__target__
            )
            await sleep(2)

            scroll_count += 1

        if not ads and not products_ads:
            return []

        # clean non-ad links and duplicates
        cleaned_ads: List[WebElement] = []
        links = []
        for ad in products_ads:
            ad_link = await ad.get_attribute("href")
            links.append(ad_link)
            cleaned_ads.append(ad)
        for ad in ads:
            att = await ad.execute_script("return obj.getAttribute('data-pcu');")

            if att:
                ad_link = await ad.get_attribute("href")

                if ad_link not in links:
                    links.append(ad_link)
                    cleaned_ads.append(ad)

        # if there are filter words given, filter results accordingly
        filtered_ads = []
        filtered_links = []

        async def get_title(ad: WebElement):
            try:
                elti = await ad.find_element(*self.AD_TITLE)
                return (await elti.text).lower()
            except NoSuchElementException:

                return (
                    await ad.execute_script("return obj.getAttribute('aria-label');")
                ).lower()  # type:ignore

        if self._filter_words:
            for ad in cleaned_ads:
                ad_title = await get_title(ad)
                ad_link = await ad.get_attribute("data-pcu") or await ad.get_attribute(
                    "href"
                )

                for word in self._filter_words:
                    if word in ad_link or word in ad_title:
                        if filtered_links not in filtered_links:
                            #logger.debug(f"Filtering [{ad_title}]: {ad_link}")
                            filtered_ads.append(ad)
                            filtered_links.append(ad_link)
        else:
            filtered_ads = cleaned_ads

        ad_links = []

        for ad in filtered_ads:
            ad_link = await ad.get_attribute("href")
            ad_title = await get_title(ad)
            #logger.debug(f"Ad title: {ad_title}, Ad link: {ad_link}")

            if self._exclude_list:
                for exclude_item in self._exclude_list:
                    if (
                        exclude_item in ad_title
                        or exclude_item.lower() in ad_title.lower()
                    ):
                        logger.debug(f"Excluding [{ad_title}]: {ad_link}")
                        break
                else:
                    #logger.info("======= Found an Ad =======")
                    ad_links.append((ad, ad_link, ad_title))
            else:
                #logger.info("======= Found an Ad =======")
                ad_links.append((ad, ad_link, ad_title))
        
        return ad_links

    async def _close_cookie_dialog(self) -> None:
        """If cookie dialog is opened, close it by accepting"""
        await self._driver.get("https://www.google.com/?hl=en-GB")
        logger.debug("Waiting for cookie dialog...")

        await sleep(3)
        try:
            before_you = await self._driver.find_element(
                By.XPATH, "//*[contains(text(),'Before you continue to Google')]"
            )
            if not await before_you.is_displayed():
                raise NoSuchElementException
            btn = await self._driver.find_element(
                By.XPATH,
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept all')]/ancestor::button[1]",
            )
            if not await btn.is_clickable():
                raise NoSuchElementException
            logger.debug("Cookie dialog found, closing it...")
            await self._driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", btn
                    )
            await sleep(1)
            await btn.click(scroll_to=False)
            await self._driver.execute_script('arguments[0].click()',btn)
            logger.debug("Sleeping for 1 second.")
            await sleep(1)
            logger.info("Cookie dialog closed!")
            await send_HOME_key(self._driver)

        except NoSuchElementException:
            logger.debug("No cookie dialog found! Continue with search...")
            return
        finally:
            await self._driver.get(self.URL)

        await self._driver.get(self.URL)

    async def _is_scroll_at_the_end(self) -> bool:
        """Check if scroll is at the end

        :rtype: bool
        :returns: Whether the scrollbar was reached to end or not
        """

        page_height = await self._driver.execute_script(
            "return document.body.scrollHeight;"
        )
        total_scrolled_height = await self._driver.execute_script(
            "return window.pageYOffset + window.innerHeight;"
        )

        return page_height - 1 <= total_scrolled_height

    @staticmethod
    def _process_query(query: str) -> tuple[str, list[str]]:
        """Extract search query and filter words from the query input

        Query and filter words are splitted with "@" character. Multiple
        filter words can be used by separating with "#" character.

        e.g. wireless keyboard@amazon#ebay
             bluetooth headphones @ sony # amazon  #bose

        :type query: str
        :param query: Query string with optional filter words
        :rtype tuple
        :returns: Search query and list of filter words if any
        """

        search_query = query.split("@")[0].strip()

        filter_words = []

        if "@" in query:
            filter_words = [
                word.strip().lower() for word in query.split("@")[1].split("#")
            ]

        return (search_query, filter_words)


async def find_ads(
    query: str,
    driver: webdriver.Chrome,
      max_clicks:int,
    excludes: str | None = None,
    max_scroll_limit: int = 0,
    is_mobile: bool = False,
    
):
    """Entry point for the tool"""

    search_controller = None

    try:
        search_controller = SearchController(driver, query, max_scroll_limit, excludes, is_mobile)
        search_controller.setup_logger(level=logging.DEBUG, print_to_console=True)
        ads = (await search_controller.search_for_ads())[:max_clicks]

        if not ads:
            logger.info("No ads in the search results!")
        else:
            logger.info(f"Found {len(ads)} ads")
            await search_controller.click_ads(ads)

    except Exception as exp:
        logger.error("Exception occurred. See the details in the log file.")

        message = str(exp).split("\n")[0]
        logger.debug(f"Exception: {message}")
        details = traceback.format_tb(exp.__traceback__)
        logger.debug(f"Exception details: \n{''.join(details)}")

        logger.debug(f"Exception cause: {exp.__cause__}") if exp.__cause__ else None

