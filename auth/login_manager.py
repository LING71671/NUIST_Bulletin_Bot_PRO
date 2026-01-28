import os
import json
import time
import PIL.Image
import logging
import contextlib  # 👈 新加这行，用来做“静音”处理
import config

# 屏蔽 onnxruntime 的红色警告
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

        # 路径配置
        current_script_path = os.path.abspath(__file__)
        base_dir = os.path.dirname(os.path.dirname(current_script_path))
        self.cookie_file = os.path.join(base_dir, "data", "cookies.json")

        # 登录 URL
        self.login_url = config.SCHOOL["LOGIN_URL"]
    def get_cookies(self):
        # 1. 优先读取本地缓存
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

    def _run_login(self):
        if not self.username or not self.password:
            print("❌ 未配置账号密码！")
            return None

        print(f"    🤖 [登录] 启动浏览器 (账号: {self.username})...")
        ocr = ddddocr.DdddOcr() if HAS_OCR else None

        # 正式模式 headless=True
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            try:
                print(f"    🔗 访问统一身份认证...")
                page.goto(self.login_url)

                # === 1. 检查是否无需登录 ===
                try:
                    if page.get_by_text("信息公告").is_visible(timeout=2000):
                        print("    🎉 检测到无需登录，直接进入首页！")
                        return self._save_cookies_and_return(context)
                except:
                    pass

                # === 2. 填写表单 ===
                print("    📝 填写账号密码...")
                if page.locator("#pwdLoginSpan").is_visible():
                    page.locator("#pwdLoginSpan").click()

                page.locator("#username").fill(str(self.username))
                page.locator("#password").fill(str(self.password))

                # === 3. 激活验证码 ===
                print("    🖱️ 点击页面激活验证码...")
                page.locator("body").click()
                page.wait_for_timeout(1500)

                if HAS_OCR and page.locator("#captchaImg").is_visible():
                    print("    👀 发现验证码，正在识别...")
                    self._solve_captcha(page, ocr)
                else:
                    print("    👻 未检测到验证码，尝试直接登录。")

                # === 4. 提交登录 (修复点：使用 ID 定位) ===
                print("    🚀 提交登录...")
                # 🔴 之前报错就是这里，现在改成精确的 ID 定位
                page.locator("#login_submit").click()

                # === 5. 结果判定 ===
                print("    ⏳ 等待跳转至 VPN 首页...")

                try:
                    # 等待"信息公告"出现
                    page.wait_for_selector("text=信息公告", timeout=15000)
                    print("    ✅ 登录成功！")
                    page.wait_for_timeout(3000)

                except Exception:
                    print("    ⚠️ 跳转超时，检查页面提示...")
                    # 检查错误提示
                    error_el = page.locator("#formErrorTip")
                    if error_el.is_visible():
                        err_text = error_el.inner_text()
                        print(f"    🚨 登录被拦截: {err_text}")

                        if "验证码" in err_text:
                            print("    🔄 正在尝试补填验证码...")
                            self._solve_captcha(page, ocr)
                            # 🔴 这里也改成了 ID 定位
                            page.locator("#login_submit").click()

                            page.wait_for_selector("text=信息公告", timeout=15000)
                            print("    ✅ 二次尝试成功！")
                    else:
                        # 最后检查一次 URL
                        if "client.vpn" in page.url:
                            print("    ✅ (URL检测) 登录成功！")
                        else:
                            page.screenshot(path="login_final_error.png")
                            raise Exception("登录失败，未跳转至预期页面")

                return self._save_cookies_and_return(context)

            except Exception as e:
                print(f"    ❌ 流程异常: {e}")
                return None
            finally:
                browser.close()

    def _solve_captcha(self, page, ocr):
        try:
            img_bytes = page.locator("#captchaImg").screenshot()
            code = ocr.classification(img_bytes)
            print(f"    🧮 验证码识别结果: [{code}]")
            page.locator("#captcha").fill(code)
        except:
            pass

    def _format_cookie_str(self, cookies_list):
        return "; ".join([f"{c['name']}={c['value']}" for c in cookies_list])

if __name__ == "__main__":
    MY_USERNAME = config.SCHOOL["USERNAME"]
    MY_PASSWORD = config.SCHOOL["PASSWORD"]

    lm = LoginManager(MY_USERNAME, MY_PASSWORD)

    if os.path.exists(lm.cookie_file):
        os.remove(lm.cookie_file)

    print("🏁 开始测试 (修复点击版)...")
    lm.get_cookies()