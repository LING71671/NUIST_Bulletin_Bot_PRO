import os
import json
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class UrlFinder:
    def __init__(self):
        self.target_text = "信息公告"
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cookie_file = os.path.join(base_dir, "data", "cookies.json")

    def find_new_urls(self, start_url):
        print(f"    🕷️ [Finder] 启动... 目标首页: {start_url}")

        all_candidates = []

        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # === 1. 注入 Cookie ===
            if os.path.exists(self.cookie_file):
                try:
                    with open(self.cookie_file, 'r', encoding='utf-8') as f:
                        cookies = json.load(f)
                        safe_cookies = []
                        for c in cookies:
                            if 'sameSite' in c and c['sameSite'] not in ['Strict', 'Lax', 'None', 'no_restriction']:
                                del c['sameSite']
                            safe_cookies.append(c)
                        context.add_cookies(safe_cookies)
                except:
                    pass

            page = context.new_page()

            try:
                # === 2. 访问首页 ===
                print(f"    🔗 正在进入 VPN 首页...")
                page.goto(start_url, timeout=60000)

                current_title = page.title()

                if "登录" in current_title or "Login" in current_title or "用户登录" in current_title:
                    print("    ❌ 检测到 Cookie 失效！")

                    # 1. 立即销毁过期的 Cookie 文件
                    if os.path.exists(self.cookie_file):
                        os.remove(self.cookie_file)
                        print("    🗑️ 已自动删除过期 Cookie 文件。")

                    # 2. 返回 None (而不是空列表)，作为发给 main.py 的“重试信号”
                    return None

                # === 3. 进入列表页 ===
                print(f"    🔍 寻找并点击 [{self.target_text}]...")
                try:
                    with context.expect_page(timeout=15000) as new_page_info:
                        # 尝试精确匹配或模糊匹配
                        page.get_by_text(self.target_text).first.click()

                    list_page = new_page_info.value
                    list_page.wait_for_load_state("domcontentloaded")

                    # 🔴 关键点：等待 ul.news_list 出现，这是截图里的核心特征
                    try:
                        list_page.wait_for_selector("ul.news_list", timeout=5000)
                    except:
                        print("    ⚠️ 未找到标准列表结构，尝试继续解析...")

                    print("    🔀 成功进入公告列表页！")
                    base_url = list_page.url
                    html_content = list_page.content()
                    soup = BeautifulSoup(html_content, 'html.parser')

                    # === 4. 解析列表 (基于截图修正) ===
                    # 截图显示：ul class="news_list clearfix" -> li class="news clearfix"

                    # 1. 找到所有的新闻项 (li 标签)
                    # 兼容 news_list 下的 li，或者直接找 class 含 news 的 li
                    items = soup.select("ul.news_list li")
                    if not items:
                        # 备用方案：直接找所有 class="news ..." 的 li
                        items = soup.find_all("li", class_=lambda x: x and 'news' in x)

                    print(f"    👀 扫描到 {len(items)} 条数据 (基于 ul/li 结构)...")

                    for item in items:
                        # --- A. 提取链接和标题 ---
                        # 链接通常在 a 标签里
                        link_tag = item.find('a', href=True)
                        if not link_tag: continue

                        title = link_tag.get_text(strip=True)
                        href = link_tag['href']

                        # --- B. 提取日期 ---
                        # 策略1：截图暗示可能有 div class="title_sj" (sj=时间)
                        date_div = item.find(class_=re.compile("title_sj|date|time"))

                        date_str = "1970-01-01"

                        if date_div:
                            # 如果找到了专门放日期的框
                            txt = date_div.get_text(strip=True)
                            match = re.search(r"(\d{4}-\d{2}-\d{2})", txt)
                            if match: date_str = match.group(1)
                        else:
                            # 策略2：没找到专门的class，就在整个 li 的文本里找日期
                            # 限制只在这个 li 内部找，绝对不会跨行！
                            item_text = item.get_text(" ", strip=True)
                            match = re.search(r"(\d{4}-\d{2}-\d{2})", item_text)
                            if match: date_str = match.group(1)

                        # --- C. 过滤 ---
                        if len(title) < 4: continue
                        # 过滤掉非公告的链接
                        blacklist = ["更多", "English", "首页", "上一页", "尾页"]
                        if any(w in title for w in blacklist): continue

                        # 组装
                        full_url = urljoin(base_url, href)

                        all_candidates.append({
                            'url': full_url,
                            'title': title,
                            'date': date_str
                        })

                except Exception as e:
                    print(f"    ⚠️ 页面操作失败: {e}")

            except Exception as e:
                print(f"    ⚠️ 抓取过程异常: {e}")
            finally:
                browser.close()

        # === 5. 排序与返回 ===
        if all_candidates:
            # 再次按日期倒序
            all_candidates.sort(key=lambda x: x['date'], reverse=True)

            print("    📉 [列表版] 排序后的前 5 条公告:")
            for idx, item in enumerate(all_candidates[:5]):
                print(f"       [{idx+1}] {item['date']} | {item['title'][:25]}...")

            return all_candidates[:5]

        return []