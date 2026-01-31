import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from .models import Base, Bulletin, ProcessStatus
from datetime import datetime

# 获取模块级日志
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path=None):
        """
        初始化数据库连接
        :param db_path: 数据库文件路径 (默认为当前目录下的 history_v2.db)
        """
        if not db_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            # 使用新文件名 history_v3.db 以免破坏旧数据
            db_path = f"sqlite:///{os.path.join(base_dir, 'history.db')}"
        
        self.engine = create_engine(db_path, echo=False) # echo=True 可打印 SQL 用于调试
        
        # 自动创建表结构
        Base.metadata.create_all(self.engine)
        
        # 创建线程安全的 Session 工厂
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
        
        logger.info(f"💾 [DB] 数据库连接已初始化: {db_path}")

    def get_session(self):
        """获取一个新的会话"""
        return self.Session()

    def close(self):
        """关闭连接池"""
        self.Session.remove()

    # ==========================
    # 业务操作 API
    # ==========================

    def is_processed(self, url):
        """检查 URL 是否已被成功处理或忽略 (用于快速查重)"""
        session = self.get_session()
        try:
            record = session.query(Bulletin).filter_by(url=url).first()
            if not record:
                return False
            # 只有状态为 SUCCESS 或 IGNORED 才算“处理完”
            # FAILED 或 PENDING 的可以重试
            return record.status in [ProcessStatus.SUCCESS, ProcessStatus.IGNORED]
        finally:
            session.close()

    def register_task(self, url, title):
        """
        注册一个新任务 (如果不存在则创建 PENDING 记录)
        :return: Bulletin 对象
        """
        session = self.get_session()
        try:
            record = session.query(Bulletin).filter_by(url=url).first()
            if not record:
                record = Bulletin(url=url, title=title, status=ProcessStatus.PENDING)
                session.add(record)
                session.commit()
                logger.info(f"    💾 [DB] 新增任务: {title[:15]}...")
            return record
        except Exception as e:
            session.rollback()
            logger.error(f"    ❌ [DB] 注册任务失败: {e}")
            raise e
        finally:
            session.close()

    def update_status(self, url, status: ProcessStatus, summary=None, error_msg=None):
        """更新任务状态"""
        session = self.get_session()
        try:
            record = session.query(Bulletin).filter_by(url=url).first()
            if record:
                record.status = status
                if summary:
                    record.summary = summary
                if error_msg:
                    record.error_msg = str(error_msg)
                    # 只有失败时才增加重试计数
                    if status == ProcessStatus.FAILED:
                        record.retry_count += 1
                
                session.commit()
                logger.info(f"    💾 [DB] 状态更新 -> {status.value}: {record.title[:10]}...")
            else:
                logger.warning(f"    ⚠️ [DB] 尝试更新不存在的记录: {url}")
        except Exception as e:
            session.rollback()
            logger.error(f"    ❌ [DB] 更新状态失败: {e}")
        finally:
            session.close()
