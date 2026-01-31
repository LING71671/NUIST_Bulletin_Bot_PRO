# 🚀 NUIST Bulletin Bot PRO

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Architecture](https://img.shields.io/badge/Architecture-Producer--Consumer-orange)
![ORM](https://img.shields.io/badge/ORM-SQLAlchemy-green)
![Playwright](https://img.shields.io/badge/Playwright-Browser-green)
![AI Powered](https://img.shields.io/badge/AI-DeepSeek%2FGLM%2FQwen-purple)
![License](https://img.shields.io/badge/License-GPLv3-red)

> **V2.2 Professional Edition**：基于 **多线程并发**、**ORM 状态机** 与 **配置化架构** 的工业级重构版本。

一个专为 **南京信息工程大学 (NUIST)** 师生打造的智能化公告监控系统。
它就像一个不知疲倦的 7x24 小时私人秘书，自动穿透学校 VPN，并发扫描最新通知，利用大模型阅读理解，并将精华内容通过精美的 HTML 邮件推送到你的手机。

拒绝“名单公示”刷屏，拒绝阅读八股文，让 AI 帮你划重点！
(readme文件由AI生成，可能会有夸大成分😂)

---

## ✨ 核心特性 (V2.2 Highlights)

### 🏗️ 工业级架构
*   **⚡ 多线程并发 (ThreadPool)**：基于生产-消费者模型，扫描与处理解耦。支持在 `config.py` 中自定义 `MAX_WORKERS` 并发数，抓取速度提升 300%+。
*   **💾 ORM 状态机**：基于 `SQLAlchemy` 重构数据层，每条公告拥有完整的生命周期 (`PENDING` -> `PROCESSING` -> `SUCCESS`/`FAILED`)，支持**断点续传**与**自动重试**。
*   **⚙️ 全局配置化**：爬虫行为（无头模式/超时）、系统性能、推送通道等所有参数均可通过 `config.py` 动态调整，无需修改代码。

### 🤖 深度智能化
*   **🔐 自动过墙登录**：内置 `Playwright` 浏览器内核，自动处理学校统一身份认证 (SSO) 及 VPN 跳转，集成 `ddddocr` 毫秒级识别验证码。
*   **🧠 全格式 AI 摘要**：
    *   **多模型支持**：DeepSeek (推荐)、通义千问、智谱 AI 等。
    *   **全格式解析**：自动下载并解析 PDF, Word, Excel, PPT 甚至 OCR 识别图片文字。
    *   **智能过滤**：精准识别并忽略无意义的“名单公示”、“纯图片占位”等低价值信息。

### 📢 极致阅读体验
*   **📧 Pro 级邮件渲染**：
    *   **Markdown 引擎**：将 AI 生成的摘要实时渲染为现代化的 HTML 卡片。
    *   **视觉优化**：品牌色 Header、高亮重点标注、附件自动挂载。
*   **📊 可视化日志**：集成 `coloredlogs`，提供赏心悦目的控制台输出与自动轮转的文件日志。

---

## 🛠️ 快速开始

### 1. 克隆项目
```bash
git clone https://github.com/LING71671/NUIST_Bulletin_Bot_PRO.git
cd NUIST_Bulletin_Bot_PRO
```

### 2. 环境准备
推荐使用虚拟环境：
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Mac / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
playwright install chromium
```

---

## ⚙️ 配置指南

### 第一步：初始化配置
将样本文件复制为真实配置文件：
```bash
# Windows
copy config_sample.py config.py

# Mac / Linux
cp config_sample.py config.py
```

### 第二步：修改 `config.py`

#### 1. 🏫 学校账号 (必须)
```python
SCHOOL = {
    "USERNAME": "2023xxxxxx",      # 你的学号
    "PASSWORD": "my_password",     # 统一身份认证密码
    # ... URL 配置通常无需修改
}
```

#### 2. 🤖 AI 模型 (推荐)
```python
AI_KEYS = {
    "deepseek": "sk-xxxxxxxx",     # 推荐填入 DeepSeek Key
    # ... 其他厂商留空即可，程序会自动选择可用的
}
```

#### 3. 🕷️ 爬虫设置 (V2.2 新增)
```python
SPIDER = {
    "HEADLESS": False,      # True=后台静默运行, False=显示浏览器(调试用)
    "TIMEOUT": 60000,       # 页面加载超时时间 (毫秒)
    "USER_AGENT": "..."     # 自定义 UA
}
```

#### 4. ⚙️ 系统性能 (V2.2 新增)
```python
SYSTEM = {
    "MAX_WORKERS": 2,       # 并发线程数。建议 1-3，过高可能触发防火墙。
    "LOG_LEVEL": "INFO"     # 日志级别
}
```

#### 5. 📧 推送通道
```python
NOTIFY = {
    "EMAIL": {
        "ENABLE": True,
        "SMTP_SERVER": "smtp.qq.com",
        "SENDER": "xxx@qq.com",
        "PASSWORD": "xxx",      # 邮箱授权码
        "RECEIVER": "xxx@qq.com"
    },
    # ... 支持 Qmsg 和 Webhook
}
```

---

## 🚀 运行

```bash
python main.py
```

*   **首次运行**：会自动初始化 `data/history.db` 数据库，并并发扫描最新的 5 条公告。
*   **增量运行**：机器人会自动识别已处理 (`SUCCESS`) 的公告并跳过，只推送真正的新消息。
*   **容错机制**：如果抓取或发送失败，任务会被标记为 `FAILED`，并在下一次运行时自动重试。

---

## 📈 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=LING71671/NUIST_Bulletin_Bot_PRO&type=Date)](https://star-history.com/#LING71671/NUIST_Bulletin_Bot_PRO&Date)

## 🤝 贡献者

<a href="https://github.com/LING71671/NUIST_Bulletin_Bot_PRO/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=LING71671/NUIST_Bulletin_Bot_PRO" />
</a>

## 📄 开源协议

本项目采用 **GPL-3.0** 协议。
Copyright (c) 2026 LING71671