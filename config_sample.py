# config_sample.py - 项目配置样本
# ⚠️ 使用说明：
# 1. 请将此文件重命名为 config.py
# 2. 在下方填入你的真实账号和Key

# ================= 🏫 学校账号配置 =================
SCHOOL = {
    "USERNAME": "",       # [必填] 你的学号，例如 "2022123456"
    "PASSWORD": "",       # [必填] 你的统一身份认证密码

    # VPN首页地址 (通常不用改，除非学校换域名了)
    "VPN_URL": "https://client.vpn.nuist.edu.cn/",

    # 登录跳转地址 (这是学校SSO的固定地址)
    "LOGIN_URL": "https://authserver.nuist.edu.cn/authserver/login?service=https://client.vpn.nuist.edu.cn/enlink/api/client/callback/cas"
}

# ================= 🤖 AI 模型配置 =================
# [选填] 填入你拥有的 Key，没有的留空即可
# 程序会自动跳过没填的厂商
AI_KEYS = {
    "deepseek": "",   # 推荐！DeepSeek API Key
    "aliyun": "",     # 阿里云通义千问 Key
    "silicon": "",    # 硅基流动 Key
    "zhipu": ""       # 智谱AI Key
}

# ================= 📢 推送通道配置 =================
NOTIFY = {
    # --- 📧 邮件推送 (推荐开启) ---
    "EMAIL": {
        "ENABLE": False,           # 改为 True 开启
        "SMTP_SERVER": "smtp.qq.com", # QQ邮箱填 smtp.qq.com，网易填 smtp.163.com
        "SMTP_PORT": 465,
        "SENDER": "",              # 发件人邮箱，例如 "123456@qq.com"
        "PASSWORD": "",            # [注意] 这里填邮箱的授权码，不是QQ密码！
        "RECEIVER": ""             # 收件人邮箱，可以和发件人一样
    },

    # --- 🐧 Qmsg酱 (QQ手机弹窗) ---
    # 获取地址: https://qmsg.zendee.cn/
    "QMSG": {
        "ENABLE": False,           # 改为 True 开启
        "KEY": ""                  # 填入你的 Qmsg Key
    },

    # --- 🤖 Webhook (钉钉/飞书/企业微信) ---
    "WEBHOOK": {
        "ENABLE": False,
        "URL": ""                  # 填入 Webhook 地址
    }
}