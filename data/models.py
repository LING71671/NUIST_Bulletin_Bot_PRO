from sqlalchemy import Column, String, Integer, DateTime, Text, Enum
from sqlalchemy.orm import declarative_base
import enum
from datetime import datetime

# 创建基类
Base = declarative_base()

# 定义处理状态枚举
class ProcessStatus(enum.Enum):
    PENDING = "pending"       # 初始状态：刚发现链接
    PROCESSING = "processing" # 中间状态：正在抓取或AI分析中
    SUCCESS = "success"       # 终态：已成功推送并存档
    FAILED = "failed"         # 终态：处理失败（如网络错误、解析失败）
    IGNORED = "ignored"       # 终态：被 Hunter 判定为无价值

class Bulletin(Base):
    """
    公告数据模型
    对应数据库表: bulletins
    """
    __tablename__ = 'bulletins'

    # 主键 ID
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 核心字段
    url = Column(String(500), unique=True, index=True, nullable=False) # URL 必须唯一且加索引
    title = Column(String(500), nullable=True)                         # 标题
    summary = Column(Text, nullable=True)                              # AI 摘要 (长文本)
    
    # 工程化字段 (状态机 & 容错)
    status = Column(Enum(ProcessStatus), default=ProcessStatus.PENDING, index=True)
    retry_count = Column(Integer, default=0)    # 重试次数
    error_msg = Column(Text, nullable=True)     # 错误日志
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)            # 首次发现时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now) # 最后更新时间

    def __repr__(self):
        return f"<Bulletin(id={self.id}, title='{self.title[:10]}...', status={self.status})>"
