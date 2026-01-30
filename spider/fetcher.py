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

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
COOKIE_FILE = os.path.join(DATA_DIR, "cookies.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
TEMP_DIR = os.path.join(DATA_DIR, "temp_files")

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ==========================================
# 🔧 工具函数
# ==========================================

def _get_playwright_cookies(context):
    """从 Playwright 上下文中提取 Cookie"""
    cookies = context.cookies()
    cookie_dict = {}
    for c in cookies:
        cookie_dict[c['name']] = c['value']
    return cookie_dict

def sanitize_filename(name):
    """清洗文件名，移除非法字符"""
    if not name: return None
    name = unquote(name)
    name = re.sub(r'[\\/*?:"<>|;]', "", name)
    name = name.replace("\n", "").replace("\r", "").strip()
    return name[:200]

def get_filename_from_cd(cd):
    """从 Content-Disposition 头中提取文件名"""
    if not cd: return None

    # 1. 优先尝试 filename*=utf-8''xxx
    fname_utf8 = re.search(r"filename\*=utf-8''([^;]+)", cd, re.IGNORECASE)
    if fname_utf8:
        return unquote(fname_utf8.group(1))

    # 2. 其次尝试 filename="xxx"
    fname_quoted = re.search(r'filename="([^"]+)"', cd, re.IGNORECASE)
    if fname_quoted:
        name = fname_quoted.group(1)
        try: return name.encode('iso-8859-1').decode('utf-8')
        except: return name

    # 3. 最后尝试 filename=xxx
    fname_simple = re.search(r'filename=([^;]+)', cd, re.IGNORECASE)
    if fname_simple:
        name = fname_simple.group(1).strip()
        try: return name.encode('iso-8859-1').decode('utf-8')
        except: return name

    return None

def download_file(url, cookie_dict, suggested_name=None):
    """智能下载文件"""
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    try:
        print(f"    ⬇️ 正在请求附件链接...")
        session = requests.Session()
        session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        session.cookies.update(cookie_dict)

        res = session.get(url, stream=True, verify=False, timeout=60)

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

        with open(save_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"    ✅ 附件下载成功: {final_filename}")
        return save_path
    except Exception as e:
        print(f"    ⚠️ 下载失败: {e}")
        return None

# ==========================================
# 🧱 原子组件：内容解析
# ==========================================

def _extract_attachments(soup, base_url, cookie_dict):
    """提取附件链接"""
    files = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        full_link = urljoin(base_url, href)
        lower_link = full_link.lower()

        valid_exts = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar']
        is_static = any(x in lower_link for x in valid_exts)
        is_dynamic = 'download.jsp' in lower_link or 'downloadattachurl' in lower_link or 'wbfileid' in lower_link

        if is_static or is_dynamic:
            if 'mailto:' in lower_link or 'javascript:' in lower_link: continue
            clean_text = re.sub(r'^附件[：:]\s*', '', text).strip()
            f_path = download_file(full_link, cookie_dict, suggested_name=clean_text)
            if f_path: files.append(f_path)
    return files

def _process_html(html_content, base_url, cookie_dict):
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text(separator='\n', strip=True)
    files = _extract_attachments(soup, base_url, cookie_dict)
    return {
        "type": "compound",
        "text": text[:8000],
        "files": files
    }

# ==========================================
# 🧱 原子组件：浏览器操作 (拆分降维)
# ==========================================

def _init_browser_context(p):
    """原子任务：启动浏览器并加载状态"""
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )

    if os.path.exists(STATE_FILE):
        context = browser.new_context(storage_state=STATE_FILE, user_agent=DEFAULT_USER_AGENT)
    else:
        context = browser.new_context(user_agent=DEFAULT_USER_AGENT)

    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return browser, context

def _navigate_and_fetch(page, url, context):
    """原子任务：页面导航与抓取"""
    try:
        page.goto(url, timeout=90000, wait_until="domcontentloaded")
    except PlaywrightError as e:
        if "ERR_EMPTY_RESPONSE" in str(e) or "ERR_CONNECTION_RESET" in str(e):
            print(f"    ⚠️ 连接被切断，指示重试...")
            return "RETRY"
        raise e

    page.wait_for_timeout(3000)

    if "404" in page.title() or "抱歉" in page.content():
        print("    ❌ 页面 404")
        return "ABORT"

    if "login" in page.url:
        print("    ❌ Cookie/State 已失效")
        return "ABORT"

    html = page.content()
    fresh_cookies = _get_playwright_cookies(context)
    return _process_html(html, url, fresh_cookies)

def _perform_single_attempt(url):
    """执行单次抓取任务"""
    with sync_playwright() as p:
        browser, context = _init_browser_context(p)
        page = context.new_page()
        try:
            result = _navigate_and_fetch(page, url, context)
            return result
        except Exception as e:
            raise e
        finally:
            browser.close()

# ==========================================
# 🚀 主入口 (重构后复杂度极低)
# ==========================================

def fetch_content(url):
    """主调度函数：只负责重试逻辑"""
    MAX_RETRIES = 3

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if attempt > 1:
                wait_time = random.uniform(2, 5) * attempt
                print(f"    ⏳ 网络波动，等待 {wait_time:.1f}s...")
                time.sleep(wait_time)

            result = _perform_single_attempt(url)

            if result == "ABORT":
                return None
            if result == "RETRY":
                continue
            if result:
                return result

        except Exception as e:
            print(f"    ❌ 第 {attempt} 次抓取失败: {e}")
            if attempt == MAX_RETRIES: return None

    return None