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
    """从 Playwright 上下文中提取 Cookie 给 requests 用"""
    cookies = context.cookies()
    cookie_dict = {}
    for c in cookies:
        cookie_dict[c['name']] = c['value']
    return cookie_dict

def get_filename_from_cd(cd):
    """从 Content-Disposition 头中提取文件名"""
    if not cd:
        return None
    # 尝试提取 filename="xxx" 或 filename*=utf-8''xxx
    fname = re.findall(r'filename="?([^"]+)"?', cd)
    if not fname:
        fname = re.findall(r"filename\*=utf-8''(.+)", cd)

    if fname:
        return unquote(fname[0]) # 解码 URL 编码的文件名
    return None

def download_file(url, cookie_dict, suggested_name=None):
    """
    智能下载文件
    1. 支持从 Header 获取真实文件名
    2. 支持自动推断后缀
    """
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    try:
        print(f"    ⬇️ 正在请求附件链接...")
        session = requests.Session()
        session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        session.cookies.update(cookie_dict)

        # 增加超时，流式下载
        res = session.get(url, stream=True, verify=False, timeout=60)

        # 🟢 [核心升级] 获取真实文件名
        final_filename = "unknown_file.dat"

        # 1. 优先尝试从响应头获取 (最准)
        server_filename = get_filename_from_cd(res.headers.get('Content-Disposition'))

        if server_filename:
            final_filename = server_filename
        elif suggested_name:
            # 2. 如果没给，用链接文字 (比如 "附件：xxx.doc")
            # 清洗文件名，去掉 "附件：" 和非法字符
            clean_name = re.sub(r'附件[：:]\s*', '', suggested_name).strip()
            clean_name = re.sub(r'[\\/*?:"<>|]', "", clean_name)
            if clean_name:
                final_filename = clean_name
                # 如果文字里没后缀，尝试补全
                if '.' not in final_filename:
                    ct = res.headers.get('Content-Type', '').split(';')[0]
                    ext = mimetypes.guess_extension(ct)
                    if ext: final_filename += ext

        # 构造保存路径
        save_path = os.path.join(TEMP_DIR, final_filename)

        # 避免覆盖
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
# 🧱 原子组件：解析逻辑
# ==========================================

def _extract_attachments(soup, base_url, cookie_dict):
    """
    提取并下载附件 (针对 JSP 动态链接优化)
    """
    files = []
    # 提取常规附件链接
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)

        full_link = urljoin(base_url, href)
        lower_link = full_link.lower()

        # 🟢 [核心升级] 判定规则
        # 规则1: 传统的静态文件后缀
        valid_exts = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar']
        is_static_file = any(x in lower_link for x in valid_exts)

        # 规则2: 动态下载链接 (针对你提供的 download.jsp)
        # 只要链接里包含 'download.jsp' 或者 'wbfileid'，不管有没有后缀，都算附件！
        is_dynamic_file = 'download.jsp' in lower_link or 'downloadattachurl' in lower_link or 'wbfileid' in lower_link

        if is_static_file or is_dynamic_file:
            # 过滤掉非文件链接 (如 mailto)
            if 'mailto:' in lower_link or 'javascript:' in lower_link: continue

            # 下载 (传入链接文字作为备选文件名)
            f_path = download_file(full_link, cookie_dict, suggested_name=text)
            if f_path: files.append(f_path)

    return files

def _process_html(html_content, base_url, cookie_dict):
    """处理 HTML 文本"""
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. 提取正文
    text = soup.get_text(separator='\n', strip=True)

    # 2. 提取附件
    files = _extract_attachments(soup, base_url, cookie_dict)

    return {
        "type": "compound",
        "text": text[:8000],
        "files": files
    }

# ==========================================
# 🚀 主入口 (Retry + Stealth)
# ==========================================

def fetch_content(url):
    """
    主抓取函数：使用 Playwright 加载页面
    """
    MAX_RETRIES = 3

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if attempt > 1:
                wait_time = random.uniform(2, 5) * attempt
                print(f"    ⏳ 网络波动，等待 {wait_time:.1f}s 后第 {attempt} 次尝试...")
                time.sleep(wait_time)

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False, # 保持有头模式防封
                    args=['--disable-blink-features=AutomationControlled']
                )

                if os.path.exists(STATE_FILE):
                    context = browser.new_context(
                        storage_state=STATE_FILE,
                        user_agent=DEFAULT_USER_AGENT
                    )
                else:
                    context = browser.new_context(user_agent=DEFAULT_USER_AGENT)

                context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                page = context.new_page()

                try:
                    page.goto(url, timeout=90000, wait_until="domcontentloaded")
                except PlaywrightError as e:
                    if "ERR_EMPTY_RESPONSE" in str(e) or "ERR_CONNECTION_RESET" in str(e):
                        print(f"    ⚠️ 连接被切断 ({e.message.split(' at ')[0]})...")
                        browser.close()
                        continue
                    else:
                        raise e

                page.wait_for_timeout(3000) # 多等一会

                if "404" in page.title() or "抱歉" in page.content():
                    print("    ❌ 页面 404 (State可能失效)")
                    browser.close()
                    return None

                if "login" in page.url:
                    print("    ❌ Cookie/State 已失效")
                    browser.close()
                    return None

                html = page.content()
                fresh_cookies = _get_playwright_cookies(context)
                browser.close()

                return _process_html(html, url, fresh_cookies)

        except Exception as e:
            print(f"    ❌ 第 {attempt} 次抓取失败: {e}")
            if attempt == MAX_RETRIES:
                return None

    return None