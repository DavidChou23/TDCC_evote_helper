#!/usr/bin/env python
# coding: utf-8
# author: Gemini CLI (Reconstructed from DavidChou's TDCC_helper_tool)
# date: 2026/5/25

import os
import sys
import time
import random
import datetime
import argparse
import threading
import hashlib
import logging
import subprocess
from enum import Enum, auto
from typing import List, Dict, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('tdcc_automation.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Define States for the Automation Process
class State(Enum):
    IDLE = auto()
    INITIALIZING = auto()
    LOGIN = auto()
    VOTING = auto()
    SCREENSHOT = auto()
    LOGOUT = auto()
    ERROR = auto()
    FINISH = auto()

class TDCCAutomation:
    """
    tdcc automation class encapsulates the entire workflow of logging in, voting, and taking screenshots for TDCC e-voting.
    
    """
    def __init__(self, args):
        self.args = args
        self.driver = None
        self.state = State.IDLE
        self.base_path = "./screenshots/"
        self.time_speed = 1.0  # Default multiplier
        self.screenshot_mode = 1
        self.shareholder_ids = []
        self.vote_settings = {
            "default": "abstain",
            "manual_vote": False,
            "accept": [],
            "opposite": [],
            "abstain": []
        }
        self.vote_info_list = {}
        self.current_user = None

    def change_state(self, new_state: State):
        logger.info(f"Transitioning state: {self.state.name} -> {new_state.name}")
        self.state = new_state

    def setup_workspace(self):
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)
            logger.info(f"Created base path: {self.base_path}")
        
        # Change working directory to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # for pyinstaller
        if getattr(sys, 'frozen', False):
            script_dir = os.path.dirname(sys.executable)
        os.chdir(script_dir)
        logger.info(f"Working directory: {os.getcwd()}")

    def id_check(self, id_number: str) -> int:
        """
        Check the validity of a Taiwan citizen ID number.
        Returns :
           0 --> valid,
           1 --> length/format is incorrect,
           2 --> check digit is incorrect.
        """
        
        import re
        if len(id_number) != 10: 
            return 1
        if not re.match(r'^[A-Z][12]\d{8}$', id_number): 
            return 1
        
        map_table = {'A':1,'B':0,'C':9,'D':8,'E':7,'F':6,'G':5,'H':4,'I':9,'J':3,'K':2,'L':2,'M':1,'N':0,'O':8,'P':9,'Q':8,'R':7,'S':6,'T':5,'U':4,'V':3,'W':1,'X':3,'Y':2,'Z':0}
        total = map_table[id_number[0]] * 1
        for i in range(1, 9):
            total += int(id_number[i]) * (9 - i)
        total %= 10
        calculated_check_digit = (10 - total) % 10
        if int(id_number[9]) != calculated_check_digit: 
            return 2
        return 0

    def load_configs(self):
        self.read_program_setting()
        self.read_vote_setting()
        self.read_vote_info_list()

    def read_program_setting(self):
        config_path = './program_setting.conf'
        if not os.path.exists(config_path):
            logger.warning("program_setting.conf not found. Please configure first.")
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            data = {}
            stored_hash = ""
            for line in lines:
                line = line.replace("\r", "").replace("\n", "").replace("\ufeff", "")
                if ':::' in line:
                    key, val = line.strip().split(':::')
                    if key == 'hash': stored_hash = val
                    else: data[key] = val
            
            # Verify Hash
            content = f"{data.get('screenshot_mode', '1')}|/|{data.get('time_speed', '2')}|/|{'@'.join(data.get('shareholderIDs', '').split('|/|'))}"
            if hashlib.sha256(content.encode()).hexdigest() != stored_hash:
                logger.error("program_setting.conf hash mismatch!")
                # rename corrupted config for backup
                if os.path.exists(config_path+".bak"):
                    os.remove(config_path+".bak")
                os.rename(config_path, config_path + ".bak")
                logger.warning("Corrupted program_setting.conf has been renamed to program_setting.conf.bak. Please reconfigure settings.")
                input("Press Enter to Exit...")
                os.remove("running.lock")
                sys.exit(1)
                return

            self.screenshot_mode = int(data.get('screenshot_mode', 1))
            self.time_speed = float(data.get('time_speed', 2)) / 2
            self.shareholder_ids = data.get('shareholderIDs', '').split('|/|')
            logger.info(f"Loaded program settings. Speed: {self.time_speed*2}")
        except Exception as e:
            logger.error(f"Error reading program settings: {e}")

    def read_vote_setting(self):
        config_path = './vote_setting.conf'
        if not os.path.exists(config_path):
            logger.warning("vote_setting.conf not found. Please configure first.")
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            data = {}
            stored_hash = ""
            for line in lines:
                line = line.replace("\r", "").replace("\n", "").replace("\ufeff", "")
                if ':::' in line:
                    key, val = line.strip().split(':::')
                    if key == 'hash': stored_hash = val
                    else: data[key] = val

            # Verify Hash (simplified check for reconstruction)
            content = f"{data.get('default','')}|/|{'#'.join(data.get('accept', '').split('|/|'))}|/|{'$'.join(data.get('opposite', '').split('|/|'))}|/|{'%'.join(data.get('abstain', '').split('|/|'))}|/|{data.get('manual_vote', '')}"
            if hashlib.sha256(content.encode()).hexdigest() != stored_hash:
                logger.error("vote_setting.conf hash mismatch!")
                # rename corrupted config for backup
                if os.path.exists(config_path+".bak"):
                    os.remove(config_path+".bak")
                os.rename(config_path, config_path + ".bak")
                logger.warning("Corrupted vote_setting.conf has been renamed to vote_setting.conf.bak. Please reconfigure settings.")
                input("Press Enter to Exit...")
                os.remove("running.lock")
                sys.exit(1)
                return
            self.vote_settings['default'] = data.get('default', 'abstain')
            self.vote_settings['manual_vote'] = data.get('manual_vote') == 'True'
            self.vote_settings['accept'] = [k for k in data.get('accept', '').split('|/|') if k]
            self.vote_settings['opposite'] = [k for k in data.get('opposite', '').split('|/|') if k]
            self.vote_settings['abstain'] = [k for k in data.get('abstain', '').split('|/|') if k]
            logger.info("Loaded vote settings.")
        except Exception as e:
            logger.error(f"Error reading vote settings: {e}")

    def read_vote_info_list(self):
        folder_list = [f for f in os.listdir(self.base_path) if os.path.isdir(os.path.join(self.base_path, f))]
        for folder in folder_list:
            if folder == "all": continue
            path = os.path.join(self.base_path, folder, "incomplete_screenshot_list.txt")
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    stocks = [line.strip() for line in f if line.strip()]
                    if stocks:
                        self.vote_info_list[folder] = stocks
            else:
                #if folder empty--> rmdir and continue
                if not os.listdir(os.path.join(self.base_path, folder)):
                    os.rmdir(os.path.join(self.base_path, folder))
                    continue
                # touch incomplete_screenshot_list.txt
                with open(path, 'w', encoding='utf-8') as f:
                    f.write("")
        logger.info(f"Read unfinished tasks: {self.vote_info_list}")

    def open_browser(self):
        self.change_state(State.INITIALIZING)
        browser_type = self.args.browser
        driver_path = self.args.driver_path

        try:
            # First try the specified driver path if provided
            if not os.path.exists(driver_path):
                logger.warning(f"Specified driver path does not exist: {driver_path}. Falling back to default logic.")
                driver_path = None
            if not os.access(driver_path, os.X_OK):
                logger.warning(f"Specified driver path is not executable: {driver_path}. Falling back to default logic.")
                driver_path = None
            if driver_path and os.path.exists(driver_path) and os.access(driver_path, os.X_OK):
                # Detect driver type
                res = subprocess.run([driver_path, '--help'], capture_output=True, text=True)
                if 'msedge' in res.stdout:
                    from selenium.webdriver.edge.service import Service
                    self.driver = webdriver.Edge(service=Service(driver_path))
                    logger.info("Using Edge WebDriver from specified path.")
                    return
                elif 'Firefox' in res.stdout:
                    from selenium.webdriver.firefox.service import Service
                    self.driver = webdriver.Firefox(service=Service(driver_path))
                    logger.info("Using Firefox WebDriver from specified path.")
                    return
                elif 'chrome' in res.stdout:
                    from selenium.webdriver.chrome.service import Service
                    self.driver = webdriver.Chrome(service=Service(driver_path))
                    logger.info("Using Chrome WebDriver from specified path.")
                    return
                else:
                    logger.warning("Could not detect driver type from help output. Falling back to default logic.")
                    driver_path = None
            # no valid driver from path, try based on browser type
            if browser_type=="Edge":
                self.driver = webdriver.Edge()
                logger.info("Using Edge WebDriver.")
                return
            elif browser_type=="Firefox":
                self.driver = webdriver.Firefox()
                logger.info("Using Firefox WebDriver.")
                return
            elif browser_type=="Chrome":
                self.driver = webdriver.Chrome()
                logger.info("Using Chrome WebDriver.")
                return
            raise Exception("Failed to initialize specified browser. Falling back to default logic.")
        # Default logic
        except Exception as e:
            logger.warning(f"Failed to open specific browser: {e}. Trying fallbacks...")
            for fallback in [webdriver.Edge, webdriver.Firefox, webdriver.Chrome]:
                try:
                    self.driver = fallback()
                    logger.info(f"Using {fallback.__name__} WebDriver as fallback.")
                    break
                except: 
                    logger.warning(f"Failed to initialize {fallback.__name__} WebDriver. Trying next fallback...")
                    continue
        
        if not self.driver:
            logger.critical("Failed to initialize any WebDriver.")
            input("Press Enter to Exit...")
            os.remove("running.lock")
            sys.exit(1)
        
        logger.info("WebDriver initialized successfully.")
        return
    
    # not code review yet
    def show_msg(self, txt1, timeout_sec, txt2):
        """In-browser message display using JS."""
        def run_msg():
            try:
                self.driver.execute_script("""
                    if (!document.getElementById('gemini-msg')) {
                        var div = document.createElement('div');
                        div.id = 'gemini-msg';
                        div.style.position = 'fixed'; div.style.top = '15px'; div.style.left = '10px';
                        div.style.padding = '10px'; div.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
                        div.style.color = '#00ff00'; div.style.fontSize = '16px'; div.style.zIndex = '9999';
                        document.body.appendChild(div);
                    }
                """)
                if timeout_sec > 0:
                    for i in range(timeout_sec, 0, -1):
                        self.driver.execute_script(f"document.getElementById('gemini-msg').innerText = '{txt1} ({i}s)';")
                        time.sleep(1)
                else:
                    self.driver.execute_script(f"document.getElementById('gemini-msg').innerText = '{txt1}';")
                    time.sleep(2)
                self.driver.execute_script(f"document.getElementById('gemini-msg').innerText = '{txt2}';")
                time.sleep(1)
                self.driver.execute_script("document.getElementById('gemini-msg').remove();")
            except: pass
        threading.Thread(target=run_msg, daemon=True).start()

    def login(self, user_id):
        logger.info(f"Attempting login for {user_id}")
        # get current document content(F12-->elements-->html)
        self.driver.get("https://stockservices.tdcc.com.tw/evote/login/shareholder.html?language=TW")
        time.sleep(5)
        if str(user_id) in self.driver.page_source:
            logger.info(f"Already logged in as {user_id}.")
            self.current_user = user_id
            self.change_state(State.LOGIN)
            return True
        
        # Reset session
        self.driver.get("https://stockservices.tdcc.com.tw/evote/logout.html")
        self.current_user = None

        time.sleep(2 * self.time_speed)
        self.driver.set_window_position(20, 20)
        self.driver.set_window_size(1000, 1000)
        self.driver.get("https://stockservices.tdcc.com.tw/evote/login/shareholder.html?language=TW") # ensure it is zh-tw
        
        # Fill ID
        try:
            wait = WebDriverWait(self.driver, 10)
            id_input = wait.until(EC.presence_of_element_located((By.NAME, "pageIdNo")))
            id_input.send_keys(user_id)
        except TimeoutException:
            logger.error("ID input field not found. or page did not load properly.")
            return self.login(user_id)  # Retry login
        
        # Select CA Type (Arrow Down for first option as per original logic)
        ca_select = self.driver.find_element(By.NAME, "caType")
        ca_select.send_keys(Keys.ARROW_DOWN)
        time.sleep(1 * self.time_speed)
        
        self.driver.find_element(By.ID, 'loginBtn').click()
        logger.info("Login clicked, waiting for user CA verification...")
        
        # Wait for the "Agree" buttons or the main page
        start_time = time.time()
        while time.time() - start_time < 90:  # 1.5 minute timeout
            time.sleep(2)
            # Check for Maintenance
            if "系統維護中" in self.driver.page_source:
                logger.error("System Maintenance detected.")
                input("Press Enter to Exit...")
                os.remove("running.lock")
                sys.exit(1)
                
            # Check for "Agree" button
            try:
                agree_btn = self.driver.find_element(By.CSS_SELECTOR, 'a.btnAgree, a[name="btn1"]')
                if agree_btn.is_displayed():
                    self.show_msg("Please read and agree to the terms", 5, "Proceeding...")
                    time.sleep(5)
                    agree_btn.click()
                    logger.info("Clicked Agree button.")
            except: pass

            # Check if logged in (redirected to main or list page)
            if "tc_estock_welshas" in self.driver.current_url:
                logger.info("Login successful.")
                self.current_user = user_id
                self.change_state(State.LOGIN)
                return True
        
        logger.error("Login timeout.")
        return False

    def auto_vote_process(self):
        self.change_state(State.VOTING)
        logger.info(f"Starting auto-vote for {self.current_user}")
        self.driver.get("https://stockservices.tdcc.com.tw/evote/shareholder/000/tc_estock_welshas.html")
        
        # wait for page load
        try:
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.NAME, 'qryStockId')))
        except TimeoutException:
            logger.error("Failed to load voting page.")
            return self.auto_vote_process()  # Retry loading the page

        logger.info("Voting page loaded. Starting vote loop...")
        while True:
            time.sleep(2 * self.time_speed)
            try:
                rows = self.driver.find_elements(By.TAG_NAME, 'tr')
                target_row = None
                for row in rows:
                    if "未投票" in row.text:
                        target_row = row
                        break
                else:
                    logger.info("No more pending votes.")
                    break
                
                stock_id = target_row.text.split()[0]
                logger.info(f"Voting for Stock: {stock_id}")
                
                # Click "Vote" link
                target_row.find_element(By.TAG_NAME, 'a')[0].click()
                time.sleep(2)
                
                # Handle possible dialog
                try: self.driver.find_element(By.ID, "msgDialog_okBtn").click()
                except: pass
                
                self.perform_vote_logic()
                
                if "系統維護中" in self.driver.page_source:
                    logger.error("System Maintenance detected during voting.")
                    input("Press Enter to Exit...")
                    os.remove("running.lock")
                    sys.exit(1)
                
                if "系統操作逾時" in self.driver.page_source:
                    logger.warning("Session timeout detected during voting. Please restart the program and try again.")
                    input("Press Enter to Exit...")
                    os.remove("running.lock")
                    sys.exit(1)

                # Record in vote_info_list for screenshot later
                if self.current_user not in self.vote_info_list:
                    self.vote_info_list[self.current_user] = []
                if stock_id not in self.vote_info_list[self.current_user]:
                    self.vote_info_list[self.current_user].append(stock_id)
                self.write_vote_info_list()
                
            except Exception as e:
                logger.error(f"Error in auto_vote_process: {e}")
                break

    def perform_vote_logic(self):
        """Inner logic for clicking options within a stock's voting page."""
        while True:
            if "投票已完成" in self.driver.page_source:
                logger.info("Vote already completed for this stock.")
                self.driver.find_element(By.CSS_SELECTOR,'button[onclick="doProcess();"]').click()
                return
            
            if "我不是機器人驗證失敗" in self.driver.page_source:
                logger.warning("CAPTCHA verification failed. Please complete it manually.")
                self.show_msg("Please complete CAPTCHA", 0, "Waiting for user...")
                while "我不是機器人驗證失敗" in self.driver.page_source:
                    time.sleep(3)
                logger.info("CAPTCHA completed. Resuming vote logic.")
                continue
            
            if "系統操作逾時" in self.driver.page_source:
                logger.warning("Session timeout detected. Please restart the program and try again.")
                input("Press Enter to Exit...")
                os.remove("running.lock")
                sys.exit(1)

            if "系統維護中" in self.driver.page_source:
                logger.error("System Maintenance detected during voting.")
                input("Press Enter to Exit...")
                os.remove("running.lock")
                sys.exit(1)
            
            try:
                wait = WebDriverWait(self.driver, 10)
                # Default options (Accept/Opposite/Abstain all)
                option_idx = {"accept": 1, "opposite": 2, "abstain": 3}.get(self.vote_settings['default'], 3)
                
                if "議案投票" in self.driver.page_source:
                    # Click the header button for default vote
                    try:
                        header_btn = self.driver.find_element(By.CSS_SELECTOR, f'table.c-votelist_docSection tr:nth-child(2) td:nth-child(2) a:nth-child({option_idx})')
                        header_btn.click()
                        time.sleep(1)
                    except: pass
    
                    # Manual overrides based on keywords
                    if self.vote_settings['manual_vote']:
                        vote_rows = self.driver.find_elements(By.XPATH, '//td/input[@type="radio"]/../..')
                        for row in vote_rows:
                            text = row.text
                            value = None
                            if any(k in text for k in self.vote_settings['accept']): value = "A"
                            elif any(k in text for k in self.vote_settings['opposite']): value = "O"
                            elif any(k in text for k in self.vote_settings['abstain']): value = "C"
    
                            if value:
                                try:
                                    row.find_element(By.CSS_SELECTOR, f'input[value="{value}"]').click()
                                    time.sleep(0.3)
                                    logger.info(f"Manual vote override: {text} -> {value}")
                                except: pass
                elif "選舉" in self.driver.page_source:
                    # Candidate voting (usually skip/abstain all as per original)
                    try:
                        self.driver.find_element(By.CSS_SELECTOR, 'a[href="javascript:giveUp();"]').click()
                        time.sleep(1)
                    except: pass
                else:
                    # unhandled type, log content for debugging
                    # body > header > div > div.c-header_pageInfo
                    try:
                        page_info = self.driver.find_element(By.CSS_SELECTOR, 'body > header > div > div.c-header_pageInfo').text
                        logger.warning(f"Unknown voting page type. Page info: {page_info}")
                    except: 
                        logger.warning("Unknown voting page type.", __LINE__)
                        pass
                    
                # Proceed steps
                for _ in range(4): # Multiple "Next" or "Confirm" steps
                    try:
                        # 下一步/棄權警告/確認投票
                        next_btns = self.driver.find_elements(By.CSS_SELECTOR, 'button[onclick*="checkVote"], button[onclick*="ignoreVote"], button[onclick*="checkMeetingPartner"]')
                        for btn in next_btns:
                            if btn.is_displayed():
                                btn.click()
                                time.sleep(2)
                    except: pass
    
            except Exception as e:
                logger.error(f"Perform vote logic failed: {e}")
    
    def take_screenshots(self):
        self.change_state(State.SCREENSHOT)
        if self.current_user not in self.vote_info_list or not self.vote_info_list[self.current_user]:
            return

        logger.info(f"Taking screenshots for {self.current_user}")
        stocks_to_capture = list(self.vote_info_list[self.current_user])
        
        for stock_id in stocks_to_capture:
            match(self.capture_stock_screenshot(stock_id)):
                case 0: # success
                    self.vote_info_list[self.current_user].remove(stock_id)
                    self.write_vote_info_list()
                case 1: # failure, move to the end of the list for retry later
                    self.vote_info_list[self.current_user].remove(stock_id)
                    self.vote_info_list[self.current_user].append(stock_id)
                    self.write_vote_info_list()
                # case 2: eGift detected, skip without retry
            time.sleep(1)

    def capture_stock_screenshot(self, stock_id):
        try:
            self.driver.get("https://stockservices.tdcc.com.tw/evote/shareholder/000/tc_estock_welshas.html")
            wait = WebDriverWait(self.driver, 10)
            search_box = wait.until(EC.presence_of_element_located((By.NAME, 'qryStockId')))
            search_box.clear()
            search_box.send_keys(stock_id)
            self.driver.find_element(By.CSS_SELECTOR, 'a[onclick="qryByStockId();"]').click()
            time.sleep(2)

            # Find the record and click "Query/Modify"
            rows = self.driver.find_elements(By.TAG_NAME, 'tr')
            items = rows[1:-1] if len(rows) > 2 else rows[1:]
            
            # Sort by date (column 1) as in original
            try:
                items.sort(key=lambda x: x.find_elements(By.TAG_NAME, 'td')[1].text, reverse=True)
            except: pass

            found = False
            stock_name = "unknown"
            for row in items:
                if stock_id in row.text:
                    stock_name = row.text.split()[1].replace("*", "")
                    links = row.find_elements(By.TAG_NAME, 'a')
                    query_link = next((l for l in links if "查詢" in l.text), None)
                    if query_link:
                        query_link.click()
                        found = True
                        break
                    else:
                        logger.warning(f"Query link not found for stock {stock_id}.")
                        logger.debug(f"Row content: {row.text}")
                        return False
            
            if not found:
                logger.warning(f"Stock {stock_id} not found for screenshot.")
                return False

            # what is it?
            time.sleep(2)
            try: self.driver.find_element(By.ID, "msgDialog_okBtn").click()
            except: pass

            # resize for uniform screenshots
            self.driver.execute_script("document.body.style.zoom = '120%'")
            time.sleep(1)
            
            # Prepare filename based on mode
            account_id = "unknown"
            try:
                table_text = self.driver.find_element(By.TAG_NAME, 'table').text
                if "戶號" in table_text:
                    ###  TODO
                    # Very rough extraction, ideally use more specific selectors
                    account_id = table_text.split("戶號")[-1].split()[0]
            except: pass


            # adjust window size
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"{stock_id}_{stock_name}_{timestamp}.png"
            
            if self.screenshot_mode == 1:
                path = os.path.join(self.base_path, self.current_user)
                if not os.path.exists(path): os.makedirs(path)
                save_path = os.path.join(path, filename)
            else:
                path = os.path.join(self.base_path, "all")
                if not os.path.exists(path): os.makedirs(path)
                id_part = account_id if self.screenshot_mode == 2 else self.current_user
                filename = f"{stock_id}_{stock_name}_{id_part}_{timestamp}.png"
                save_path = os.path.join(path, filename)

            # check egift
            while(True):
                try:
                    # found barcode
                    self.driver.find_element(By.CSS_SELECTOR,'div[class="u-width--100 u-t_align--right"]')
                    tmp_cnt=0
                    break
                except:
                    try:
                        if self.driver.find_element(By.CSS_SELECTOR,'li.c-hint:nth-child(1)').get_property("innerText").find("eGift電子紀念品") != -1:
                            logger.info("eGift electronic souvenir detected, skipping screenshot.")
                            with open(os.path.join(path, "eGift_skipped.txt"), 'a', encoding='utf-8') as f:
                                if self.screenshot_mode == 1:
                                    f.write(f"{stock_id}\n")
                                else:
                                    f.write(f"{stock_id}_{account_id}_{self.current_user}\n")
                            # return 2
                            break
                    except:
                        tmp_cnt+=1
                        time.sleep(1)
                        if tmp_cnt%8==0:
                            logger.warning("Unhandled page layout, screenshot may be incorrect")
                            return 1
                        continue

            self.driver.save_screenshot(save_path)
            logger.info(f"Screenshot saved: {save_path}")

            self.driver.execute_script("document.body.style.zoom = '100%'")
            
            # Go back
            self.driver.execute_script("back();")
            return 0
        except Exception as e:
            logger.error(f"Screenshot failed for {stock_id}: {e}")
            return 1

    def write_program_setting(self):
        config_path = './program_setting.conf'
        try:
            content = f"{self.screenshot_mode}|/|{int(self.time_speed*2)}|/|{'@'.join(self.shareholder_ids)}"
            h = hashlib.sha256(content.encode()).hexdigest()
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(f"screenshot_mode:::{self.screenshot_mode}\n")
                f.write(f"time_speed:::{int(self.time_speed*2)}\n")
                f.write(f"shareholderIDs:::{'|/|'.join(self.shareholder_ids)}\n")
                f.write(f"hash:::{h}\n")
            logger.info("Program settings saved.")
        except Exception as e:
            logger.error(f"Failed to save program settings: {e}")

    def vi_program_setting(self):
        print("\n--- Program Setting Configuration ---")
        
        # Screenshot file structure
        print("Screenshot file structure:")
        print("1. Current structure (per user folder)")
        print("2. All in one, {stock_id}_{stock_name}_{account_id}.png")
        print("3. All in one, {stock_id}_{stock_name}_{user_id}.png")
        while True:
            m = input("Select screenshot file structure (1-3) [1]: ")
            if m in ['1', '2', '3']:
                break
        self.screenshot_mode = int(m)

        # set time speed
        print("Run speed: (default 2, smaller is faster)")
        print("set it larger if:")
        print("    - your computer is slow")
        print("    - your network is slow")
        print("    - the TDCC server thinks you are a robot")
        while True:
            s = input("Enter run speed (1-30, smaller is faster) [2]: ")
            if s.isdigit() and 1 <= int(s) <= 30:
                break
            if s == "": s = "2"
        self.time_speed = (int(s)) / 2

        # Set shareholder IDs
        print("Enter shareholder IDs (Taiwan citizen ID), one per line, 'end' to finish:")
        print("Example: A123456789")
        self.shareholder_ids = []
        while True:
            uid = input("> ").strip().upper()
            if uid == 'END': break
            if not uid: continue
            res = self.id_check(uid)
            if res == 0: self.shareholder_ids.append(uid)
            else: print(f"Invalid ID: {uid} (Error reason: { 'Format error' if res == 1 else 'Check digit error' if res == 2 else 'Unknown error' })")
        
        # print for confirmation
        print("\nCurrent Settings:")
        print(f"Screenshot Mode: {self.screenshot_mode}: {'Per user folders' if self.screenshot_mode == 1 else 'All in one with account ID' if self.screenshot_mode == 2 else 'All in one with user ID'}")
        print(f"Time Speed: {self.time_speed*2}")
        print(f"Shareholder IDs: {', '.join(self.shareholder_ids)}")
        while True:
            confirm = input("Is this correct? (y/n): ").lower()
            if confirm in ['y', 'n']:
                break
        if confirm == 'y':
            self.write_program_setting()
        else:
            print("Settings not saved. Please reconfigure.")
            return self.vi_program_setting()

    def write_vote_setting(self):
        config_path = './vote_setting.conf'
        self.vote_settings['manual_vote'] = any(self.vote_settings[a] for a in ['accept', 'opposite', 'abstain'])
        try:
            content = f"{self.vote_settings['default']}|/|{'#'.join(self.vote_settings['accept'])}|/|{'$'.join(self.vote_settings['opposite'])}|/|{'%'.join(self.vote_settings['abstain'])}|/|{self.vote_settings['manual_vote']}"
            h = hashlib.sha256(content.encode()).hexdigest()
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(f"default:::{self.vote_settings['default']}\n")
                f.write(f"accept:::{'|/|'.join(self.vote_settings['accept'])}\n")
                f.write(f"opposite:::{'|/|'.join(self.vote_settings['opposite'])}\n")
                f.write(f"abstain:::{'|/|'.join(self.vote_settings['abstain'])}\n")
                f.write(f"manual_vote:::{self.vote_settings['manual_vote']}\n")
                f.write(f"hash:::{h}\n")
            logger.info("Vote settings saved.")
        except Exception as e:
            logger.error(f"Failed to save vote settings: {e}")

    def vi_vote_setting(self):
        print("\n--- Vote Setting Configuration ---")
        d = input("Default vote option (accept/opposite/abstain) [abstain]: ").lower()
        self.vote_settings['default'] = d if d in ['accept', 'opposite', 'abstain'] else 'abstain'

        for action in ['accept', 'opposite', 'abstain']:
            print(f"Keywords to {action} (one per line, 'end' to finish):")
            self.vote_settings[action] = []
            while True:
                kw = input("> ").strip()
                if kw.lower() == 'end': break
                if kw: self.vote_settings[action].append(kw)
        
        self.vote_settings['manual_vote'] = any(self.vote_settings[a] for a in ['accept', 'opposite', 'abstain'])
        
        # check keywords do not overlap
        all_keywords = self.vote_settings['accept'] + self.vote_settings['opposite'] + self.vote_settings['abstain']
        if len(all_keywords) != len(set(all_keywords)):
            print("Error: Keywords cannot overlap between categories.")
            return self.vi_vote_setting()
        
        # default vote option cannot have keywords
        if self.vote_settings[self.vote_settings['default']]:
            self.vote_settings[self.vote_settings['default']] = []
            
        # print for confirmation
        print("\nCurrent Vote Settings:")
        print(f"Default Vote: {self.vote_settings['default']}")
        print(f"Accept Keywords: {', '.join(self.vote_settings['accept'])}")
        print(f"Opposite Keywords: {', '.join(self.vote_settings['opposite'])}")
        print(f"Abstain Keywords: {', '.join(self.vote_settings['abstain'])}")
        while True:
            confirm = input("Is this correct? (y/n): ").lower()
            if confirm in ['y', 'n']:
                break
        if confirm == 'y':
            self.write_vote_setting()
        else:
            print("Settings not saved. Please reconfigure.")
            return self.vi_vote_setting()

    def main_menu(self):
        while True:
            print("\n" + "="*30)
            print(" TDCC E-Vote Automation Tool")
            print("="*30)
            print("(1) All accounts: Vote + Screenshot")
            print("(2) Specific stocks: Take screenshots")
            ###  TODO
            print("(3) ALL stocks: Take screenshots")
            print("(4) Configure settings")
            print("(5) Exit")
            print("=" * 30)
            
            if self.args.yes: 
                choice = "1"
            else: 
                while True:
                    choice = input("Select an option: ").strip()
                    if choice in ['1', '2', '3', '4', '5']:
                        break
                    print("Invalid choice. Please enter a number between 1 and 5.")

            if choice == "1":
                if not self.shareholder_ids:
                    print("No shareholder IDs configured. Please configure first.")
                    self.vi_program_setting()
                    self.load_configs()
                    continue
                self.open_browser()
                for uid in self.shareholder_ids:
                    if self.login(uid):
                        self.auto_vote_process()
                        self.take_screenshots()
                        self.logout()
                if self.driver: 
                    self.driver.quit()
                if self.args.yes: 
                    break
            elif choice == "2":
                while True:
                    uid = input("Enter User ID: ").strip().upper()
                    if self.id_check(uid) == 0:
                        break
                    print("Invalid ID format. Please try again.")
                self.open_browser()
                if self.login(uid):
                    stocks = input("Enter stock IDs (comma separated): eg:2330,2634").split(",")
                    self.vote_info_list[uid] = [s.strip() for s in stocks if s.strip()]
                    self.take_screenshots()
                    self.logout()
                if self.driver:
                    self.driver.quit()
            elif choice == "3":
                raise NotImplementedError("Option 3 (ALL stocks screenshot) is not implemented yet.")
            elif choice == "4":
                self.vi_program_setting()
                self.vi_vote_setting()
            elif choice == "5":
                print("Exiting...")
                if self.driver: 
                    self.driver.quit()
                input("Press Enter to Exit...")
                os.remove("running.lock")
                sys.exit(0)
                break
            else:
                print("Invalid choice.")

    def generate_statement_html(self):
        html_content = '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>TDCC E-Vote Automation Tool</title>
        </head>
        <body>
            <h1>TDCC E-Vote Automation Tool</h1>
            <p>Version: 2026.5.26</p>
            <p>Author: DavidChou</p>
            <p>Repository: <a href="https://github.com/DavidChou23/TDCC_evote_helper">https://github.com/DavidChou23/TDCC_evote_helper</a> </p>
            <p>This script is only for assisting shareholders to complete the voting process in advance</p>
            <p>Voting content can be modified at any time without affecting the shareholder's intention</p>
            <p>This script is not responsible for any consequences caused by the use of this script</p>
            <br>
            <p><strong> please enter the command in the black control window. The voting content can be modified at any time without affecting the shareholder's intention</strong></p>
        </body>
        </html>
        '''
        try:
            with open('./statement.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info("Statement.html generated.")
        except Exception as e:
            logger.error(f"Failed to generate statement.html: {e}")

    def run(self):
        self.setup_workspace()
        self.generate_statement_html()
        
        # check if configs exist or force configure
        if not os.path.exists('./program_setting.conf'):
            self.vi_program_setting()
        if not os.path.exists('./vote_setting.conf'):
            self.vi_vote_setting()
        
        self.load_configs()
        
        # Check for unfinished tasks
        if self.vote_info_list:
            # while True:
            #     print("Unfinished screenshot tasks detected for the following users:")
            #     for uid, stocks in self.vote_info_list.items():
            #         print(f"User {uid}: {', '.join(stocks)}")
            #     choice = input("Do you want to complete them now? (y/n): ").lower()
            #     if choice in ['y', 'n']:
            #         break
            #     print("Invalid choice. Please enter 'y' or 'n'.")
            choice = 'y'   
            if self.args.yes or choice == 'y':
                self.open_browser()
                for uid in list(self.vote_info_list.keys()):
                    if self.login(uid):
                        self.take_screenshots()
                        self.logout()
                if self.driver: self.driver.quit()

        self.main_menu()
        self.change_state(State.FINISH)
        logger.info("Automation session ended.")

def parse_args():
    parser = argparse.ArgumentParser(description="TDCC evote and screenshot automation tool")
    parser.add_argument("-y", "--yes", action="store_true", help="No confirm mode(directly use existing configs)")
    parser.add_argument("-d", "--driver_path", type=str, help="Custom driver path")
    parser.add_argument("-b", "--browser", choices=["Edge", "Chrome", "Firefox"], default="Edge", help="Browser to use")
    return parser.parse_args()

if __name__ == "__main__":
    if os.path.exists("running.lock"):
        print("Another instance is already running. Please close it before starting a new one.")
        input("Press Enter to Exit...")
        sys.exit(1)

    with open("running.lock", "w") as f:
        f.write(str(os.getpid()))
    
    args = parse_args()
    bot = TDCCAutomation(args)
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
        if bot.driver: 
            bot.driver.quit()
            input("Press Enter to Exit...")
            os.remove("running.lock")
            sys.exit(1)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        if bot.driver: 
            bot.driver.quit()
        input("Press Enter to Exit...")
        os.remove("running.lock")
        sys.exit(1)
    finally:
        os.remove("running.lock")

