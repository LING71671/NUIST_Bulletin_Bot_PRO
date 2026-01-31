import time
import urllib3
import os
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.logger import setup_logger

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from auth.login_manager import LoginManager
from spider.url_finder import UrlFinder
from spider.fetcher import fetch_content
from ai_brain.summarizer import BulletinSummarizer
from notify.sender import Notifier
from data.db_manager import DatabaseManager
from data.models import ProcessStatus
import config

# 获取日志记录器
logger = logging.getLogger(__name__)

def process_single_task(item, db, ai, notifier):
    """
    工作线程：处理单条公告的全生命周期
    """
    url = item['url']
    title = item['title']
    
    # 1. 再次查重 (防止并发时的重复提交，虽然概率很低)
    if db.is_processed(url):
        logger.info(f"    ⏭️ [Worker] 跳过已处理: {title[:10]}...")
        return

    # 2. 注册任务
    db.register_task(url, title)
    logger.info(f"⚡ [Worker] 开始处理: {title[:15]}...")

    # 3. 随机等待 (错峰请求，防止并发触发防火墙)
    time.sleep(random.uniform(0.5, 2.0))

    try:
        # 4. 抓取内容
        content = fetch_content(url)
        if not content:
            db.update_status(url, ProcessStatus.FAILED, error_msg="抓取内容为空")
            return

        # 5. AI 分析
        logger.info(f"    🧠 [Worker-AI] 分析中: {title[:10]}...")
        summary = ai.summarize(content, title=title)

        if summary == "IGNORE":
            logger.info(f"    🗑️ [Worker] 判定无价值: {title[:10]}...")
            db.update_status(url, ProcessStatus.IGNORED)
            return

        # 6. 推送通知
        logger.info(f"    🔔 [Worker] 准备推送: {title[:10]}...")
        files_to_send = content.get('files', [])
        is_success = notifier.send(title, summary, attachments=files_to_send)

        if is_success:
            db.update_status(url, ProcessStatus.SUCCESS, summary=summary)
            logger.info(f"    ✅ [Worker] 任务完成: {title[:10]}...")
        else:
            logger.warning(f"    ⚠️ [Worker] 推送失败: {title[:10]}...")
            db.update_status(url, ProcessStatus.FAILED, error_msg="推送通知失败")

    except Exception as e:
        logger.error(f"    ❌ [Worker] 任务异常 ({title[:10]}...): {e}")
        db.update_status(url, ProcessStatus.FAILED, error_msg=f"Worker异常: {str(e)}")


def main():
    # 0. 初始化日志系统
    setup_logger()
    
    logging.info("🚀 NUIST 公告推送系统启动 (V2.1 Concurrency)...")

    # 1. 模块初始化 (主线程持有)
    db = DatabaseManager()
    login_mgr = LoginManager(username=config.SCHOOL["USERNAME"], password=config.SCHOOL["PASSWORD"])
    finder = UrlFinder()
    
    # 这些对象是线程安全的或无状态的，可以共享
    ai = BulletinSummarizer()
    notifier = Notifier()

    # 2. 登录检查
    logging.info("🔐 检查登录状态...")
    login_mgr.get_cookies()

    if not os.path.exists(login_mgr.cookie_file):
        logging.error("❌ 登录失败，退出。")
        return

    # 3. 扫描公告 (生产者)
    logging.info(f"📡 扫描首页: {config.SCHOOL['VPN_URL']}")
    new_links = finder.find_new_urls(config.SCHOOL['VPN_URL'])

    if new_links is None:
        logging.warning("🔄 触发自动重连机制...")
        login_mgr.get_cookies()
        logging.info(f"📡 [重试] 再次扫描首页...")
        new_links = finder.find_new_urls(config.SCHOOL['VPN_URL'])

    if not new_links:
        logging.info("⚠️ 未发现新公告链接。")
        db.close()
        return

    # 4. 过滤已处理任务
    # 只将数据库中未标记为 SUCCESS/IGNORED 的任务提交给线程池
    tasks_to_run = []
    for item in new_links:
        if not db.is_processed(item['url']):
            tasks_to_run.append(item)
        else:
            logging.info(f"    ⏭️ [已读] {item['title'][:15]}...")

    if not tasks_to_run:
        logging.info("✅ 所有公告均已处理。")
        db.close()
        return

    # 5. 启动线程池 (消费者)
    # 读取配置中的并发数，默认为 2
    max_workers = config.SYSTEM.get("MAX_WORKERS", 2)
    logging.info(f"📋 待处理任务数: {len(tasks_to_run)} (并发数: {max_workers})")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for task in tasks_to_run:
            # 提交任务
            future = executor.submit(process_single_task, task, db, ai, notifier)
            futures.append(future)
        
        # 等待所有任务完成
        for future in as_completed(futures):
            try:
                future.result() # 这里会抛出 worker 内部未捕获的异常
            except Exception as e:
                logger.error(f"💥 线程池异常: {e}")

    logging.info("✅ 所有并发任务执行完毕！")
    db.close()

if __name__ == "__main__":
    main()