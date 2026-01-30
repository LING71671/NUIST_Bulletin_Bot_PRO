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

        # 📂 状态文件路径
        self.data_dir = os.path.join(base_dir, "data")
        self.cookie_file = os.path.join(self.data_dir, "cookies.json")
        self.state_file = os.path.join(self.data_dir, "state.json") # 🟢 新增：浏览器全状态文件

        self.login_url = config.SCHOOL["LOGIN_URL"]
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def get_cookies(self):
        """获取 Cookie：优先读缓存，无缓存则登录"""
        # 检查是否同时存在 cookie 和 state 文件
        if os.path.exists(self.cookie_file) and os.path.exists(self.state_file):
            try:
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                    print(f"    🍪 [缓存] 读取本地 Cookie: {self.cookie_file}")
                    return self._format_cookie_str(cookies)
            except:
                pass
        return self._run_login()

    def _save_cookies_and_return(self, context):
        """保存双重凭证"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # 1. 保存 cookies.json (给 fetcher/requests 用)
        cookies = context.cookies()
        with open(self.cookie_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f)

        # 2. 🟢 保存 state.json (给 UrlFinder/Playwright 用)
        # 这包含了 LocalStorage，能完美欺骗 SPA 页面
        context.storage_state(path=self.state_file)

        print(f"    💾 凭证已保存 (Cookie: {len(cookies)} | State: ✅)")
        return self._format_cookie_str(cookies)

    # ... (中间的 _check_critical_errors, _is_login_success, _wait_for_success, _solve_captcha, _fill_form, _execute_attempt 保持不变) ...
    # 为了节省篇幅，这里省略了中间的原子函数，它们逻辑不用变，请保留原样
    # 只需替换 __init__, get_cookies, _save_cookies_and_return
    # 以及下面的 _run_login (确保 headless 设置正确)

    def _check_critical_errors(self, page):
        if page.locator("#formErrorTip").is_visible():
            err_text = page.locator("#formErrorTip").inner_text()
            if "验证码" in err_text: raise Exception("验证码错误")
            if "密码" in err_text or "账号" in err_text: raise Exception("FATAL:账号密码错误")

    def _is_login_success(self, page):
        if "client/app" in page.url or "index" in page.url:
            print("    ✅ 登录成功 (URL特征匹配)！")
            return True
        if page.get_by_text("应用访问统一入口").is_visible():
            print("    ✅ 登录成功 (检测到首页标题)！")
            return True
        if page.get_by_text("信息公告").is_visible():
            print("    ✅ 登录成功 (检测到信息公告)！")
            return True
        return False

    def _wait_for_success(self, page):
        print("    ⏳ 等待跳转至 VPN 首页...")
        start_time = time.time()
        while time.time() - start_time < 15:
            self._check_critical_errors(page)
            if self._is_login_success(page): return True
            time.sleep(0.5)
        return False

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
        if page.locator("#pwdLoginSpan").is_visible(): page.locator("#pwdLoginSpan").click()
        page.locator("#username").fill(str(self.username))
        page.locator("#password").fill(str(self.password))
        page.locator("body").click()
        page.wait_for_timeout(500)
        if HAS_OCR and page.locator("#captchaImg").is_visible(): self._solve_captcha(page, ocr)
        print("    🚀 提交登录...")
        page.locator("#login_submit").click()

    def _execute_attempt(self, page, context, ocr):
        try:
            print(f"    🔗 访问统一身份认证...")
            page.goto(self.login_url)
            page.wait_for_load_state("domcontentloaded")
            if self._is_login_success(page): return True
            self._fill_form(page, ocr)
            if self._wait_for_success(page):
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

    def _run_login(self):
        if not self.username or not self.password:
            print("❌ 未配置账号密码！")
            return None
        ocr = ddddocr.DdddOcr() if HAS_OCR else None
        MAX_RETRIES = 3
        with sync_playwright() as p:
            print(f"    🤖 [登录] 启动浏览器 (账号: {self.username})...")
            # 调试时 headless=False, 部署时建议 True
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=self.user_agent)
            page = context.new_page()
            for attempt in range(1, MAX_RETRIES + 1):
                print(f"\n    🔄 [第 {attempt}/{MAX_RETRIES} 次尝试登录]...")
                result = self._execute_attempt(page, context, ocr)
                if result is True: return self._save_cookies_and_return(context)
                elif result is None: break
            print("❌ 达到最大重试次数，登录失败。")
            browser.close()
            return None

    def _format_cookie_str(self, cookies_list):
        return "; ".join([f"{c['name']}={c['value']}" for c in cookies_list])

if __name__ == "__main__":
    MY_USERNAME = config.SCHOOL["USERNAME"]
    MY_PASSWORD = config.SCHOOL["PASSWORD"]
    lm = LoginManager(MY_USERNAME, MY_PASSWORD)
    # 强制重新生成
    if os.path.exists(lm.cookie_file): os.remove(lm.cookie_file)
    if os.path.exists(lm.state_file): os.remove(lm.state_file)
    print("🏁 开始测试 (State 模式)...")
    lm.get_cookies()