import os
import json
import time
import PIL.Image
import config

# 屏蔽干扰日志
os.environ["ORT_LOGGING_LEVEL"] = "3"

# 🚑 修复 Pillow 兼容性
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from playwright.sync_api import sync_playwright

try:
    import ddddocr
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("⚠️ 未安装 ddddocr，验证码将无法自动识别。")

class LoginManager:
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password

        current_script_path = os.path.abspath(__file__)
        base_dir = os.path.dirname(os.path.dirname(current_script_path))
        self.cookie_file = os.path.join(base_dir, "data", "cookies.json")
        self.login_url = config.SCHOOL["LOGIN_URL"]

        # 🔴 核心修复：确保与 UrlFinder 使用完全一致的 User-Agent
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def get_cookies(self):
        """获取 Cookie：优先读缓存，无缓存则登录"""
        if os.path.exists(self.cookie_file) and os.path.getsize(self.cookie_file) > 0:
            try:
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                    print(f"    🍪 [缓存] 读取本地 Cookie: {self.cookie_file}")
                    return self._format_cookie_str(cookies)
            except:
                pass
        return self._run_login()

    def _save_cookies_and_return(self, context):
        cookies = context.cookies()
        save_dir = os.path.dirname(self.cookie_file)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        with open(self.cookie_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f)
        print(f"    💾 Cookie 已保存 ({len(cookies)} 个)")
        return self._format_cookie_str(cookies)

    # ==========================================
    # 🧱 原子组件：判定逻辑
    # ==========================================

    def _check_critical_errors(self, page):
        if page.locator("#formErrorTip").is_visible():
            err_text = page.locator("#formErrorTip").inner_text()
            if "验证码" in err_text:
                raise Exception("验证码错误")
            if "密码" in err_text or "账号" in err_text:
                raise Exception("FATAL:账号密码错误")

    def _is_login_success(self, page):
        # 1. URL 特征
        if "client/app" in page.url or "index" in page.url:
            print("    ✅ 登录成功 (URL特征匹配)！")
            return True
        # 2. 标题特征
        if page.get_by_text("应用访问统一入口").is_visible():
            print("    ✅ 登录成功 (检测到首页标题)！")
            return True
        # 3. 元素特征
        if page.get_by_text("信息公告").is_visible():
            print("    ✅ 登录成功 (检测到信息公告)！")
            return True
        return False

    def _wait_for_success(self, page):
        print("    ⏳ 等待跳转至 VPN 首页...")
        start_time = time.time()

        while time.time() - start_time < 15:
            self._check_critical_errors(page)
            if self._is_login_success(page):
                return True
            time.sleep(0.5)

        return False

    # ==========================================
    # 🔧 原子组件：操作逻辑
    # ==========================================

    def _solve_captcha(self, page, ocr):
        try:
            print("    👀 正在识别验证码...")
            captcha_box = page.locator("#captchaImg")
            img_bytes = captcha_box.screenshot()
            code = ocr.classification(img_bytes)
            print(f"    🧮 识别结果: [{code}]")
            page.locator("#captcha").fill(code)
        except Exception as e:
            print(f"    ⚠️ 验证码处理失败: {e}")

    def _fill_form(self, page, ocr):
        if page.locator("#pwdLoginSpan").is_visible():
            page.locator("#pwdLoginSpan").click()

        page.locator("#username").fill(str(self.username))
        page.locator("#password").fill(str(self.password))

        page.locator("body").click()
        page.wait_for_timeout(500)

        if HAS_OCR and page.locator("#captchaImg").is_visible():
            self._solve_captcha(page, ocr)

        print("    🚀 提交登录...")
        page.locator("#login_submit").click()

    def _execute_attempt(self, page, context, ocr):
        try:
            print(f"    🔗 访问统一身份认证...")
            page.goto(self.login_url)
            page.wait_for_load_state("domcontentloaded")

            if self._is_login_success(page):
                return True

            self._fill_form(page, ocr)

            if self._wait_for_success(page):
                # 登录成功后多等一会，确保 Session Cookie 写入完成
                page.wait_for_timeout(3000)
                return True
            else:
                print("    ⚠️ 等待跳转超时")
                return False

        except Exception as e:
            msg = str(e)
            if "FATAL" in msg:
                print(f"    ❌ 致命错误: {msg}")
                return None
            if "验证码错误" in msg:
                print("    ⚠️ 验证码错误，准备刷新重试...")
                return False

            print(f"    ⚠️ 尝试过程异常: {msg}")
            return False

    # ==========================================
    # 🚀 主入口
    # ==========================================

    def _run_login(self):
        if not self.username or not self.password:
            print("❌ 未配置账号密码！")
            return None

        ocr = ddddocr.DdddOcr() if HAS_OCR else None
        MAX_RETRIES = 3

        with sync_playwright() as p:
            print(f"    🤖 [登录] 启动浏览器 (账号: {self.username})...")

            # 启动浏览器
            browser = p.chromium.launch(headless=False)

            # 🔴 关键修改：注入与 UrlFinder 一致的 User-Agent
            context = browser.new_context(user_agent=self.user_agent)

            page = context.new_page()

            for attempt in range(1, MAX_RETRIES + 1):
                print(f"\n    🔄 [第 {attempt}/{MAX_RETRIES} 次尝试登录]...")

                result = self._execute_attempt(page, context, ocr)

                if result is True:
                    return self._save_cookies_and_return(context)
                elif result is None:
                    break

            print("❌ 达到最大重试次数，登录失败。")
            browser.close()
            return None

    def _format_cookie_str(self, cookies_list):
        return "; ".join([f"{c['name']}={c['value']}" for c in cookies_list])

if __name__ == "__main__":
    MY_USERNAME = config.SCHOOL["USERNAME"]
    MY_PASSWORD = config.SCHOOL["PASSWORD"]
    lm = LoginManager(MY_USERNAME, MY_PASSWORD)

    if os.path.exists(lm.cookie_file):
        os.remove(lm.cookie_file)

    print("🏁 开始测试 (User-Agent 修复版)...")
    lm.get_cookies()