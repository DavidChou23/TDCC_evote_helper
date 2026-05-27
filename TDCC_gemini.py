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
import json

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


if not os.path.exists("./log"):
    os.makedirs("./log")
# Configure Logging(with line numbers and timestamps)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s:%(lineno)d] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'./log/tdcc_automation_{datetime.datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8')
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
        self.tmp_download_path = "./tmp_downloads_tdcc_evote_helper/"
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
        if not os.path.exists(self.tmp_download_path):
            os.makedirs(self.tmp_download_path)
            logger.info(f"Created temp download path: {self.tmp_download_path}")
        
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
    
    def check_login_as(self, user_id):
        assert self.driver is not None, "WebDriver is not initialized for login check."
        #debug
        # assert user_id==self.current_user, f"check_login_as called with user_id {user_id} but current_user is {self.current_user}"
        if user_id is None:
            return False

        #open a temp new tab to check if already logged in as user_id
        logger.info(f"Checking if already logged in as {user_id}")
        # self.driver.execute_script("window.open('');")
        # self.driver.switch_to.window(self.driver.window_handles[-1])
        # self.driver.get("https://stockservices.tdcc.com.tw/evote/login/shareholder.html?language=TW")
        # # wait for page load
        # try:
        #     WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, 'html')))
        # except TimeoutException:
        #     logger.error("Failed to load login page.")
        #     return
        
        #check is it in page_source(exclude any "input" tag)
        filtered_source = self.driver.page_source
        for tag_name in ['input', 'textarea', 'select']:
            for tag in self.driver.find_elements(By.TAG_NAME, tag_name):
                filtered_source = filtered_source.replace(tag.get_attribute('outerHTML'), '')
        if str(user_id) in filtered_source:
            logger.info(f"Already logged in as {user_id}.")
            self.current_user = user_id
            # self.driver.close()
            # self.driver.switch_to.window(self.driver.window_handles[0])
            return True
        # self.driver.close()
        # self.driver.switch_to.window(self.driver.window_handles[0])
        return False
        
        
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
            content = f"{data.get('screenshot_mode', '1')}|/|{str(float(data.get('time_speed', '2')))}|/|{'@'.join(data.get('shareholderIDs', '').split('|/|'))}"
            if hashlib.sha256(content.encode()).hexdigest() != stored_hash:
                logger.error("program_setting.conf hash mismatch!")
                print(content)
                logger.info(f"Expected hash: {stored_hash}")
                logger.info(f"Actual hash: {hashlib.sha256(content.encode()).hexdigest()}")
                # rename corrupted config for backup
                if os.path.exists(config_path+".bak"):
                    os.remove(config_path+".bak")
                os.rename(config_path, config_path + ".bak")
                logger.warning("Corrupted program_setting.conf has been renamed to program_setting.conf.bak. Please reconfigure settings.")
                self.exit(1)

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
                logger.debug(f"Expected hash: {stored_hash}")
                logger.debug(f"Actual hash: {hashlib.sha256(content.encode()).hexdigest()}")
                # rename corrupted config for backup
                if os.path.exists(config_path+".bak"):
                    os.remove(config_path+".bak")
                os.rename(config_path, config_path + ".bak")
                logger.warning("Corrupted vote_setting.conf has been renamed to vote_setting.conf.bak. Please reconfigure settings.")
                self.exit(1)

            self.vote_settings['default'] = data.get('default', 'abstain')
            self.vote_settings['manual_vote'] = data.get('manual_vote') == 'True'
            self.vote_settings['accept'] = [k for k in data.get('accept', '').split('|/|') if k]
            self.vote_settings['opposite'] = [k for k in data.get('opposite', '').split('|/|') if k]
            self.vote_settings['abstain'] = [k for k in data.get('abstain', '').split('|/|') if k]
            logger.info("Loaded vote settings.")
        except Exception as e:
            logger.error(f"Error reading vote settings: {e}")
    def read_voteinfolist_old(self, file_full_path):
        # for compatibility with old version, used to change file structure from txt to json
        file_full_path = file_full_path.replace("\\\\","\\").replace("\\","/")  # windows path compatibility
        assert os.path.exists(file_full_path), f"File not found: {file_full_path}"
        user_id = str(os.path.dirname(file_full_path).split("/")[-1])
        assert self.id_check(user_id) == 0, f"Invalid user ID: {user_id}"

        with open(file_full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                stock_id = line.strip()
                if stock_id not in self.vote_info_list:
                    try:
                        self.vote_info_list[user_id].append(stock_id)
                    except AttributeError:
                        if(self.debug>=3):
                            print(self.vote_info_list)
                            print(user_id, stock_id)
                        self.vote_info_list[user_id] = [stock_id]
                    except KeyError:
                        self.vote_info_list[user_id] = [stock_id]
    
    def read_vote_info_list(self):
        path = f"{self.base_path}/incomplete_screenshot_list.json"
        #file is empty
        if os.path.getsize(path) == 0:
            self.vote_info_list = {}
            return
        
        #file exists
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                self.vote_info_list = json.load(f)
        # compatibility with old version, if there are any folders with incomplete_screenshot_list.txt, read them and convert to json format, then delete the txt files
        ## list all file named incomplete_screenshot_list.txt in base_path and subfolders
        txt_files = []
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                if file == "incomplete_screenshot_list.txt" or file == "imcomplele_screenshot_list.txt":
                    txt_files.append(os.path.join(root, file))
        for txt_file in txt_files:
            try:
                logger.info(f"Converting old format: {txt_file}")
                self.read_voteinfolist_old(txt_file)
                os.remove(txt_file)
                self.write_vote_info_list()  # write after each file to ensure data is not lost if there are many files
                logger.info(f"Converted old format and removed: {txt_file}")
            except Exception as e:
                logger.error(f"Error converting old format for {txt_file}: {e}")

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

    def open_browser(self):
        self.change_state(State.INITIALIZING)
        browser_type = self.args.browser
        driver_path = self.args.driver_path
        if self.driver!= None:
            logger.warning("WebDriver is already initialized. Skipping browser initialization.")
            return
        def build_browser_options(browser_name: str):
            download_dir = os.path.abspath(self.tmp_download_path)
            if browser_name in ("Edge", "Chrome"):
                options = webdriver.EdgeOptions() if browser_name == "Edge" else webdriver.ChromeOptions()
                prefs = {
                    "download.default_directory": download_dir,
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "safebrowsing.enabled": True,
                }
                options.add_experimental_option("prefs", prefs)
                return options

            if browser_name == "Firefox":
                from selenium.webdriver.firefox.options import Options

                options = Options()
                options.set_preference("browser.download.folderList", 2)
                options.set_preference("browser.download.dir", download_dir)
                options.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv,application/csv,text/plain,application/octet-stream")
                options.set_preference("pdfjs.disabled", True)
                return options

            return None

        try:
            # First try the specified driver path if provided
            if driver_path!= None:
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
                    
                    self.driver = webdriver.Edge(service=Service(driver_path), options=build_browser_options("Edge"))
                    logger.info("Using Edge WebDriver from specified path.")
                    return
                elif 'Firefox' in res.stdout:
                    from selenium.webdriver.firefox.service import Service
                    self.driver = webdriver.Firefox(service=Service(driver_path), options=build_browser_options("Firefox"))
                    logger.info("Using Firefox WebDriver from specified path.")
                    return
                elif 'chrome' in res.stdout:
                    from selenium.webdriver.chrome.service import Service
                    self.driver = webdriver.Chrome(service=Service(driver_path), options=build_browser_options("Chrome"))
                    logger.info("Using Chrome WebDriver from specified path.")
                    return
                else:
                    logger.warning("Could not detect driver type from help output. Falling back to default logic.")
                    driver_path = None
            # no valid driver from path, try based on browser type
            if browser_type=="Edge":
                self.driver = webdriver.Edge(options=build_browser_options("Edge"))
                logger.info("Using Edge WebDriver.")
                return
            elif browser_type=="Firefox":
                self.driver = webdriver.Firefox(options=build_browser_options("Firefox"))
                logger.info("Using Firefox WebDriver.")
                return
            elif browser_type=="Chrome":
                self.driver = webdriver.Chrome(options=build_browser_options("Chrome"))
                logger.info("Using Chrome WebDriver.")
                return
            raise Exception("Failed to initialize specified browser. Falling back to default logic.")
        # Default logic
        except Exception as e:
            logger.warning(f"Failed to open specific browser: {e}. Trying fallbacks...")
            for fallback_name, fallback in [("Edge", webdriver.Edge), ("Firefox", webdriver.Firefox), ("Chrome", webdriver.Chrome)]:
                try:
                    self.driver = fallback(options=build_browser_options(fallback_name))
                    logger.info(f"Using {fallback.__name__} WebDriver as fallback.")
                    break
                except: 
                    logger.warning(f"Failed to initialize {fallback.__name__} WebDriver. Trying next fallback...")
                    continue
        
        if not self.driver:
            logger.critical("Failed to initialize any WebDriver.")
            self.exit(1)
        
        logger.info("WebDriver initialized successfully.")
        return
    
    def cleanup(self):
        if self.driver:
            self.logout()
            self.driver.quit()
            self.driver = None
            logger.info("WebDriver closed.")
        # Clean up temp download files
        try:
            for f in os.listdir(self.tmp_download_path):
                logger.info(f"Removing temporary file: {f}")
                os.remove(os.path.join(self.tmp_download_path, f))
            try:
                os.rmdir(self.tmp_download_path)
            #not exist
            except FileNotFoundError: pass
            except OSError as e:
                logger.error(f"Error removing temporary directory: {e}")
            logger.info("Cleaned up temporary download files.")
            try:
                os.remove("./statement.html")
            except FileNotFoundError: pass
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def exit(self, code=0):
        self.cleanup()
        if self.args.yes:
            logger.info("Auto-exit enabled, exiting immediately.")
            sys.exit(code)
        input("Press Enter to Exit...")
        assert os.path.exists("running.lock"), "running.lock not found during exit. This may indicate an unexpected state."
        os.remove("running.lock")
        logger.info("Exiting program.")
        if code != 0:
            logger.error(f"Exiting with error code: {code}")
            # log calling stack for debugging
            import traceback
            logger.error("Stack trace at exit:\n" + traceback.format_exc())
        else:
            logger.info("Exiting successfully.")
        sys.exit(0)

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

        if self.check_login_as(user_id):
            logger.info(f"Already logged in as {user_id}.")
            self.current_user = user_id
            self.change_state(State.LOGIN)
            return True
        
        # Reset session
        if self.current_user is not None:
            self.logout()

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
                self.exit(1)
                
            # Check for "Agree" button
            try:
                agree_btn = self.driver.find_element(By.CSS_SELECTOR, 'a.btnAgree, a[name="btn1"]')
                if agree_btn.is_displayed():
                    self.show_msg("Please read and agree to the terms", 5, "Proceeding...")
                    time.sleep(5)
                    agree_btn.click()
                    logger.info("Clicked Agree button.")
            except: pass
            
            # 本次為重複登入或前次未能正常登出， 按下【確定】，將自動關閉前次連線， 並正常登入系統。
            try:
                self.driver.find_element(By.ID,"comfirmDialog_okBtn").click()
                time.sleep(5*self.time_speed)
            except:
                pass

            # Check if logged in (redirected to main or list page)
            # if "tc_estock_welshas" in self.driver.current_url:
            if self.check_login_as(user_id):
                logger.info("Login successful.")
                self.current_user = user_id
                self.change_state(State.LOGIN)
                return True
        
        logger.error("Login timeout.")
        return False

    def logout(self):
        try:
            self.driver.get("https://stockservices.tdcc.com.tw/evote/logout.html")
            logger.info("Logged out successfully.")
            self.driver.delete_all_cookies()
            self.change_state(State.LOGOUT)
            self.current_user = None
        except Exception as e:
            logger.error(f"Error during logout: {e}")
            assert self.check_login_as(self.current_user) == False, "Logout failed, still logged in as current user."

    def auto_vote_process(self):
        self.change_state(State.VOTING)
        assert self.current_user is not None, "Current user is not set for voting process."
        assert self.check_login_as(self.current_user), "Not logged in as the expected user for voting process."
        
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
                    self.exit(1)
                
                if "系統操作逾時" in self.driver.page_source:
                    logger.warning("Session timeout detected during voting. Please restart the program and try again.")
                    self.exit(1)

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
        assert self.check_login_as(self.current_user), "Not logged in as the expected user for performing vote logic."
        
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
                self.exit(1)

            if "系統維護中" in self.driver.page_source:
                logger.error("System Maintenance detected during voting.")
                self.exit(1)

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
                        logger.warning("Unknown voting page type.")
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
    def get_all_screenshotable_stocks(self, user_id):
        assert self.check_login_as(user_id), "Not logged in as the expected user for getting screenshotable stocks."
        
        self.change_state(State.SCREENSHOT)
        self.driver.get("https://stockservices.tdcc.com.tw/evote/shareholder/000/tc_estock_welshas.html")
        #wait for page load(html)
        try:
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, 'html')))
        except TimeoutException:
            logger.error("Failed to load page for fetching screenshotable stocks.")
            return self.get_all_screenshotable_stocks(user_id)  # Retry loading the page
        
        #get csv download link(//div[@id='downloadMeetingList']/a)
        link = self.driver.find_element(By.XPATH, "//div[@id='downloadMeetingList']/a")
        #download csv content(click the link and wait for download to complete)
        link.click()
        time.sleep(10)
        #find the latest downloaded csv file in tmp_download_path and check created time to ensure it's the correct file
        csv_file = None
        dir_list = os.listdir(self.tmp_download_path)
        # filter csv files and sort by created time
        csv_files = [f for f in dir_list if f.endswith('.csv')]
        if not csv_files:
            logger.error("No CSV file found in download directory.")
            # retry
            return self.get_all_screenshotable_stocks(user_id)
        csv_files.sort(key=lambda x: os.path.getctime(os.path.join(self.tmp_download_path, x)), reverse=True)
        # check abs time in 5 minutes to ensure it's the correct file
        latest_file = csv_files[0]
        latest_file_path = os.path.join(self.tmp_download_path, latest_file)
        if (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getctime(latest_file_path))).total_seconds() > 300:
            logger.error("No recent CSV file found in download directory.")
            # retry
            return self.get_all_screenshotable_stocks(user_id)
        csv_file = latest_file
        logger.info(f"Found CSV file: {csv_file}")
        # read and parse the csv file to get stock ids with columnG"已投票"
        stocks = []
        import csv
        with open(os.path.join(self.tmp_download_path, csv_file), 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row[6].strip() == "已投票":
                    stocks.append(row[0].strip())
        logger.info(f"Screenshotable stocks for {user_id}: {stocks}")
        self.vote_info_list[user_id].extend(stocks)
        self.write_vote_info_list()
        return


    def take_screenshots(self,user_id=None):
        assert self.check_login_as(user_id), "Not logged in as the expected user for taking screenshots."
        
        self.change_state(State.SCREENSHOT)
        if user_id not in self.vote_info_list or not self.vote_info_list[user_id]:
            return

        logger.info(f"Taking screenshots for {user_id}")
        stocks_to_capture = list(self.vote_info_list[user_id])
        if not stocks_to_capture:
            logger.info("No stocks to capture for screenshots.")
            return

        for stock_id in stocks_to_capture:
            match(self.capture_stock_screenshot(stock_id)):
                case 0: # success
                    self.vote_info_list[user_id].remove(stock_id)
                    self.write_vote_info_list()
                case 1: # failure, move to the end of the list for retry later
                    self.vote_info_list[user_id].remove(stock_id)
                    self.vote_info_list[user_id].append(stock_id)
                    self.write_vote_info_list()
                # case 2: eGift detected, skip without retry
            time.sleep(1)

    def capture_stock_screenshot(self, stock_id):
        assert self.check_login_as(self.current_user), "Not logged in as the expected user for capturing screenshots."
        
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
            eGift = None
            for row in items:
                if stock_id in row.text:
                    stock_name = row.text.split()[1].replace("*", "")
                    links = row.find_elements(By.TAG_NAME, 'a')
                    query_link = next((l for l in links if "查詢" in l.text), None)
                    if query_link:
                        if "Y" in row.find_element(By.XPATH, './/td[4]').text:
                            eGift = row.find_element(By.XPATH, './/td[4]').text.split("Y")[1].strip()
                            logger.info(f"eGift electronic souvenir detected for stock {stock_id}. Will check inside before screenshot.")
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
                # wait for table to load
                wait = WebDriverWait(self.driver, 10)
                table = wait.until(EC.presence_of_element_located((By.XPATH, '//table[0]//tr')))
                for row in table:
                    if "戶號" in row.text:
                        account_id = row.find_element(By.XPATH, '//td').text.strip()
                        break
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

            #eGift
            if eGift!= None:
                #change screenshot filename
                filename = f"eGift_{filename}"
                save_path = os.path.join(path, filename)
                
                # add eGift info to filename and save to eGift list
                with open(os.path.join(path, f"eGifts_{datetime.datetime.now().strftime('%Y')}.txt"), 'a', encoding='utf-8') as f:
                    if self.screenshot_mode == 1:
                        f.write(f"{stock_id}_{eGift}\n")
                    else:
                        f.write(f"{stock_id}_{account_id}_{self.current_user}_{eGift}\n")
            # # check egift
            # while(True):
            #     try:
            #         # found barcode
            #         self.driver.find_element(By.CSS_SELECTOR,'div[class="u-width--100 u-t_align--right"]')
            #         tmp_cnt=0
            #         break
            #     except:
            #         try:
            #             if self.driver.find_element(By.CSS_SELECTOR,'li.c-hint:nth-child(1)').get_property("innerText").find("eGift電子紀念品") != -1:
            #                 logger.info("eGift electronic souvenir detected, skipping screenshot.")
            #                 with open(os.path.join(path, "eGift_skipped.txt"), 'a', encoding='utf-8') as f:
            #                     if self.screenshot_mode == 1:
            #                         f.write(f"{stock_id}\n")
            #                     else:
            #                         f.write(f"{stock_id}_{account_id}_{self.current_user}\n")
            #                 # return 2
            #                 break
            #         except:
            #             tmp_cnt+=1
            #             time.sleep(1)
            #             if tmp_cnt%8==0:
            #                 logger.warning("Unhandled page layout, screenshot may be incorrect")
            #                 return 1
            #             continue

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
            content = f"{self.screenshot_mode}|/|{float(self.time_speed*2)}|/|{'@'.join(self.shareholder_ids)}"
            logger.info(f"Writing program settings with content: {content}")
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
        if self.args.yes:
            logger.info("Auto-confirm mode is enabled. Shouldn't be configuring program settings interactively. Exiting.")
            self.exit(1)
        print("\n--- Program Setting Configuration(User Settings) ---")
        if os.path.exists('./program_setting.conf'):
            print("Existing program settings found. Do you want to reconfigure? (y/n) [n]: ")
            while True:
                m = input().lower()
                if m in ['y', 'n', '']:
                    break
            if m == 'n' or m == '':
                logger.info("Keeping existing program settings.")
                return
        # Screenshot file structure
        print("--------------------- Screenshot file structure:  ------------------------------")
        print("1. Current structure (per user folder)")
        print("2. All in one, {stock_id}_{stock_name}_{account_id}.png")
        print("3. All in one, {stock_id}_{stock_name}_{user_id}.png")
        while True:
            m = input("Select screenshot file structure (1-3) [1]: ")
            if m in ['1', '2', '3']:
                break
        self.screenshot_mode = int(m)

        # set time speed
        print("--------------------- Run Speed Configuration:  ------------------------------")
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
        print("--------------------- Shareholder IDs Configuration:  ------------------------------")
        print("Enter shareholder IDs (Taiwan citizen ID), one per line, 'end' to finish:")
        print("Example: A123456789")
        self.shareholder_ids = []
        while True:
            uid = input("> ").strip().upper()
            if uid == 'END': 
                if not self.shareholder_ids:
                    print("At least one shareholder ID is required.")
                    continue
                else: 
                    break
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
            # logger.info(content)
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
        if self.args.yes:
            logger.info("Auto-confirm mode is enabled. Shouldn't be configuring vote settings interactively. Exiting.")
            self.exit(1)
        
        if os.path.exists('./vote_setting.conf'):
            print("Existing vote settings found. Do you want to reconfigure? (y/n) [n]: ")
            while True:
                m = input().lower()
                if m in ['y', 'n', '']:
                    break
            if m == 'n' or m == '':
                logger.info("Keeping existing vote settings.")
                return
    
        print("\n--------------------- Vote Setting Configuration:  ------------------------------")
        d = input("Default vote option (accept/opposite/abstain) [abstain]: ").lower()
        self.vote_settings['default'] = d if d in ['accept', 'opposite', 'abstain'] else 'abstain'

        for action in ['accept', 'opposite', 'abstain']:
            print(f"\n--------------------- Manual vote keywords for '{action}' option:  ------------------------------")
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
                    logger.error("No shareholder IDs configured. Please configure first.")
                    self.vi_program_setting()
                    self.load_configs()
                    continue
                self.open_browser()
                for uid in self.shareholder_ids:
                    if self.login(uid):
                        self.auto_vote_process()
                        self.take_screenshots(uid)
                        self.logout()
                self.exit(0)

            elif choice == "2":
                while True: # for different users
                    while True:
                        uid = input("Enter User ID one per time(End to exit): ").strip().upper()
                        if uid.upper() == "END":
                            return
                        if self.id_check(uid) != 0:
                            print("Invalid ID format. Please try again.")
                            continue
                        break
                    self.open_browser()
                    if self.current_user!=None and self.current_user!=uid:
                        self.logout()
                    if self.login(uid):
                        stocks = input("Enter stock IDs (comma separated): eg:2330,2634").split(",")
                        self.vote_info_list[uid] = [s.strip() for s in stocks if s.strip()]
                        self.take_screenshots(uid)
            elif choice == "3":
                while True: # for different users
                    while True:
                        uid = input("Enter User ID one per time(End to exit): ").strip().upper()
                        if uid.upper() == "END":
                            return
                        if self.id_check(uid) != 0:
                            print("Invalid ID format. Please try again.")
                            continue
                        break
                    self.open_browser()
                    if self.current_user!=None and self.current_user!=uid:
                        self.logout()
                    if self.login(uid):
                        self.get_all_screenshotable_stocks(uid)
                        self.take_screenshots(uid)
            elif choice == "4":
                self.vi_program_setting()
                self.vi_vote_setting()
            elif choice == "5":
                print("Exiting...")
                self.exit(0)
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
                    if not self.vote_info_list[uid]:  # only attempt if there are pending stocks
                        continue
                    if self.login(uid):
                        self.take_screenshots(uid)
                        self.logout()

        self.main_menu()
        self.cleanup()
        self.change_state(State.FINISH)
        logger.info("Automation session ended.")
        self.exit(0)

def parse_args():
    parser = argparse.ArgumentParser(description="TDCC evote and screenshot automation tool")
    parser.add_argument("-y", "--yes", action="store_true", help="No confirm mode(directly use existing configs)")
    parser.add_argument("-d", "--driver_path", type=str, help="Custom driver path")
    parser.add_argument("-b", "--browser", choices=["Edge", "Chrome", "Firefox"], default="Edge", help="Browser to use")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    if os.path.exists("running.lock"):
        #if the previous process is terminated but the lock file still exists, check if the process is still running by checking the pid in the lock file
        with open("running.lock", "r") as f:
            pid = int(f.read())
        # get process name by pid
        import psutil
        try:
            process = psutil.Process(pid)
            if process.is_running() and any(keyword in process.name() for keyword in ["python", "python3","TDCC"]):
                logger.warning(f"Another instance (PID: {pid}) is still running.")
                if args.yes:
                    sys.exit(1)
                input("Press Enter to Exit...")
                sys.exit(1)
            else:
                logger.warning(f"Stale lock file detected. Previous process (PID: {pid}) is not running. Removing lock file.")
                if process.is_running():
                    # log it's name for debugging
                    logger.warning(f"Process with PID {pid} is running but does not seem to be a TDCC automation process. Process name: {process.name()}. Removing lock file.")
                os.remove("running.lock")
        except psutil.NoSuchProcess:
            logger.warning(f"Stale lock file detected. Previous process (PID: {pid}) is not running. Removing lock file.")
            os.remove("running.lock")

    with open("running.lock", "w") as f:
        f.write(str(os.getpid()))
    
    bot = TDCCAutomation(args)
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
        bot.exit(1)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        bot.exit(1)

    finally:
        if os.path.exists("running.lock"):
            os.remove("running.lock")

