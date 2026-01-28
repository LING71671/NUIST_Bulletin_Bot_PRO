import smtplib
import requests
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

class Notifier:
    def __init__(self):
        # ================= ⚙️ 配置读取 =================
        cfg = config.NOTIFY # 偷懒写法，简化代码

        # 1. 邮件
        self.enable_email = cfg["EMAIL"]["ENABLE"]
        self.smtp_server = cfg["EMAIL"]["SMTP_SERVER"]
        self.smtp_port = cfg["EMAIL"]["SMTP_PORT"]
        self.sender_email = cfg["EMAIL"]["SENDER"]
        self.email_password = cfg["EMAIL"]["PASSWORD"]
        self.receiver_email = cfg["EMAIL"]["RECEIVER"]

        # 2. Qmsg
        self.enable_qmsg = cfg["QMSG"]["ENABLE"]
        self.qmsg_key = cfg["QMSG"]["KEY"]

        # 3. Webhook
        self.enable_webhook = cfg["WEBHOOK"]["ENABLE"]
        self.webhook_url = cfg["WEBHOOK"]["URL"]

    def send_email(self, title, content):
        """发送富文本邮件"""
        if not self.enable_email: return

        try:
            # 简单清洗 markdown，防止邮件里出现太多 ** ##
            clean_content = content.replace("##", "").replace("**", "")

            message = MIMEMultipart()
            message['From'] = Header(f"NUIST公告助手 <{self.sender_email}>", 'utf-8')
            message['To'] = Header("同学", 'utf-8')
            message['Subject'] = Header(f"🔔 {title}", 'utf-8')

            # HTML 样式优化，电脑手机看都很舒服
            html_content = f"""
            <div style="font-family: '微软雅黑', sans-serif; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px; max-width: 600px;">
                <h2 style="color: #007bff; border-bottom: 2px solid #007bff; padding-bottom: 10px;">{title}</h2>
                <div style="white-space: pre-wrap; line-height: 1.6; color: #333; font-size: 15px; background-color: #f8f9fa; padding: 15px; border-radius: 5px;">
                    {clean_content}
                </div>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #999; text-align: center;">来自 NUIST Bulletin Bot 🤖 | AI 自动摘要</p>
            </div>
            """
            message.attach(MIMEText(html_content, 'html', 'utf-8'))

            server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            server.login(self.sender_email, self.email_password)
            server.sendmail(self.sender_email, [self.receiver_email], message.as_string())
            server.quit()
            print(f"    📧 [邮件] 推送成功: {title[:10]}...")
        except Exception as e:
            print(f"    ❌ [邮件] 发送失败: {e}")

    def send_qmsg(self, title, content):
        """发送 QQ 私聊消息 (Qmsg)"""
        if not self.enable_qmsg or not self.qmsg_key: return

        try:
            # Qmsg 主要是手机看，做一些文本精简
            # 把 markdown 的加粗符号去掉，把 emoji 换成文字
            txt_content = content.replace("**", "").replace("##", "").replace("📌", "[!]").replace("⏰", "[截止]")

            # 拼接消息文本
            msg_text = f"【校内新公告】\n{title}\n\n{txt_content}\n\n(详细内容请查看邮件)"

            # 发送请求
            url = f"https://qmsg.zendee.cn/send/{self.qmsg_key}"
            data = {
                "msg": msg_text
            }

            resp = requests.post(url, data=data, timeout=10)

            if resp.status_code == 200 and resp.json()['success']:
                print("    🐧 [Qmsg] QQ消息推送成功！")
            else:
                print(f"    ⚠️ [Qmsg] 响应异常: {resp.text}")

        except Exception as e:
            print(f"    ❌ [Qmsg] 推送失败: {e}")

    def send_webhook(self, title, content):
        if not self.enable_webhook or not self.webhook_url: return
        try:
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": f"### {title}\n\n{content}\n\n> 🤖 NUIST Bot"
                }
            }
            requests.post(self.webhook_url, json=data)
            print("    🤖 [Webhook] 推送成功！")
        except Exception as e:
            print(f"    ❌ [Webhook] 发送失败: {e}")

    def send(self, title, summary):
        """统一发送入口：所有开启的通道都会发一遍"""
        self.send_email(title, summary)
        self.send_qmsg(title, summary)
        self.send_webhook(title, summary)

# --- 测试代码 ---
if __name__ == "__main__":
    print("🚀 正在测试双通道推送...")
    notifier = Notifier()

    # 模拟一条数据
    t_title = "2026年奖学金评选通知(程序测试信息，没有真实性)"
    t_content = "📌 **要点**：\n1. 综合测评排名需在前30%\n2. 无挂科记录\n⏰ **截止时间**：2026-03-15"

    notifier.send(t_title, t_content)