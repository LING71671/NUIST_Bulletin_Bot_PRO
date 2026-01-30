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
        self.data_dir = os.path.join(base_dir, "data")
        self.cookie_file = os.path.join(self.data_dir, "cookies.json")
        self.state_file = os.path.join(self.data_dir, "state.json")

    def find_new_urls(self, start_url):
        """主入口"""
        print(f"    🕷️ [Finder] 启动... 目标首页: {start_url}")

        # 🟢 修改1：接收返回的 tuple (content, final_url)
        result = self._fetch_page_source(start_url)

        if result is None:
            return None

        html_content, final_url = result

        # 🟢 修改2：使用跳转后的 final_url 作为基准进行拼接
        print(f"    📍 列表页真实地址: {final_url}")
        items = self._parse_html(html_content, final_url)

        if items:
            items.sort(key=lambda x: x['date'], reverse=True)
            print("    📉 [列表版] 排序后的前 5 条公告:")
            for idx, item in enumerate(items[:5]):
                print(f"       [{idx+1}] {item['date']} | {item['title'][:20]}...")
            return items[:5]
        return []

    # ==========================
    # 🔧 原子功能组件
    # ==========================

    def _is_valid_link(self, href, text):
        if not href or href == '#' or 'javascript' in href.lower(): return False
        if text.startswith('[') and text.endswith(']'): return False
        ignore_words = {"更多", "详细", "置顶", "new", "HOT", "首页", "尾页"}
        if text in ignore_words: return False
        return True

    def _pick_best_link(self, candidates):
        if not candidates: return None
        for cand in candidates:
            if cand['len'] > 5: return cand['link']
        candidates.sort(key=lambda x: x['len'], reverse=True)
        return candidates[0]['link']

    def _extract_date(self, text):
        match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        return match.group(1) if match else "1970-01-01"

    # ==========================
    # 🧱 浏览器操作
    # ==========================

    def _inject_cookies_fallback(self, context):
        if not os.path.exists(self.cookie_file): return
        try:
            with open(self.cookie_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
                safe = [c for c in cookies if c.pop('sameSite', None) not in ['Strict', 'Lax']]
                context.add_cookies(safe)
        except: pass

    def _navigate_and_get_content(self, page, context):
        """
        页面跳转逻辑
        返回: (html_content, current_url)
        """
        final_content = ""
        final_url = page.url

        # 如果当前页就有目标按钮，尝试点击
        if self.target_text in page.content():
            try:
                with context.expect_page(timeout=15000) as new_info:
                    page.get_by_text(self.target_text).first.click()

                list_page = new_info.value
                list_page.wait_for_load_state("domcontentloaded")

                # 等待列表加载
                try: list_page.wait_for_selector("ul.news_list, tr", timeout=5000)
                except: pass

                final_content = list_page.content()
                final_url = list_page.url # 🟢 抓取跳转后的 URL

            except:
                # 点击失败，回退使用当前页
                final_content = page.content()
                final_url = page.url
        else:
            final_content = page.content()
            final_url = page.url

        return final_content, final_url

    def _fetch_page_source(self, url):
        """浏览器主流程"""
        result = None
        with sync_playwright() as p:
            # 保持之前的配置 (有头+隐身)
            browser = p.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )

            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

            if os.path.exists(self.state_file):
                # print(f"    📂 [Finder] 加载完整浏览器状态: {self.state_file}")
                context = browser.new_context(
                    storage_state=self.state_file,
                    user_agent=user_agent
                )
            else:
                print("    ⚠️ 未找到状态文件，尝试仅注入 Cookie...")
                context = browser.new_context(user_agent=user_agent)
                self._inject_cookies_fallback(context)

            # 注入防检测
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            page = context.new_page()
            try:
                print(f"    🔗 正在访问首页...")
                page.goto(url, timeout=60000)

                if any(x in page.title() for x in ["登录", "Login", "用户登录"]):
                    print("    ❌ 凭证已失效 (Redirected to Login)")
                    if os.path.exists(self.cookie_file): os.remove(self.cookie_file)
                    if os.path.exists(self.state_file): os.remove(self.state_file)
                    return None

                # 🟢 修改3：返回 (content, url)
                result = self._navigate_and_get_content(page, context)

            except Exception as e:
                print(f"    ⚠️ 浏览器异常: {e}")
            finally:
                browser.close()
        return result

    # ==========================
    # 🧵 核心解析
    # ==========================

    def _extract_link_from_row(self, row):
        all_links = row.find_all('a', href=True)
        if not all_links: return None
        valid_candidates = []
        for link in all_links:
            href = link['href'].strip()
            text = link.get_text(strip=True)
            if self._is_valid_link(href, text):
                valid_candidates.append({'link': link, 'len': len(text)})
        best_link = self._pick_best_link(valid_candidates)
        if not best_link: return None
        return {
            'url': best_link['href'],
            'title': best_link.get_text(strip=True),
            'date': self._extract_date(row.get_text(" ", strip=True))
        }

    def _parse_html(self, html, base_url):
        soup = BeautifulSoup(html, 'html.parser')
        candidates = []
        items = soup.select("ul.news_list li")
        if not items: items = soup.find_all("li", class_=lambda x: x and 'news' in x)
        if not items: items = soup.select("tr")

        print(f"    👀 扫描到 {len(items)} 个潜在行...")

        for item in items:
            data = self._extract_link_from_row(item)
            if data:
                # 🟢 这里通过正确的 base_url 拼接，就不会 404 了
                data['url'] = urljoin(base_url, data['url'])
                candidates.append(data)
        return candidates