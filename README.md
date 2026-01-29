# 🚀 NUIST Bulletin Bot (南信大公告自动推送助手)

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Playwright](https://img.shields.io/badge/Playwright-Browser-green)
![AI Powered](https://img.shields.io/badge/AI-DeepSeek%2FGLM%2FQwen-purple)
![License](https://img.shields.io/badge/License-GPLv3-red)

一个基于 Python 的智能化校园公告监控系统，专为南京信息工程大学（NUIST）设计。
它能自动登录学校 VPN，监控最新“信息公告”，利用 AI 大模型自动阅读并生成摘要，最后通过多种渠道推送到你的手机。

拒绝错过重要通知，拒绝阅读八股文，让 AI 帮你划重点！

> ⚠️ **说明**：本项目还在测试阶段，有很多代码没有优化，还需要努力。目前只为南信大定制，后续将会重构以增强兼容性。

---

## ✨ 核心功能

* **🔐 自动过墙登录**：基于 `Playwright` 模拟浏览器，自动通过学校统一身份认证（支持 VPN 跳转），集成了 `ddddocr` 自动识别并填充验证码。
* **🕷️ 智能爬虫**：自动扫描“信息公告”栏目，支持日期过滤，只抓取最新的有效通知，自动过滤置顶旧闻。
* **🧠 AI 大脑摘要**：
    * 集成 DeepSeek、通义千问（阿里）、智谱 AI 等多种大模型接口。
    * **全格式支持**：自动下载并解析正文及附件（PDF, Word, Excel, PPT），甚至能用 Vision 模型识别图片中的文字。
    * **智能过滤**：自动识别并忽略无意义的名单公示、纯图片占位符等“垃圾公告”。
* **📢 多通道推送**：
    * 📧 **邮件推送**：支持富文本（HTML）邮件，排版精美。
    * 🐧 **QQ 消息**：通过 Qmsg 酱推送到 QQ 手机端。
    * 🤖 **Webhook**：支持钉钉、飞书、企业微信机器人接入。
* **💾 数据持久化**：使用 SQLite 数据库自动去重，防止重复推送。

## 📈 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=LING71671/NUIST_Bulletin_Bot_PRO&type=Date)](https://star-history.com/#LING71671/NUIST_Bulletin_Bot_PRO&Date)
---

## 🛠️ 安装指南

### 1. 克隆项目
首先将项目下载到本地：
```bash
git clone [https://github.com/LING71671/NUIST_Bulletin_Bot_PRO.git](https://github.com/LING71671/NUIST_Bulletin_Bot_PRO.git)
cd NUIST_Bulletin_Bot_PRO
```
### 2. 创建虚拟环境
Windows:
```bash
python -m venv .venv
.\.venv\Scripts\activate
```
Mac / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```
### 3. 安装依赖包
```bash
pip install -r requirements.txt
```
### 4. 安装浏览器内核
```bash
playwright install chromium
```

## ⚙️ 配置指南

安装完成后，你需要告诉机器人你的账号和密码才能让它工作。

### 第一步：创建配置文件
在项目根目录下，你会看到一个名为 `config_sample.py` 的文件。
1.  **复制** 这个文件。
2.  将复制后的文件重命名为 **`config.py`**。

### 第二步：修改配置信息
用 PyCharm 或记事本打开刚才创建的 `config.py`，根据你的实际情况修改以下三处内容：

#### 1. 🏫 学校账号设置 
找到 `SCHOOL` 区域，填入你的统一身份认证账号和密码：

```python
SCHOOL = {
    "USERNAME": "2023123456",      # <--- 在引号里填入你的学号
    "PASSWORD": "my_password123",  # <--- 在引号里填入你的密码
    "VPN_URL": "[https://client.vpn.nuist.edu.cn/](https://client.vpn.nuist.edu.cn/)",
    "LOGIN_URL": "[https://authserver.nuist.edu.cn/authserver/login?service=https://client.vpn.nuist.edu.cn/enlink/api/client/callback/cas](https://authserver.nuist.edu.cn/authserver/login?service=https://client.vpn.nuist.edu.cn/enlink/api/client/callback/cas)"
}
```

#### 2.🤖 AI 模型设置
找到 AI_KEYS 区域。

```
AI_KEYS = {
    "deepseek": "sk-xxxxxxxxxxxxxxxxxxxxxxxx",  # <--- 填入你的 DeepSeek API Key
    "aliyun": "",     # 如果没有可以留空
    "silicon": "",
    "zhipu": ""
}
```

#### 3.📧 推送设置
找到 NOTIFY 区域。

```
NOTIFY = {
    "EMAIL": {
        "ENABLE": True,            # <--- 改为 True 开启功能
        "SMTP_SERVER": "smtp.qq.com",
        "SMTP_PORT": 465,
        "SENDER": "123456@qq.com", # <--- 发件人邮箱 (你的)
        "PASSWORD": "abcdefghijkl",# <--- 填入邮箱授权码 (不是QQ密码！)
        "RECEIVER": "123456@qq.com"# <--- 收件人邮箱 (通常和发件人一样)
    },
    "QMSG": {
        "ENABLE": False,           # 如果你有 Qmsg Key，改为 True
        "KEY": ""                  # Qmsg Key获取请去https://qmsg.zendee.cn/login获取
  },
    "WEBHOOK": {
        "ENABLE": False,
        "URL": ""
    }
}
```

## 🤝 贡献者 (Contributors)

<a href="https://github.com/LING71671/NUIST_Bulletin_Bot_PRO/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=LING71671/NUIST_Bulletin_Bot_PRO" />
</a>

## 📄 开源协议 (License)

本项目采用 **GPL-3.0** 开源协议。

这意味着你可以自由地使用、修改和分发本项目的源代码，但前提是：

1. **保持开源**：如果你修改了代码并发布，你的项目也必须开源。
2. **相同协议**：你的衍生项目必须继续使用 GPL-3.0 协议。
3. **版权声明**：必须保留原作者的版权声明。

详细协议内容请查看 [LICENSE](LICENSE) 文件。

---
Copyright (c) 2026 LING71671
