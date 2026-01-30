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
        """主入口"""
        print(f"    🕷️ [Finder] 启动... 目标首页: {start_url}")

        html_content = self._fetch_page_source(start_url)
        if html_content is None: return None

        items = self._parse_html(html_content, start_url)

        if items:
            items.sort(key=lambda x: x['date'], reverse=True)
            print("    📉 [列表版] 排序后的前 5 条公告:")
            for idx, item in enumerate(items[:5]):
                print(f"       [{idx+1}] {item['date']} | {item['title'][:20]}...")
            return items[:5]
        return []

    # ==========================
    # 🔧 原子功能组件：逻辑判断
    # ==========================

    def _is_valid_link(self, href, text):
        """判断链接是否有效"""
        if not href or href == '#' or 'javascript' in href.lower():
            return False
        # 过滤 [分类]
        if text.startswith('[') and text.endswith(']'):
            return False
        # 过滤功能词
        ignore_words = {"更多", "详细", "置顶", "new", "HOT", "首页", "尾页"}
        if text in ignore_words:
            return False
        return True

    def _pick_best_link(self, candidates):
        """从一行中选出最佳链接"""
        if not candidates: return None

        # 策略1：优先选第一个长度 > 5 的 (通常是标题)
        for cand in candidates:
            if cand['len'] > 5:
                return cand['link']

        # 策略2：兜底选最长的
        candidates.sort(key=lambda x: x['len'], reverse=True)
        return candidates[0]['link']

    def _extract_date(self, text):
        match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        return match.group(1) if match else "1970-01-01"

    # ==========================
    # 🧱 原子功能组件：浏览器操作 (拆分解决复杂度警告)
    # ==========================

    def _inject_cookies(self, context):
        """任务：注入Cookie"""
        if not os.path.exists(self.cookie_file): return
        try:
            with open(self.cookie_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
                # 清洗 sameSite 字段
                safe = [c for c in cookies if c.pop('sameSite', None) not in ['Strict', 'Lax']]
                context.add_cookies(safe)
        except Exception as e:
            print(f"    ⚠️ Cookie 读取微瑕: {e}")

    def _navigate_and_get_content(self, page, context):
        """任务：处理页面跳转"""
        # 如果当前页就有目标按钮，尝试点击跳转
        if self.target_text in page.content():
            try:
                with context.expect_page(timeout=15000) as new_info:
                    page.get_by_text(self.target_text).first.click()
                list_page = new_info.value
                list_page.wait_for_load_state("domcontentloaded")
                try: list_page.wait_for_selector("ul.news_list, tr", timeout=5000)
                except: pass
                return list_page.content()
            except:
                # 点击失败，回退使用当前页
                return page.content()
        return page.content()

    # ==========================
    # 🧵 主流程控制
    # ==========================

    def _extract_link_from_row(self, row):
        """解析单行数据"""
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
        """解析整页 HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        candidates = []

        # 兼容多种列表选择器
        items = soup.select("ul.news_list li")
        if not items: items = soup.find_all("li", class_=lambda x: x and 'news' in x)
        if not items: items = soup.select("tr")

        print(f"    👀 扫描到 {len(items)} 个潜在行...")

        for item in items:
            data = self._extract_link_from_row(item)
            if data:
                data['url'] = urljoin(base_url, data['url'])
                candidates.append(data)
        return candidates

    def _fetch_page_source(self, url):
        """
        浏览器主流程
        现在它只是一个指挥官，不负责具体干活，复杂度极低
        """
        source = None
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # 1. 注入
            self._inject_cookies(context)

            page = context.new_page()
            try:
                print(f"    🔗 正在访问首页...")
                page.goto(url, timeout=60000)

                # 2. 检查
                if any(x in page.title() for x in ["登录", "Login", "用户登录"]):
                    print("    ❌ Cookie 已失效")
                    if os.path.exists(self.cookie_file): os.remove(self.cookie_file)
                    return None

                # 3. 跳转并获取
                source = self._navigate_and_get_content(page, context)

            except Exception as e:
                print(f"    ⚠️ 浏览器异常: {e}")
            finally:
                browser.close()
        return source