import os
import json
import requests
import mimetypes
import time
import random
import re
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
import urllib3
from playwright.sync_api import sync_playwright, Error as PlaywrightError
import logging
import sys

# 引用根目录配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 初始化模块级日志
logger = logging.getLogger(__name__)

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
COOKIE_FILE = os.path.join(DATA_DIR, "cookies.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
TEMP_DIR = os.path.join(DATA_DIR, "temp_files")

# 🟢 读取配置
HEADLESS = config.SPIDER.get("HEADLESS", True)
TIMEOUT = config.SPIDER.get("TIMEOUT", 60000)
DEFAULT_USER_AGENT = config.SPIDER.get("USER_AGENT", "Mozilla/5.0...")

# ==========================================
# 🔧 工具函数
# ==========================================

def _get_playwright_cookies(context):
    cookies = context.cookies()
    cookie_dict = {}
    for c in cookies:
        cookie_dict[c['name']] = c['value']
    return cookie_dict

def sanitize_filename(name):
    if not name: return None
    name = unquote(name)
    name = re.sub(r'[\\/*?:"<>|;]', "", name)
    name = name.replace("\n", "").replace("\r", "").strip()
    return name[:200]

def get_filename_from_cd(cd):
    if not cd: return None
    fname_utf8 = re.search(r"filename\*=utf-8''([^;]+)", cd, re.IGNORECASE)
    if fname_utf8: return unquote(fname_utf8.group(1))
    fname_quoted = re.search(r'filename="([^"]+)"', cd, re.IGNORECASE)
    if fname_quoted:
        name = fname_quoted.group(1)
        try: return name.encode('iso-8859-1').decode('utf-8')
        except: return name
    fname_simple = re.search(r'filename=([^;]+)', cd, re.IGNORECASE)
    if fname_simple:
        name = fname_simple.group(1).strip()
        try: return name.encode('iso-8859-1').decode('utf-8')
        except: return name
    return None

def download_file(url, cookie_dict, suggested_name=None):
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    try:
        logger.info(f"    ⬇️ 正在请求附件链接...")
        session = requests.Session()
        session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        session.cookies.update(cookie_dict)
        
        req_timeout = config.SPIDER.get("REQUEST_TIMEOUT", 60)
        res = session.get(url, stream=True, verify=False, timeout=req_timeout)
        
        final_filename = "unknown.dat"
        server_filename = get_filename_from_cd(res.headers.get('Content-Disposition'))
        if server_filename:
            final_filename = server_filename
        elif suggested_name:
            base_name = suggested_name
            if '.' not in base_name:
                ct = res.headers.get('Content-Type', '').split(';')[0]
                ext = mimetypes.guess_extension(ct)
                if ext: base_name += ext
            final_filename = base_name
        final_filename = sanitize_filename(final_filename)
        if not final_filename:
            final_filename = f"attach_{int(time.time())}.dat"
        save_path = os.path.join(TEMP_DIR, final_filename)
        if os.path.exists(save_path):
            name, ext = os.path.splitext(final_filename)
            final_filename = f"{name}_{int(time.time())}{ext}"
            save_path = os.path.join(TEMP_DIR, final_filename)
            
        chunk_size = config.SPIDER.get("CHUNK_SIZE", 8192)
        with open(save_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=chunk_size):
                f.write(chunk)
        logger.info(f"    ✅ 附件下载成功: {final_filename}")
        return save_path
    except Exception as e:
        logger.warning(f"    ⚠️ 下载失败: {e}")
        return None

def _extract_attachments(soup, base_url, cookie_dict):
    files = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        full_link = urljoin(base_url, href)
        valid_exts = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar']
        is_static = any(x in full_link.lower() for x in valid_exts)
        is_dynamic = 'download.jsp' in full_link or 'downloadattachurl' in full_link or 'wbfileid' in full_link
        if is_static or is_dynamic:
            if 'mailto:' in full_link.lower() or 'javascript:' in full_link.lower(): continue
            clean_text = re.sub(r'^附件[：:]\s*', '', text).strip()
            f_path = download_file(full_link, cookie_dict, suggested_name=clean_text)
            if f_path: files.append(f_path)
    return files

def _process_html(html_content, base_url, cookie_dict):
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text(separator='\n', strip=True)
    files = _extract_attachments(soup, base_url, cookie_dict)
    return {"type": "compound", "text": text[:8000], "files": files}

def _init_browser_context(p):
    # 🟢 使用配置中的 HEADLESS
    browser = p.chromium.launch(headless=HEADLESS, args=['--disable-blink-features=AutomationControlled'])
    if os.path.exists(STATE_FILE):
        context = browser.new_context(storage_state=STATE_FILE, user_agent=DEFAULT_USER_AGENT)
    else:
        context = browser.new_context(user_agent=DEFAULT_USER_AGENT)
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return browser, context

def _navigate_and_fetch(page, url, context):
    try:
        # 🟢 使用配置中的 TIMEOUT
        page.goto(url, timeout=TIMEOUT, wait_until="domcontentloaded")
    except PlaywrightError as e:
        if "ERR_EMPTY_RESPONSE" in str(e) or "ERR_CONNECTION_RESET" in str(e):
            logger.warning(f"    ⚠️ 连接被切断，指示重试...")
            return "RETRY"
        raise e
    
    wait_time = config.SPIDER.get("WAIT_AFTER_GOTO", 3000)
    page.wait_for_timeout(wait_time)
    
    if "404" in page.title() or "抱歉" in page.content():
        logger.error("    ❌ 页面 404")
        return "ABORT"
    if "login" in page.url:
        logger.error("    ❌ Cookie/State 已失效")
        return "ABORT"
    html = page.content()
    fresh_cookies = _get_playwright_cookies(context)
    return _process_html(html, url, fresh_cookies)

def _perform_single_attempt(url):
    with sync_playwright() as p:
        browser, context = _init_browser_context(p)
        page = context.new_page()
        try:
            result = _navigate_and_fetch(page, url, context)
            return result
        finally:
            browser.close()

def fetch_content(url):
    max_retries = config.SPIDER.get("MAX_RETRIES", 3)
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                delay_min = config.SPIDER.get("RANDOM_DELAY_MIN", 2)
                delay_max = config.SPIDER.get("RANDOM_DELAY_MAX", 5)
                wait_time = random.uniform(delay_min, delay_max) * attempt
                logger.info(f"    ⏳ 网络波动，等待 {wait_time:.1f}s...")
                time.sleep(wait_time)
            result = _perform_single_attempt(url)
            if result == "ABORT": return None
            if result == "RETRY": continue
            if result: return result
        except Exception as e:
            logger.error(f"    ❌ 第 {attempt} 次抓取失败: {e}")
            if attempt == max_retries: return None
    return None
