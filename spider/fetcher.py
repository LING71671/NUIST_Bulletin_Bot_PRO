import os
import json
import requests
import mimetypes
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import urllib3
from playwright.sync_api import sync_playwright

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
COOKIE_FILE = os.path.join(DATA_DIR, "cookies.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json") # 🟢 必须加载这个！
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

def download_file(url, cookie_dict):
    """使用 requests 下载文件"""
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    try:
        print(f"    ⬇️ 下载附件: {url.split('/')[-1][:20]}...")
        session = requests.Session()
        session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        session.cookies.update(cookie_dict)

        res = session.get(url, stream=True, verify=False, timeout=60)

        content_type = res.headers.get('Content-Type', '').split(';')[0]
        ext = mimetypes.guess_extension(content_type) or ".dat"
        if '.' in url.split('/')[-1]:
            ext = '.' + url.split('/')[-1].split('.')[-1]

        filename = f"attach_{datetime.now().strftime('%H%M%S_%f')}{ext}"
        path = os.path.join(TEMP_DIR, filename)

        with open(path, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
        return path
    except Exception as e:
        print(f"    ⚠️ 下载失败: {e}")
        return None

# ==========================================
# 🧱 原子组件：解析逻辑
# ==========================================

def _extract_attachments(soup, base_url, cookie_dict):
    """提取并下载附件"""
    files = []
    # 提取常规附件链接
    for a in soup.find_all('a', href=True):
        href = a['href']
        full_link = urljoin(base_url, href)
        lower_link = full_link.lower()

        valid_exts = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar']

        if any(x in lower_link for x in valid_exts):
            if 'mailto:' in lower_link or 'javascript:' in lower_link: continue
            f_path = download_file(full_link, cookie_dict)
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
        "text": text[:8000], # 增大上下文
        "files": files
    }

# ==========================================
# 🚀 主入口 (Playwright + State注入 + 隐身)
# ==========================================

def fetch_content(url):
    """
    主抓取函数：使用 Playwright 加载页面
    已加入反爬虫对抗参数，并强制注入 State
    """
    try:
        with sync_playwright() as p:
            # 1. 启动浏览器 (关闭无头，启用隐身)
            browser = p.chromium.launch(
                headless=False, # 必须有头，否则 VPN 会拦截
                args=['--disable-blink-features=AutomationControlled']
            )

            # 2. 🟢 核心修复：加载完整的 State (Cookies + LocalStorage)
            if os.path.exists(STATE_FILE):
                # print(f"    📂 [Fetcher] 加载身份凭证: {STATE_FILE}")
                context = browser.new_context(
                    storage_state=STATE_FILE,
                    user_agent=DEFAULT_USER_AGENT
                )
            else:
                print("    ⚠️ 严重警告: 身份凭证丢失，可能导致 404！")
                context = browser.new_context(user_agent=DEFAULT_USER_AGENT)

            # 3. 注入防检测脚本 (双重保险)
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            page = context.new_page()

            # 4. 访问页面
            # print(f"    🔗 正在加载详情页...")
            page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # 5. 等待内容加载 (防止空白)
            page.wait_for_timeout(2000)

            # 6. 检查是否是 404 或 登录页
            title = page.title()
            if "404" in title or "抱歉" in page.content():
                print("    ❌ 页面 404，可能是权限不足或 State 失效")
                browser.close()
                return None

            if "login" in page.url or "登录" in title:
                print("    ❌ Cookie/State 已失效，无法抓取")
                browser.close()
                return None

            html = page.content()
            fresh_cookies = _get_playwright_cookies(context)
            browser.close()

            return _process_html(html, url, fresh_cookies)

    except Exception as e:
        print(f"    ❌ 抓取内容出错: {e}")
        return None