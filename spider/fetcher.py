import os
import json
import requests
import mimetypes
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 自动定位 cookie 文件
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE = os.path.join(BASE_DIR, "data", "cookies.json")
TEMP_DIR = os.path.join(BASE_DIR, "data", "temp_files")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_requests_cookies():
    """从 json 文件加载 cookie 并转换为 requests 字典"""
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
    """下载附件"""
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    try:
        print(f"    ⬇️ 下载附件: {url.split('/')[-1][:20]}...")
        # verify=False 是因为学校VPN证书通常无效
        res = session.get(url, stream=True, verify=False, timeout=30)

        # 猜后缀
        content_type = res.headers.get('Content-Type', '').split(';')[0]
        ext = mimetypes.guess_extension(content_type) or ".dat"

        filename = f"attach_{datetime.now().strftime('%H%M%S_%f')}{ext}"
        path = os.path.join(TEMP_DIR, filename)

        with open(path, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
        return path
    except Exception as e:
        print(f"    ⚠️ 下载失败: {e}")
        return None

def fetch_content(url):
    """主抓取函数"""
    # 1. 准备 Session (自动带 Cookie)
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    session.cookies.update(get_requests_cookies())

    try:
        response = session.get(url, verify=False, timeout=15)
        response.encoding = 'utf-8' # 防止中文乱码

        # 情况 A: HTML 网页
        if 'text/html' in response.headers.get('Content-Type', ''):
            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取正文 (简单提取)
            # 针对学校网页，通常正文在特定的 div 里，这里先做通用提取
            text = soup.get_text(separator='\n', strip=True)

            # 提取附件
            files = []
            # 查找所有 a 标签
            for a in soup.find_all('a', href=True):
                href = a['href']
                full_link = urljoin(url, href)

                # 简单的附件判断逻辑
                lower_link = full_link.lower()
                if any(x in lower_link for x in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.zip']):
                    # 过滤掉一些垃圾链接
                    if 'mailto:' in lower_link: continue

                    f_path = download_file(full_link, session)
                    if f_path:
                        files.append(f_path)

            return {
                "type": "compound",
                "text": text[:3000], # 截取前3000字
                "files": files
            }

        # 情况 B: 直接是文件
        else:
            path = download_file(url, session)
            return {"type": "file", "path": path}

    except Exception as e:
        print(f"    ❌ 抓取内容出错: {e}")
        return None