import logging
import os
import sys
from logging.handlers import RotatingFileHandler
import coloredlogs

def setup_logger(log_dir="logs", log_filename="bot.log", level=logging.INFO):
    """
    配置全局日志系统
    :param log_dir: 日志目录
    :param log_filename: 日志文件名
    :param level: 日志级别
    """
    # 1. 确保日志目录存在
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except Exception:
            pass # 忽略并发创建时的错误

    log_path = os.path.join(log_dir, log_filename)

    # 2. 获取根日志记录器
    # 必须配置 root logger，否则其他模块的 logging.getLogger(__name__) 不会生效
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 清除已有的 handler (防止重复打印)
    root_logger.handlers = []

    # 3. 文件处理器 (RotatingFileHandler)
    # maxBytes=5MB, backupCount=5 (保留5个历史文件)
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(level)
    root_logger.addHandler(file_handler)

    # 4. 控制台处理器 (使用 coloredlogs 美化)
    # 定义颜色方案
    field_styles = {
        'asctime': {'color': 'green'},
        'levelname': {'bold': True, 'color': 'black'},
        'name': {'color': 'blue'}
    }
    
    level_styles = {
        'debug': {'color': 'white', 'faint': True},
        'info': {'color': 'white'},
        'warning': {'color': 'yellow'},
        'error': {'color': 'red', 'bold': True},
        'critical': {'color': 'red', 'bold': True, 'background': 'white'}
    }

    coloredlogs.install(
        level=logging.getLevelName(level),
        logger=root_logger,
        fmt='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        field_styles=field_styles,
        level_styles=level_styles
    )

    logging.info(f"✅ 日志系统初始化完成，输出路径: {log_path}")
