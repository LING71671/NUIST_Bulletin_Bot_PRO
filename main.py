import time
import urllib3
import os

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from auth.login_manager import LoginManager
from spider.url_finder import UrlFinder
from spider.fetcher import fetch_content
from ai_brain.summarizer import BulletinSummarizer
from notify.sender import Notifier
from data.database import Database
import config


def main():
    print("🚀 NUIST 公告推送系统启动 (全栈重构版)...")

    # 1. 模块初始化
    db = Database()
    login_mgr = LoginManager(username=config.SCHOOL["USERNAME"], password=config.SCHOOL["PASSWORD"])
    finder = UrlFinder()
    ai = BulletinSummarizer()
    notifier = Notifier()

    # 2. 登录检查 (确保 cookies.json 是新的)
    print("\n🔐 检查登录状态...")
    # 这一步会生成或刷新 data/cookies.json
    cookie_res = login_mgr.get_cookies()

    if not os.path.exists(login_mgr.cookie_file):
        print("❌ 登录失败，未生成 Cookie 文件，程序退出。")
        return

    # 3. 扫描公告
    # finder 会自动读取 cookies.json
    print(f"\n📡 扫描首页: {config.SCHOOL['VPN_URL']}")
    new_links = finder.find_new_urls(config.SCHOOL['VPN_URL'])

    # 如果 finder 返回 None，说明它刚才删掉了坏 Cookie，请求重试
    if new_links is None:
        print("\n🔄 触发自动重连机制...")

        # 1. 重新调用 get_cookies (因为文件没了，它会强制启动浏览器登录)
        login_mgr.get_cookies()

        # 2. 再次尝试抓取
        print(f"📡 [重试] 再次扫描首页...")
        new_links = finder.find_new_urls(config.SCHOOL['VPN_URL'])

    # 如果重试后还是空的 (是 [] 而不是 None)，那是真的没公告
    if not new_links:
        print("⚠️ 未发现新公告链接。")
        return

    print(f"📋 发现 {len(new_links)} 条公告，开始处理...")

    # 4. 逐条处理
    for item in new_links:
        url = item['url']
        title = item['title']

        # 查重
        if db.is_seen(url):
            print(f"    ⏭️ [已读] {title}")
            continue

        print(f"\n⚡ 处理新公告: [{title}]")

        # 抓取 (fetcher 会自动读取 cookies.json)
        content = fetch_content(url)
        if not content:
            continue

        # AI 总结
        print("    🧠 AI 分析中...")
        summary = ai.summarize(content)

        if summary == "IGNORE":
            print("    🗑️ 无价值内容，忽略。")
            db.add_record(url, title, "IGNORE")
            continue

        # 推送
        print("    🔔 发送通知...")
        notifier.send(title, summary)

        # 入库
        db.add_record(url, title, summary)

        # 休息一下，防封禁
        time.sleep(3)

    print("\n✅ 所有任务完成！")
    db.close()

if __name__ == "__main__":
    main()