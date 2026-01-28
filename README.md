# 🚀 NUIST Bulletin Bot (南信大公告自动推送助手)

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Playwright](https://img.shields.io/badge/Playwright-Browser-green)
![AI Powered](https://img.shields.io/badge/AI-DeepSeek%2FGLM%2FQwen-purple)
![License](https://img.shields.io/badge/License-MIT-orange)

一个基于 Python 的智能化校园公告监控系统，专为南京信息工程大学（NUIST）设计。
它能自动登录学校 VPN，监控最新“信息公告”，利用 AI 大模型自动阅读并生成摘要，最后通过多种渠道推送到你的手机。

拒绝错过重要通知，拒绝阅读八股文，让 AI 帮你划重点！

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

---

## 🛠️ 安装指南

### 1. 克隆项目
```bash
git clone [https://github.com/你的用户名/NUIST_Bulletin_Bot.git](https://github.com/你的用户名/NUIST_Bulletin_Bot.git)
cd NUIST_Bulletin_Bot
