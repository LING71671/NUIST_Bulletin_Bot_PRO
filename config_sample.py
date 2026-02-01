# config_sample.py - 项目配置样本

# ================= 🏫 学校账号配置 =================
SCHOOL = {
    "USERNAME": "",
    "PASSWORD": "",
    "VPN_URL": "https://client.vpn.nuist.edu.cn/",
    "LOGIN_URL": "https://authserver.nuist.edu.cn/authserver/login?service=https://client.vpn.nuist.edu.cn/enlink/api/client/callback/cas"
}

# ================= 🤖 AI 模型配置 =================
AI_KEYS = {
    "deepseek": "",
    "aliyun": "",
    "silicon": "",
    "zhipu": ""
}

AI_CONFIG = {
    "TEMPERATURE": 0.1,
    "TIMEOUT": 45,
    "VISION_TIMEOUT": 30,
    "MAX_ATTACH_PAGES": 10,     # PDF 解析页数限制
    "MAX_ATTACH_SLIDES": 15,    # PPT 解析页数限制
    "MAX_CONTEXT_LEN": 12000,   # 总结时的上下文长度限制
    "FILTER_CONTEXT_LEN": 2500  # 过滤时的上下文长度限制
}

# ================= 📢 推送通道配置 =================
NOTIFY = {
    "EMAIL": {
        "ENABLE": False,
        "SMTP_SERVER": "smtp.qq.com",
        "SMTP_PORT": 465,
        "SENDER": "",
        "PASSWORD": "",
        "RECEIVER": ""
    },
    "QMSG": {
        "ENABLE": False,
        "KEY": ""
    },
    "WEBHOOK": {
        "ENABLE": False,
        "URL": ""
    }
}

# ================= 🕷️ 爬虫设置 =================
SPIDER = {
    "HEADLESS": True,       # 是否隐藏浏览器窗口
    "TIMEOUT": 60000,       # 页面加载超时时间 (毫秒)
    "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "MAX_RETRIES": 3,
    "REQUEST_TIMEOUT": 60,
    "CHUNK_SIZE": 8192,
    "WAIT_AFTER_GOTO": 3000,
    "RANDOM_DELAY_MIN": 2,
    "RANDOM_DELAY_MAX": 5
}

# ================= ⚙️ 系统运行配置 =================
SYSTEM = {
    "MAX_WORKERS": 2,
    "LOG_LEVEL": "INFO",
    "WORKER_DELAY_MIN": 0.5,
    "WORKER_DELAY_MAX": 2.0,
    "LOG_MAX_BYTES": 5 * 1024 * 1024,
    "LOG_BACKUP_COUNT": 5
}
