import sqlite3
import os
from datetime import datetime

class Database:
    def __init__(self, db_path=None):
        # 如果不传路径，自动找当前文件同级目录下的 history.db
        if not db_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "history.db")

        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        """初始化表结构"""
        # 创建一个简单的表：存URL、标题、摘要、时间
        self.cursor.execute('''
                            CREATE TABLE IF NOT EXISTS seen_urls (
                                                                     url TEXT PRIMARY KEY,
                                                                     title TEXT,
                                                                     summary TEXT,
                                                                     created_at TIMESTAMP
                            )
                            ''')
        self.conn.commit()

    def is_seen(self, url):
        """检查 URL 是否已经处理过"""
        self.cursor.execute('SELECT 1 FROM seen_urls WHERE url = ?', (url,))
        return self.cursor.fetchone() is not None

    def add_record(self, url, title, summary=""):
        """添加处理记录"""
        try:
            self.cursor.execute('''
                                INSERT INTO seen_urls (url, title, summary, created_at)
                                VALUES (?, ?, ?, ?)
                                ''', (url, title, summary, datetime.now()))
            self.conn.commit()
            print(f"    💾 [DB] 已记录: {title[:10]}...")
        except sqlite3.IntegrityError:
            print(f"    ⚠️ [DB] 跳过重复: {url}")

    def close(self):
        self.conn.close()