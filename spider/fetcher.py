import os
import json
import requests
import mimetypes
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 自动定位 cookie 文件
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE = os.path.join(BASE_DIR, "data", "cookies.json")
TEMP_DIR = os.path.join(BASE_DIR, "data", "temp_files")

DEFAULT_HEADERS = {
    # 必须与 LoginManager 保持一致，否则会被踢下线
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_requests_cookies():
    """工具函数：加载 Cookie"""
    cookie_dict = {}
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    cookie_dict[item['name']] = item['value']
        except:
            pass
    return cookie_dict

def download_file(url, session):
    """工具函数：下载文件"""
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    try:
        print(f"    ⬇️ 下载附件: {url.split('/')[-1][:20]}...")
        res = session.get(url, stream=True, verify=False, timeout=30)

        # 智能猜测后缀
        content_type = res.headers.get('Content-Type', '').split(';')[0]
        ext = mimetypes.guess_extension(content_type) or ".dat"

        # 如果 URL 本身有后缀，优先用 URL 的
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
# 🔧 原子组件：解析逻辑 (拆分降低复杂度)
# ==========================================

def _setup_session():
    """原子任务：初始化会话"""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    session.cookies.update(get_requests_cookies())
    return session

def _extract_attachments(soup, base_url, session):
    """原子任务：从 HTML 中提取并下载附件"""
    files = []
    # 查找所有带 href 的链接
    for a in soup.find_all('a', href=True):
        href = a['href']
        full_link = urljoin(base_url, href)
        lower_link = full_link.lower()

        # 附件后缀白名单
        valid_exts = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar']

        if any(x in lower_link for x in valid_exts):
            # 过滤垃圾链接
            if 'mailto:' in lower_link or 'javascript:' in lower_link:
                continue

            f_path = download_file(full_link, session)
            if f_path:
                files.append(f_path)
    return files

def _process_html_response(response, session, url):
    """原子任务：处理 HTML 类型的响应"""
    soup = BeautifulSoup(response.text, 'html.parser')

    # 1. 提取正文 (简单清洗)
    text = soup.get_text(separator='\n', strip=True)

    # 2. 提取附件
    files = _extract_attachments(soup, url, session)

    return {
        "type": "compound",
        "text": text[:5000], # 稍微给多点上下文
        "files": files
    }

# ==========================================
# 🚀 主入口
# ==========================================

def fetch_content(url):
    """
    主抓取函数
    现在它只是一个调度员，复杂度极低
    """
    session = _setup_session()

    try:
        response = session.get(url, verify=False, timeout=15)
        response.encoding = 'utf-8' # 强制 UTF-8，防止乱码

        content_type = response.headers.get('Content-Type', '')

        # 分流处理
        if 'text/html' in content_type:
            return _process_html_response(response, session, url)
        else:
            # 如果直接是文件链接
            path = download_file(url, session)
            return {"type": "file", "path": path}

    except Exception as e:
        print(f"    ❌ 抓取内容出错: {e}")
        return None