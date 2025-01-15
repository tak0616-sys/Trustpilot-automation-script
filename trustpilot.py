import asyncio
import configparser
import email as email_module
import hashlib
import itertools
import logging
import os
import poplib
import random
import re
import socket
import time
import traceback
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parseaddr
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import paramiko
import paramiko.ssh_exception
import requests
from openpyxl import load_workbook
from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import NoSuchElementException

from ads import find_ads

#New code to handle MOUSE movements
from record_movements import MouseDataHandler

# Router settings


config_file_name = "config.ini"
encoding = "utf-8-sig"
logger_name = "trustpilot"
log_file_name = "trustpilot.log"
level = logging.DEBUG


####


def get_desktop_path():
    import ctypes
    from ctypes import windll, wintypes  # type:ignore

    CSIDL_DESKTOP = 0
    _SHGetFolderPath = windll.shell32.SHGetFolderPathW
    _SHGetFolderPath.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPCWSTR,
    ]
    path_buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    _SHGetFolderPath(0, CSIDL_DESKTOP, 0, 0, path_buf)
    return path_buf.value


if os.environ.get("mode") == "dev":
    event = asyncio.Event()
config_file = os.path.join(os.path.dirname(__file__), config_file_name)

default_config_file = os.path.join(os.path.dirname(__file__), "configSample.ini")
configuraion = configparser.ConfigParser(inline_comment_prefixes="#")
configuraion.read(default_config_file, encoding=encoding)
configuraion.read(config_file, encoding=encoding)


class TrustPilotconfig:
    skip = configuraion.getboolean("TrustPilot", "skip")
    excel_file = os.path.join(
        get_desktop_path(), configuraion.get("TrustPilot", "excel_file")
    )


class Adsconfig:
    skip = configuraion.getboolean("Ads", "skip")
    query = configuraion.get("Ads", "query")
    keywords = [x.strip() for x in configuraion.get("Ads", "keywords").split(",")]
    randomize_query = configuraion.getboolean("Ads", "randomize_query")
    ad_clicks = configuraion.getint("Ads", "ad_clicks")


class IPconfig:
    skip = configuraion.getboolean("IP", "skip")
    IP = configuraion.get("IP", "ip")
    username = configuraion.get("IP", "username")
    password = configuraion.get("IP", "passowrd")
    command = configuraion.get("IP", "command")


class Browserconfig:
    location = configuraion.get("Browser", "location")


class Outputconfig:
    statuscolumn = configuraion.get("Output", "statuscolumn")


#
logger = logging.getLogger(logger_name)
log_file = os.path.join(os.path.dirname(__file__), log_file_name)

if not os.path.exists(log_file):
    open(log_file, mode="w+", encoding=encoding).close()
logger.setLevel(level)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# Create a file handler
file_handler = logging.FileHandler(log_file, encoding=encoding)
file_handler.setLevel(level)

# Create a console handler

# Create a formatter and set it for both handlers

file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(level)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
# Add handlers to the logger

# proxy_ad = "premium-residential.geonode.com:9002"

GMX_HOST = {
    "host": "pop.gmx.com",
    "port": 995,
    "handler": "get_last_email_code",
    "argument": "provider",
}

OUTLOOK_HOST = {"handler": "get_last_outlook_code", "argument": "driver"}
GMAIL_HOST = {"handler": "get_last_gmail_code", "argument": "driver"}
YAHOO_HOST = {"handler": "get_last_yahoo_code", "argument": "driver"}

EMAIL_PROVIDERS = {
    # ProtonMail domains
    # GMX domains
    "gmx.com": GMX_HOST,
    "gmx.de": GMX_HOST,
    "gmx.net": GMX_HOST,
    # Gmail domains
    "gmail.com": GMAIL_HOST,
    # Outlook, Hotmail, Live, MSN domains
    "outlook.com": OUTLOOK_HOST,
    "hotmail.com": OUTLOOK_HOST,
    "live.com": OUTLOOK_HOST,
    "msn.com": OUTLOOK_HOST,
    "live.co.uk": OUTLOOK_HOST,
    "hotmail.co.uk": OUTLOOK_HOST,
}


# Function to simulate typing with a random delay
async def type_with_random_delay(
    element: webdriver.WebElement, text, min_delay=0.05, max_delay=0.8
):
    await element.clear()
    logger.debug(f"Typing: {text}")
    for char in text:
        await element.write(char, click_on=False)
        await asyncio.sleep(random.uniform(min_delay, max_delay))


def check_internet_connection(timeout=60 * 5, interval=10):
    """
    Check for an active internet connection for up to `timeout` seconds,
    retrying every `interval` seconds.

    Args:
        timeout (int): Maximum time to keep checking for an internet connection.
        interval (int): Time to wait between checks.

    Raises:
        TimeoutError: If no internet connection is detected within the timeout period.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Attempt to connect to a common DNS server (Google's public DNS server)
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            logger.debug("Internet connection detected.")
            return True
        except OSError:
            logger.debug(f"No internet connection. Retrying in {interval} seconds...")
            time.sleep(interval)

    raise TimeoutError("No internet connection detected after 2 minutes.")


def get_public_ip():
    try:
        # Make a request to an external service that returns your public IP address
        response = requests.get("https://api.ipify.org?format=json")
        public_ip = response.json().get("ip")
        return public_ip
    except requests.RequestException as e:
        logger.debug(f"Unable to get public IP address: {e}")
        return None


def generate_variations(query: str, extra_words: List[str]):
    if not Adsconfig.randomize_query:
        return query
    words = query.split()
    permutations = list(itertools.permutations(words))

    variations = set()
    for perm in permutations:
        variation = " ".join(perm)
        variations.add(variation)

        # Optional: add extra words to blur the search further
        if extra_words:
            for _ in range(random.randint(1, 3)):
                variation_with_extra = variation + " " + random.choice(extra_words)
                variations.add(variation_with_extra)

    return random.choice(list(variations))


def restart_wan():
    # Create an SSH client
    if IPconfig.skip:
        return
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # Connect to the router
        client.connect(
            IPconfig.IP, username=IPconfig.username, password=IPconfig.password
        )

        # Execute the command to restart the WAN interface
        client.exec_command(IPconfig.command)
    except paramiko.ssh_exception.AuthenticationException:
        logger.error(
            "Couldn't Authenticate to the router. Maybe wrong IP/username/password?"
        )
    finally:
        # Close the connection
        client.close()


def get_email_provider(email):
    # Extract the domain from the email
    match = re.search(r"@([\w.-]+)", email)
    if match:
        domain = match.group(1).lower()
        provider = EMAIL_PROVIDERS.get(domain)
        if provider:
            return provider
    raise Exception(f"Couldn't detect provider for: {email}")

##################### NEW ASYNC FUNCTIONS #####################
# Add after existing imports




# # Replace or modify the existing type_with_random_delay function
# async def type_with_random_delay(element: webdriver.WebElement, text: str, min_delay=0.05, max_delay=0.8):
#     """Type text with random delays and occasional mistakes"""
#     await element.clear()
#     logger.debug(f"Typing: {text}")
    
#     typed_text = ""
#     for char in text:
#         # Simulate typing mistakes (5% chance)
#         if random.random() < 0.05:
#             # Type a wrong character
#             wrong_char = random.choice('qwertyuiopasdfghjklzxcvbnm')
#             await element.write(wrong_char, click_on=False)
#             await asyncio.sleep(random.uniform(0.1, 0.3))
#             # Delete the mistake
#             await element.send_keys(webdriver.Keys.BACKSPACE)
#             await asyncio.sleep(random.uniform(0.1, 0.3))
            
#         # Type the correct character with variable delay
#         await element.write(char, click_on=False)
#         typed_text += char
        
#         # Variable typing speed based on character type
#         if char in '.!? ':
#             delay = random.uniform(max_delay, max_delay * 1.5)
#         elif char in ',;':
#             delay = random.uniform(min_delay * 2, max_delay)
#         else:
#             delay = random.uniform(min_delay, max_delay)
            
#         await asyncio.sleep(delay)





async def replay_random_mouse_recording():
    """
    Select and replay a random mouse recording using MouseDataHandler.
    """
    # Instantiate the MouseDataHandler class
    mouse_data_handler = MouseDataHandler(base_dir="mouse_recordings")
    print("MouseDataHandler instantiated.", mouse_data_handler.metadata_path)

    # # Print metadata for existing recordings
    # for rec_id, meta in mouse_data_handler.metadata["recordings"].items():
    #     print(f"Recording ID: {rec_id}", meta)

    # Get all recordings
    recordings = mouse_data_handler.get_all_recordings()
    if not recordings:
        print("No recordings found.")
        return

    # Select a random recording
    random_recording = random.choice(recordings)
    recording_id = random_recording["id"]

    print(f"Selected recording: {recording_id}")

    # Replay the selected recording
    mouse_data_handler.replay_recording(recording_id)


#Scrolling naturally
async def scroll_naturally(driver):
    total_height = await driver.execute_script("return document.body.scrollHeight")
    current_height = 0
    scroll_step = random.randint(100, 300)
    
    while current_height < total_height:
        scroll_amount = min(scroll_step, total_height - current_height)
        await driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
        current_height += scroll_amount
        await random_sleep(0.3, 1.2)  # Random pause between scrolls
        
        # Occasionally scroll back up a bit
        if random.random() < 0.2:  # 20% chance
            await driver.execute_script(f"window.scrollBy(0, -{random.randint(50, 150)})")
            await random_sleep(0.5, 1.5)


# randomly visiting common pages    
async def visit_random_pages(driver, base_url):
    # Common pages to visit
    paths = [
        '/about',
        '/categories',
        '/blog',
    ]
    
    num_pages = random.randint(1, 3)
    visited_paths = random.sample(paths, num_pages)
    
    for path in visited_paths:
        full_url = base_url.rstrip('/') + path
        await driver.get(full_url, wait_load=True)
        await scroll_naturally(driver)
        await random_sleep(3, 7)

# # Randomly clicking things
# async def random_interactions(driver):
#     # Common elements to interact with
#     selectors = [
#         "//a[contains(@href, 'categories')]",
#         "//a[contains(@href, 'about')]",
#         "//div[contains(@class, 'footer')]//a",
#         "//button[contains(@class, 'menu')]"
#     ]
    
#     num_interactions = random.randint(2, 5)
#     for _ in range(num_interactions):
#         try:
#             # Try to find and click random elements
#             elements = await driver.find_elements(By.XPATH, random.choice(selectors))
#             if elements:
#                 element = random.choice(elements)
#                 if await element.is_displayed() and await element.is_clickable():
#                     await element.click()
#                     await random_sleep(2, 5)
#                     await driver.back()
#                     await random_sleep(1, 3)
#         except Exception as e:
#             logger.debug(f"Interaction failed: {e}")
#             continue

###############################################################

async def random_sleep(min_seconds=1.0, max_seconds=5.0):
    # Generate a random float between min_seconds and max_seconds
    sleep_time = random.uniform(min_seconds, max_seconds)
    logger.debug(f"Sleeping for {sleep_time:.2f} seconds...")
    await asyncio.sleep(sleep_time)
    logger.debug("Awoke from sleep!")


class Wait_DOM_after_exit:
    def __init__(
        self, target: webdriver.Target, timeout: int = 10, raise_on_timeout=True
    ) -> None:
        self.target = target
        self.trig: Callable | None = None
        self.event: asyncio.Event | None = None
        self.timeout = timeout
        self.raise_on_timeout = raise_on_timeout

    async def __aenter__(self):
        await self.target.execute_cdp_cmd("Page.enable")
        load_event = asyncio.Event()
        logger.debug("Listening for Dom event...")

        def trig(event_data):
            nonlocal load_event
            load_event.set()
            logger.debug("DOM FIRED sent signal.")

        self.trig = trig
        await self.target.add_cdp_listener("Page.domContentEventFired", self.trig)
        self.event = load_event
        return self

    async def __aexit__(self, exc_type, exc, tb):

        if self.trig and self.event:
            # await self.event.wait() but with timeout
            try:
                await asyncio.wait_for(self.event.wait(), timeout=self.timeout)
                logger.debug("DOM signal received.")
            except asyncio.TimeoutError:
                if self.raise_on_timeout:
                    raise TimeoutError("Timeout waiting for DOM signal.")
                logger.debug("Timeout waiting for DOM signal.")
            finally:
                await self.target.remove_cdp_listener(
                    "Page.domContentEventFired", self.trig
                )


class Wait_LOAD_after_exit:
    eventname = "Page.loadEventFired"

    def __init__(
        self, target: webdriver.Target, timeout: int = 10, raise_on_timeout=True
    ) -> None:
        self.target = target
        self.trig: Callable | None = None
        self.event: asyncio.Event | None = None
        self.timeout = timeout
        self.raise_on_timeout = raise_on_timeout

    async def __aenter__(self):
        await self.target.execute_cdp_cmd("Page.enable")
        load_event = asyncio.Event()
        logger.debug("Listening for Dom event...")

        def trig(event_data):
            nonlocal load_event
            load_event.set()
            logger.debug("DOM FIRED sent signal.")

        self.trig = trig
        await self.target.add_cdp_listener(self.eventname, self.trig)
        self.event = load_event
        return self

    async def __aexit__(self, exc_type, exc, tb):

        if self.trig and self.event:
            # await self.event.wait() but with timeout
            try:
                await asyncio.wait_for(self.event.wait(), timeout=self.timeout)
                logger.debug("DOM signal received.")
            except asyncio.TimeoutError:
                if self.raise_on_timeout:
                    raise TimeoutError("Timeout waiting for DOM signal.")
                logger.debug("Timeout waiting for DOM signal.")
            finally:
                await self.target.remove_cdp_listener(self.eventname, self.trig)


async def get_current_url(target: webdriver.Target) -> str:
    startingdelay = 5
    exc = Exception("Couldn't retreive URL.")

    for i in range(3):
        try:
            return await target.current_url
        except Exception as e:
            logger.warning(f"Couldn't get URL. Retrying... {i} {e}")
            if i == 2:
                await target.refresh()
            exc = e
            await asyncio.sleep(startingdelay)
            startingdelay *= 2
    raise exc


async def find_gmail_tab(_driver: webdriver.Chrome) -> webdriver.Target:
    targets = await _driver.get_targets(_type="page")
    for i in targets.values():
        if "gmail" in i.title.lower():
            return await _driver.get_target(i.id)
    raise Exception("Gmail tab not found.")


async def get_verification_code(target: webdriver.Target, recovery_email, email_address, email_password, driver):
    provider = get_email_provider(recovery_email)
    handler: Callable[
        [str, str, str, Optional[Dict | webdriver.Chrome]], Awaitable[str]
    ] = globals().get(
        provider["handler"]
    )
    if not handler:
        raise Exception("Handler not found.")

    third_argument = (
        locals().get(provider["argument"])
        if ("argument" in provider and provider["argument"])
        else None
    )

    last_email_code = await handler(
        recovery_email, email_password, email_address, third_argument
    )
    logger.info(f"Verification code or error: {last_email_code}")
    if last_email_code.isdigit() and len(last_email_code) == 6:
        logger.debug("Verification code found.")
        return last_email_code
    else:
        logger.error(f"Couldn't get verification code: {last_email_code}")
        raise Exception(f"Couldn't get verification code: {last_email_code}")


async def get_last_gmail_code(email_address, email_password, recovery_email, _driver: webdriver.Chrome):

    logger.info(f"Get pin code from gmail: {email_address}")
    start_time = time.time()
    target = await _driver.new_window("tab", activate=True)
    logger.debug("Waiting for Gmail Page to load...")
    await target.get("https://gmail.com", timeout=120)
    old_url = await target.current_url
    match = re.search(r"[?&]hl=([^&]*)", old_url)
    if match:
        lang = match.group(1)
        new_url = old_url.replace(lang, "en-GB")
    else:
        new_url = old_url + "&hl=en-GB"
    await target.get(new_url, timeout=120)
    logger.debug("Page loaded.")
    for typ, value, next in zip(
        ("email", "password"),
        (email_address, email_password),
        ("identifierNext", "passwordNext"),
    ):

        element = await target.find_element(
            By.XPATH, f"//input[@type='{typ}']", timeout=10
        )
        while not await element.is_displayed():
            await asyncio.sleep(0.5)
        await type_with_random_delay(element, value)
        next_button = await target.find_element(
            By.XPATH, f"//div[@id='{next}']//button", timeout=5
        )
        if not await next_button.is_clickable():
            raise Exception("The next button is not clickable...")
        await next_button.click()
        logger.debug(f"{typ} entered and next button clicked.")
        await random_sleep(min_seconds=5, max_seconds=8)
        if typ == "email":
            try:
                await target.find_element(
                    By.XPATH, "//iframe[@title='reCAPTCHA']", timeout=1
                )
                logger.error(f"Captcha detected for {value}. Exiting...")
                raise Exception("Captcha detected.")
            except NoSuchElementException:
                pass

    while not ("mail.google.com/mail/" in (await get_current_url(target))):
        async with Wait_DOM_after_exit(target, timeout=10, raise_on_timeout=False):
            # check for "Recover your Google Account" page
            try:
                unusual_activity = await target.find_element(
                    By.XPATH,
                    "//*[contains(text(), 'We noticed unusual activity with your Google Account.')]",
                    timeout=5
                )
                if await unusual_activity.is_displayed():
                    raise Exception("Found 'Unusual activity detected.' message.")
            except NoSuchElementException:
                logger.debug("Unusual activity not detected.")

            # check for "Couldn’t find your Google Account" page
            try:
                error = await target.find_element(
                    By.XPATH, "//*[contains(text(), 'find your Google Account')]", timeout=5
                )
                if await error.is_displayed():
                    raise Exception("Couldn’t find your Google Account")
            except NoSuchElementException:
                logger.debug("Couldn’t find errors.")

            # check for "Verify it's you" page
            try:
                continue_button = await target.find_element(
                    By.XPATH, "//*[@id='accountRecoveryButton']", timeout=5
                )
                await continue_button.click()
                logger.debug("Clicked on 'Continue' button.")
                await random_sleep(5, 8)
                continue
            except NoSuchElementException:
                logger.debug("Continue button not found.")

            # check for "Get a verification code" page
            try:
                verification_element = await target.find_element(
                    By.XPATH, "//*[contains(text(), 'Get a verification code')]"
                )
                if await verification_element.is_clickable():
                    logger.debug("Verification page detected, proceeding with verification.")
                    await verification_element.click()
                    logger.debug("Selected 'Get a verification code at...'")
                verification_code = await get_verification_code(
                    target, recovery_email, email_address, email_password, _driver
                )
                code_input = await target.find_element(By.XPATH, "//*[@id='idvPinId']", timeout=30)
                await type_with_random_delay(code_input, verification_code)
                next_button = await target.find_element(By.XPATH, "//button[text()='Next']")
                await next_button.click()
                logger.debug("Verification code entered and next button clicked.")
                await random_sleep(5, 8)
                break
            except NoSuchElementException:
                logger.debug("Verification page not detected, continuing...")

            logger.debug(
                "The webserver didn't redirect to gmail, clicking 'Not now'...."
            )

            not_now = None
            try:
                not_now = await target.find_element(
                    By.XPATH, "//span[text()='Not now']", timeout=3
                )
            except NoSuchElementException:
                logger.debug("Not now button not found. Trying to find 'Skip' button.")
                try:
                    not_now = await target.find_element(
                        By.XPATH, "//span[text()='Skip']", timeout=3
                    )
                except NoSuchElementException:
                    logger.debug("Skip button not found.")
            if not_now and await not_now.is_displayed():
                await not_now.click()
                logger.debug("'Not now' button clicked, sleeping...")
                await random_sleep(15, 18)

            break
    async with Wait_DOM_after_exit(target, timeout=10, raise_on_timeout=False):
        await target.get(
            "https://mail.google.com/mail/u/0/#advanced-search/is_unread=true&isrefinement=true"
        )
    await random_sleep(5, 10)
    targets = await _driver.get_targets(_type="page")
    for i in targets.values():
        if "gmail" in i.title.lower():
            target = await _driver.get_target(i.id)
            break
    else:
        raise Exception("Gmail tab not found.")
    logger.debug("The webserver redirected the user to gmail.")
    time_diff = time.time() - start_time
    if (time_diff) < 30:
        logger.debug(f"Sleeping time difference: {time_diff} Seconds.")
        await asyncio.sleep(time_diff)

    list_of_mails = await target.find_elements(By.XPATH, "//div//tbody//tr")
    subjects = [await el.text for el in list_of_mails]
    await target.close()
    confirmation_code = (
        f"No confirmation code found in subject. Total subjects ({len(subjects)})"
    )
    for subject in subjects:
        if match := re.search(r"\b\d{4}\b", subject):
            confirmation_code = match.group(0)
            return confirmation_code
        elif match := re.search(r"\b\d{6}\b", subject):
            confirmation_code = match.group(0)
            return confirmation_code
        else:
            confirmation_code = "No confirmation code found in subject."

    return confirmation_code


async def get_last_outlook_code(
    email_address, email_password, recovery_email, _driver: webdriver.Chrome
):
    logger.info(f"Get pin code from outlook: {email_address}")
    start_time = time.time()

    target = await _driver.new_window("tab", activate=True)
    async with Wait_LOAD_after_exit(target):
        await target.get("https://outlook.office.com/mail/")
        await random_sleep(8, 12)
    try:
        email_input_el = await target.find_element(
            By.XPATH, f"//input[@type='email']", timeout=5
        )
    except NoSuchElementException:
        logger.error("Email input not found.")
        raise Exception("Email input not found.")
    await type_with_random_delay(email_input_el, email_address)
    await random_sleep(1, 3)
    try:
        submit_btn = await target.find_element(
            By.XPATH, "//input[@type='submit']", timeout=1
        )
    except NoSuchElementException:
        logger.error("Submit button not found.")
        raise Exception("Submit button not found.")
    async with Wait_LOAD_after_exit(target):
        await submit_btn.click()
        await random_sleep(8, 12)

    try:
        password_el = await target.find_element(
            By.XPATH, f"//input[@type='password']", timeout=8
        )
    except NoSuchElementException:
        logger.error("Password input not found.")
        raise Exception("Password input not found.")
    await type_with_random_delay(password_el, email_password)
    await random_sleep(1, 3)
    try:
        submit_btn = await target.find_element(
            By.XPATH, "//button[@type='submit']", timeout=5
        )
    except NoSuchElementException:
        logger.error("Submit button not found.")
        raise Exception("Submit button not found.")
    async with Wait_LOAD_after_exit(target):
        await submit_btn.click()

        await random_sleep(8, 12)

    while True:
        if not "/mail/0/" in (current_url := await get_current_url(target)).lower():
            async with Wait_LOAD_after_exit(target, timeout=10, raise_on_timeout=False):
                # find skip button
                try:
                    skip_btn = await target.find_element(
                        By.XPATH,
                        "//*[not(self::script) and not(self::style) and (contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'skip') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ignorer pour')) and not(ancestor-or-self::*[@style[contains(.,'display:none') or contains(.,'visibility:hidden') or contains(.,'opacity:0')]])]",
                        timeout=10,
                    )
                    await skip_btn.click()
                    logger.debug("Clicked 'Skip' button")
                    await random_sleep(3, 8)
                    continue  # Restart the loop after clicking
                except NoSuchElementException:
                    logger.debug("'Skip' button not found. Trying 'no' button.")

                # If "skip" is not found, try the "no" button
                try:
                    no_btn = await target.find_element(
                        By.XPATH,
                        "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'no') and @type='submit']",
                        timeout=2,
                    )
                    await no_btn.click()
                    logger.debug("Clicked 'No' button")
                    await random_sleep(3, 8)
                    continue  # Restart the loop after clicking
                except NoSuchElementException:
                    logger.debug("'No' button not found. Trying 'Next'.")

                # If neither "skip" nor "no" are found, try the "Next" button
                try:
                    accept_conditions_btn = await target.find_element(
                        By.XPATH, "//*[@id='iNext']", timeout=10
                    )
                    if await accept_conditions_btn.is_displayed():
                        await accept_conditions_btn.click()
                        logger.debug("Clicked 'Next' button")
                        await random_sleep(3, 8)
                        continue  # Restart the loop after clicking
                except NoSuchElementException:
                    raise Exception("No 'Skip', 'No', 'Next' or 'Accept' button found.")

        else:
            break
    await random_sleep(8, 12)
    list_of_mails = await target.find_elements(By.XPATH, "//div[@role='option']")

    subjects = [await el.text for el in list_of_mails]
    await target.close()
    confirmation_code = (
        f"No confirmation code found in subject. Total subjects ({len(subjects)})"
    )
    for subject in subjects:
        if match := re.search(r"\b\d{4}\b", subject):
            confirmation_code = match.group(0)
            return confirmation_code
        elif match := re.search(r"\b\d{6}\b", subject):
            confirmation_code = match.group(0)
            return confirmation_code
        else:
            confirmation_code = "No confirmation code found in subject."

    return confirmation_code


async def get_last_yahoo_code(email_address, email_password, recovery_email, _driver: webdriver.Chrome):
    logger.info(f"Yahoo {email_address}: Get pin code from yahoo: {email_address}")
    start_time = time.time()

    target = await _driver.new_window("tab", activate=True)
    async with Wait_DOM_after_exit(target):
        await target.get("https://login.yahoo.com/")
    await random_sleep(3, 6)
    try:
        email_input_el = await target.find_element(By.ID, f"login-username", timeout=10)
    except NoSuchElementException:
        logger.error(f"Yahoo {email_address}: Email input not found.")
        raise Exception("Email input not found.")
    await type_with_random_delay(email_input_el, email_address)
    await random_sleep(1, 3)
    try:
        submit_btn = await target.find_element(By.ID, "login-signin", timeout=5)
    except NoSuchElementException:
        logger.error(f"Yahoo {email_address}: Submit button not found.")
        raise Exception(f"Yahoo {email_address}: Submit button not found.")
    async with Wait_DOM_after_exit(target):
        await submit_btn.click()
    await random_sleep(3, 5)
    try:
        password_el = await target.find_element(By.ID, f"login-passwd", timeout=5)
    except NoSuchElementException:
        # fin el that have "We can’t sign you in right now"
        try:
            error = await target.find_element(
                By.XPATH,
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'We can’t sign you in right now')]",
                timeout=2,
            )
            logger.error(f"Yahoo {email_address}: We can’t sign you in right now")
            raise Exception(f"Yahoo {email_address}: We can’t sign you in right now")
        except NoSuchElementException:
            pass
        logger.error(f"Yahoo {email_address}: Password input not found.")
        raise Exception(f"Yahoo {email_address}: Password input not found.")
    await type_with_random_delay(password_el, email_password)
    await random_sleep(3, 5)
    try:
        submit_btn = await target.find_element(By.ID, "login-signin", timeout=5)
    except NoSuchElementException:
        logger.error(f"Yahoo {email_address}: Submit button not found.")
        raise Exception(f"Yahoo {email_address}: Submit button not found.")
    async with Wait_DOM_after_exit(target):
        await submit_btn.click()

    await random_sleep(5, 8)
    while True:
        if not "login.yahoo" in (current_url := await get_current_url(target)).lower():
            # find skip button
            try:
                skip_btn = await target.find_element(
                    By.XPATH,
                    "//*[not(self::script) and not(self::style) and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'skip') and not(ancestor-or-self::*[@style[contains(.,'display:none') or contains(.,'visibility:hidden') or contains(.,'opacity:0')]])]",
                    timeout=2,
                )
            except NoSuchElementException:
                skip_btn = await target.find_element(
                    By.XPATH,
                    "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'no') and @type='submit']",
                    timeout=2,
                )
            await skip_btn.click()
            await random_sleep(3, 8)
        else:
            break
    async with Wait_LOAD_after_exit(target, timeout=10, raise_on_timeout=True):
        await target.get("https://mail.yahoo.com/d/folders/1?reason=onboarded")

    list_of_mails = await target.find_elements(By.XPATH, "//div[@role='option']")
    subjects = [await el.text for el in list_of_mails]
    await target.close()
    confirmation_code = (
        f"No confirmation code found in subject. Total subjects ({len(subjects)})"
    )
    for subject in subjects:
        if match := re.search(r"\b\d{4}\b", subject):
            confirmation_code = match.group(0)
            return confirmation_code
        elif match := re.search(r"\b\d{6}\b", subject):
            confirmation_code = match.group(0)
            return confirmation_code
        else:
            confirmation_code = "No confirmation code found in subject."

    return confirmation_code


"""async def test():
    options = webdriver.ChromeOptions()
    options.add_argument("--lang=en-GB")
    options.binary_location = Browserconfig.location
    async with webdriver.Chrome(options=options) as driver:
        await get_last_yahoo_code("hbczySSfpBe@yahoo.com", "8E8cuUr0YhuB", driver)


asyncio.run(test())"""


# Function to get the last email code
async def get_last_email_code(email_address, email_password, recovery_email, provider):
    await asyncio.sleep(30)
    try:

        # Connect to the server using POP3
        mail = poplib.POP3_SSL(provider["host"], provider["port"])
        mail.user(email_address)
        mail.pass_(email_password)
        logger.debug("Connected and logged in.")

        # Get the number of messages in the mailbox
        num_messages = len(mail.list()[1])
        if num_messages == 0:
            logger.debug("No emails found in inbox.")
            mail.quit()
            return "No emails found in inbox."

        # Fetch the latest email
        for i in range(num_messages, 0, -1):
            response, lines, octets = mail.retr(i)
            msg_data = b"\r\n".join(lines)
            msg = email_module.message_from_bytes(msg_data)
            recipient_address = parseaddr(msg["To"])[1]
            if not recipient_address == email_address:
                continue
            # Decode email subject
            subject, encoding = decode_header(msg["Subject"])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding if encoding else "utf-8")

            # logger.debug the subject for debugging
            logger.debug("Email Subject: %s", subject)

            # Use regular expression to find a 4-digit code in the subject
            if match := re.search(r"\b\d{4}\b", subject):
                confirmation_code = match.group(0)
            elif match := re.search(r"\b\d{6}\b", subject):
                confirmation_code = match.group(0)
            else:
                confirmation_code = "No confirmation code found in subject."

            # Close the connection
            mail.quit()
            logger.debug("Logged out.")

            return confirmation_code
        logger.error(f"No confirmation code found for {email_address}.")
        return f"No confirmation code found for {email_address}."
    except Exception as e:
        logger.error(f"Exception occurred: {e}")
        return f"An error occurred: {e}"


# Function to generate a random date between two dates
def generate_random_date(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    random_date = start + timedelta(days=random.randint(0, (end - start).days))
    return random_date.strftime("%Y-%m-%d")


def get_distictint_2_ports() -> Tuple[int, int]:
    from selenium_driverless.utils.utils import random_port

    port1, port2 = 0, 0
    while port1 == port2:
        port1 = random_port()
        port2 = random_port()
    return port1, port2


def process_options(options: webdriver.ChromeOptions):
    if os.environ.get("mode") == "dev":
        # options.add_argument(f"--load-extension={os.path.abspath('vpn')}")
        pass
    # options.add_argument(f"--proxy-server={proxy_ad}")
    # Block the specific URL
    # options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=en-GB")
    options.add_experimental_option("prefs", {"intl.accept_languages": "en,en_US"})
    options.binary_location = Browserconfig.location
    options.add_experimental_option(
        "prefs",
        {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        },
    )
    return options


def get_query() -> str:

    query = Adsconfig.query
    if not query:
        raise SystemExit(f"Please put the Query in the configuration file.")
    keywords = Adsconfig.keywords
    if "@" in query:
        query_parts = query.split("@")
        original_query = query_parts[0].strip()
        filter_query = query_parts[1].strip()
        return (
            generate_variations(original_query, keywords) + "@" + filter_query.strip()
        )
    return generate_variations(query, keywords)


def update_row(row_number: int, column: str, value: str):
    # Load the workbook and select the active sheet
    wb = load_workbook(TrustPilotconfig.excel_file)
    ws = wb.active
    if not ws:
        raise Exception("Problem with Excel file.")

    # Check if the column header exists; if not, add it
    header_row = ws[1]  # Assuming the first row is the header row
    col_index = None

    # Iterate over the headers to find if the column exists
    for cell in header_row:
        if cell.value == column:
            col_index = cell.column  # Get the column index (e.g., A=1, B=2, etc.)
            break

    # If column doesn't exist, add it at the next available column
    if col_index is None:
        col_index = len(header_row) + 1
        ws.cell(row=1, column=col_index, value=column)

    # Update the specific cell with the provided value
    ws.cell(row=row_number, column=col_index, value=value)
    # Save the workbook
    while True:
        try:
            wb.save(TrustPilotconfig.excel_file)
            logger.debug(f"Row {row_number} Column {column} updated with: {value}")
            break
        except PermissionError:
            input(
                f"Can't write to The Excel file {os.path.basename(TrustPilotconfig.excel_file)} while is opened in Excel.\nPlease Exit from Excel, then press Enter:"
            )


# Main function to perform the automation
async def main():
    # Load the Excel file

    excel_data = pd.read_excel(TrustPilotconfig.excel_file)

    for index, row in excel_data.iterrows():
        real_index = int(index) + (2 if list(excel_data.columns) else 1)  # type: ignore
        if Outputconfig.statuscolumn in excel_data.columns:
            if isinstance(row[Outputconfig.statuscolumn], str) and (
                not "error" in row[Outputconfig.statuscolumn].lower()
            ):
                continue
        # Extract details from the current row
        title = row["Title"]
        url = row["URL"]
        comment = row["Message"]
        name = row["name"]
        email_credentials = row["email"]
        logger.debug(f"Processing review for: {url}")
        parts = [part.strip() if part else None for part in email_credentials.split(":")]
        email_address, email_password, recovery_email = (parts + [None])[:3]
        provider = get_email_provider(email_address)
        # Initialize the webdriver for each review

        async def process_url(port, index: int):
            nonlocal email_address

            if TrustPilotconfig.skip:
                if os.environ.get("mode") == "dev":
                    if not event.is_set():
                        event.set()
                    else:
                        event.clear()
                return
            try:
                options = process_options(webdriver.ChromeOptions())

                options.debugger_address = f"127.0.0.1:{port}"
                options.add_argument(f"--remote-debugging-port={port}")

                async with webdriver.Chrome(options=options, debug=True) as driver:
                    """await get_last_gmail_code(
                        "MikeSpears670@gmail.com", "hgvfdxgf55", driver
                    )"""
                    if os.environ.get("mode") == "dev":
                        if event.is_set():
                            logger.debug(
                                "Browser 1 already initiated waiting for plugin and resuming..."
                            )
                            event.clear()
                        else:
                            logger.debug("Browser 1 initiated....")
                            event.set()
                            while event.is_set():
                                await asyncio.sleep(1)
                    # Use Chrome DevTools Protocol to block a specific API
                    logger.debug("Executing cdp command: Network.setBlockedURLs")
                    await driver.execute_cdp_cmd(
                        "Network.setBlockedURLs",
                        {"urls": ["https://optimizationguide-pa.googleapis.com/*"]},
                    )
                    logger.debug("Executing cdp command: Network.enable")
                    await driver.execute_cdp_cmd("Network.enable", {})

                    await driver.get(url, wait_load=True, timeout=200)
                    
                    # await replay_random_mouse_recording()
                    #Newly modified CODE 10 Jan 25 by Hamza. hamza170537@gmail.com
                    
                    # creating 20% chance to visit random pages
                    if random.randint(1, 100) <= 20:
                        await random_sleep(2, 5)
                        base_url = '/'.join(url.split('/')[:3])
                        await visit_random_pages(driver, base_url)
                        await replay_random_mouse_recording()
                        await driver.get(url, wait_load=True, timeout=200)

                    if random.randint(1, 100) <= 30: # 30% chance
                        await replay_random_mouse_recording()
                    # await random_interactions(driver)
                    # await scroll_naturally(driver)

                    await driver.maximize_window()
                    await driver.focus()
                    await random_sleep(2.5)

                    # Accept cookies
                    try:
                        accept_cookie_element = await driver.find_element(
                            By.XPATH,
                            "//button[@id='onetrust-accept-btn-handler']",
                            timeout=3,
                        )
                        logger.debug("Trying to click cookie close button..")
                        await accept_cookie_element.click(timeout=5, visible_timeout=7)
                        logger.debug("Cookie button clicked.")
                        await driver.sleep(1)
                    except:
                        logger.debug("Cookie consent button not shown")

                    # Select star review
                    star_review = await driver.find_element(
                        By.XPATH, "(//input[@name='quick-evaluate'])[5]", timeout=5
                    )
                    await star_review.click()
                    await random_sleep(4, 9)
                    try:
                        # Select star review
                        star_review = await driver.find_element(
                            By.XPATH, "(//input[@name='quick-evaluate'])[5]"
                        )
                        await star_review.click()
                        await driver.sleep(15)
                    except:
                        logger.debug("stars passed")

                    if random.randint(1, 100) <= 30: # 30% chance
                        await driver.get(url, wait_load=True, timeout=200)
                    # Type review text with random delay
                    review_box = await driver.find_element(
                        By.XPATH, "//textarea[@id='review-text']"
                    )
                    await type_with_random_delay(review_box, comment)
                    await driver.sleep(1.5)

                    ####### new code 
                    # creating 20% chance to visit random pages
                    if random.randint(1, 100) <= 20:
                        await scroll_naturally(driver)
                    ##########

                    # Type review title with random delay
                    review_title = await driver.find_element(
                        By.XPATH, "//input[@id='review-title']"
                    )
                    await review_title.clear()  # Clear the input field
                    await driver.sleep(0.5)
                    await type_with_random_delay(review_title, title)

                    await driver.sleep(1.5)
                    # Get min and max date from the date input element
                    date_element = await driver.find_element(
                        By.XPATH, "//input[@id='review-date-of-experience']"
                    )
                    min_date = await date_element.get_attribute("min")
                    max_date = await date_element.get_attribute("max")

                    ########### NEW CODE Visit random pages with 30% chance
                    if random.randint(1, 100) <= 30: # 30% chance
                        await driver.get(url, wait_load=True, timeout=200)
                    #########
                    # Generate a random date within the min and max range
                    random_date = generate_random_date(min_date, max_date)
                    await driver.sleep(10.5)
                    await driver.execute_script(
                        """
                        var element = arguments[0];
                        var value = arguments[1];
                        element.focus();
                        element.setAttribute('value', value);
                        element.dispatchEvent(new Event('input', { bubbles: true }));
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                        element.dispatchEvent(new Event('blur', { bubbles: true }));
                    """,
                        date_element,
                        random_date,
                    )
                    await driver.sleep(12.5)
                    # Proceed with the email verification process
                    email_contine_btn = await driver.find_element(
                        By.XPATH, "//button[@name='reveal-email-flow']", timeout=30
                    )
                    await email_contine_btn.click()
                    await driver.sleep(1.5)

                    email_input = await driver.find_element(
                        By.XPATH, "//input[@id='email-lookup']", timeout=30
                    )
                    
                    ####### new code 
                    # creating 20% chance to visit random pages
                    if random.randint(1, 100) <= 20:
                        await scroll_naturally(driver)
                    ##########

                    await type_with_random_delay((email_input), email_address)

                    await driver.sleep(2.5)

                    email_smbt_btn = await driver.find_element(
                        By.XPATH, "//button[@name='email-lookup']", timeout=30
                    )
                    ######## new code
                    if random.randint(1, 100) <= 30: # 30% chance
                        await driver.get(url, wait_load=True, timeout=200)
                    ########
                    await email_smbt_btn.click()
                    await driver.sleep(8)

                    try:
                        name_input = await driver.find_element(
                            By.XPATH, "//input[@id='signup-name-input']", timeout=10
                        )
                        await type_with_random_delay(name_input, name)
                        await driver.sleep(3.5)
                        smbt_btn = await driver.find_element(
                            By.XPATH, "//button[@name='signup']", timeout=10
                        )
                        await smbt_btn.click()
                        await random_sleep(4, 7)
                    except:
                        logger.debug("Name input not showing")

                    # Wait for email to be received and then get the verification code
                    # Wait for some time to receive the email
                    handler: Callable[
                        [str, str, str, Optional[Dict | webdriver.Chrome]], Awaitable[str]
                    ] = globals().get(
                        provider["handler"]
                    )  # type: ignore
                    if not handler:
                        raise Exception("Handler not found.")
                    third_argument = (
                        locals().get(provider["argument"])
                        if ("argument" in provider and provider["argument"])
                        else None
                    )
                    last_email_code = await handler(
                        email_address, email_password, recovery_email, third_argument
                    )
                    # logger.debug the verification code or error
                    logger.info(f"Verification code or error: {last_email_code}")

                    # Enter the verification code if it's valid
                    if last_email_code.isdigit() and len(last_email_code) == 4:
                        code_input = await driver.find_element(
                            By.XPATH,
                            "//input[@id='verification-code-input']",
                            timeout=30,
                        )
                        await type_with_random_delay(code_input, last_email_code)
                        await driver.sleep(10)
                        update_row(index, Outputconfig.statuscolumn, "Success ✅")
                    else:
                        update_row(
                            index,
                            Outputconfig.statuscolumn,
                            f"Error in Getting Verification code. Row: {index} | email: {email_address}",
                        )
                    await driver.execute_cdp_cmd(
                        "Network.setBlockedURLs",
                        {"urls": ["https://optimizationguide-pa.googleapis.com/*"]},
                    )
                    await driver.execute_cdp_cmd("Network.enable", {})
                    logger.info(f"Published Review sucessfully for row {index} .")

            except Exception as e:
                logger.error(
                    f"Error processing review for URL {url}: {traceback.format_exc()}"
                )
                update_row(
                    index,
                    Outputconfig.statuscolumn,
                    f"Error processing review for URL {url}: {traceback.format_exc()}",
                )

        async def run_ads(port: int) -> None:
            if Adsconfig.skip:
                if os.environ.get("mode") == "dev":
                    if not event.is_set():
                        event.set()
                    else:
                        event.clear()
                return
            try:
                options = process_options(webdriver.ChromeOptions())

                options.debugger_address = f"127.0.0.1:{port}"
                options.add_argument(f"--remote-debugging-port={port}")

                async with webdriver.Chrome(options=options, debug=True) as driver:

                    if os.environ.get("mode") == "dev":
                        if event.is_set():
                            logger.debug(
                                "Browser 1 already initiated waiting for plugin and resuming..."
                            )
                            event.clear()
                        else:
                            logger.debug("Browser 1 initiated....")
                            event.set()
                            while event.is_set():
                                await asyncio.sleep(1)
                    ###click ads
                    search_query = get_query()
                    await driver.maximize_window()
                    await find_ads(
                        # "celine opticien lunetier@celine-opticien-lunetier",
                        search_query,
                        driver,
                        max_scroll_limit=1,
                        max_clicks=Adsconfig.ad_clicks,
                    )
                    logger.info(
                        f"Clicked on ads ended succesfuly for row number {real_index}."
                    )
            except Exception as e:
                logger.error(f"Error clicking on ads: {traceback.format_exc()}")

        port1, port2 = get_distictint_2_ports()
        task1 = asyncio.create_task(process_url(port1, real_index))
        task2 = asyncio.create_task(run_ads(port2))
        try:
            await asyncio.gather(task1, task2)
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("User stopped the script, exiting ....")
            return
        try:
            old_ip = get_public_ip()
            logger.debug(f"Old IP: {old_ip}")
            print("-" * 20)
            print("\n" * 3)
            restart_wan()
            await asyncio.sleep(30)
            check_internet_connection()
            await asyncio.sleep(2)
            new_ip = get_public_ip()
            logger.debug(f"New IP: {new_ip}")

            if new_ip == old_ip:
                logger.warning("Ip didn't change!")
            else:
                logger.info("Ip changes successfully.")
        except Exception as e:
            logger.error(f"Error Rotating IP: {traceback.format_exc()}")


# Run the automation script
if __name__ == "__main__":
    asyncio.run(main())
