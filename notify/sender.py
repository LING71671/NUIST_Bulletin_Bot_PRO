import smtplib
import requests
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

class Notifier:
    def __init__(self):
        # ================= ⚙️ 配置读取 =================
        cfg = config.NOTIFY

        # 1. 邮件
        self.enable_email = cfg["EMAIL"]["ENABLE"]
        self.smtp_server = cfg["EMAIL"]["SMTP_SERVER"]
        self.smtp_port = cfg["EMAIL"]["SMTP_PORT"]
        self.sender_email = cfg["EMAIL"]["SENDER"]
        self.email_password = cfg["EMAIL"]["PASSWORD"]

        # 🔴 [核心修改1] 智能处理多收件人
        # 无论用户填的是 "a@qq.com" 还是 "a@qq.com, b@qq.com"，都统一转为列表
        raw_receiver = cfg["EMAIL"]["RECEIVER"]
        if "," in raw_receiver:
            # 如果有逗号，切开并去掉空格
            self.receiver_emails = [email.strip() for email in raw_receiver.split(",")]
        else:
            # 如果是单个，也放进列表里
            self.receiver_emails = [raw_receiver.strip()]

        # 2. Qmsg
        self.enable_qmsg = cfg["QMSG"]["ENABLE"]
        self.qmsg_key = cfg["QMSG"]["KEY"]

        # 3. Webhook
        self.enable_webhook = cfg["WEBHOOK"]["ENABLE"]
        self.webhook_url = cfg["WEBHOOK"]["URL"]

    def send_email(self, title, content):
        """发送富文本邮件 (支持群发)"""
        if not self.enable_email: return

        try:
            clean_content = content.replace("##", "").replace("**", "")

            message = MIMEMultipart()

            # 发件人
            message['From'] = formataddr(("NUIST公告助手", self.sender_email))

            # 🔴 [核心修改2] 构造群发邮件头
            # 生成类似: 同学 <a@qq.com>, 同学 <b@qq.com> 的格式
            # 这样所有收件人都能看到这封邮件是发给谁的
            to_header_list = [formataddr(("同学", email)) for email in self.receiver_emails]
            message['To'] = ", ".join(to_header_list)

            message['Subject'] = Header(f"🔔 {title}", 'utf-8')

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

            # 🔴 [核心修改3] 传递列表给 sendmail
            # 这里必须传 list，不能传 string
            server.sendmail(self.sender_email, self.receiver_emails, message.as_string())

            server.quit()
            print(f"    📧 [邮件] 群发成功 ({len(self.receiver_emails)}人): {title[:10]}...")
        except Exception as e:
            print(f"    ❌ [邮件] 发送失败: {e}")

    def send_qmsg(self, title, content):
        if not self.enable_qmsg or not self.qmsg_key: return
        try:
            txt_content = content.replace("**", "").replace("##", "").replace("📌", "[!]").replace("⏰", "[截止]")
            msg_text = f"【校内新公告】\n{title}\n\n{txt_content}\n\n(详细内容请查看邮件)"
            url = f"https://qmsg.zendee.cn/send/{self.qmsg_key}"
            data = {"msg": msg_text}
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
        self.send_email(title, summary)
        self.send_qmsg(title, summary)
        self.send_webhook(title, summary)

if __name__ == "__main__":
    print("🚀 正在测试群发功能...")
    notifier = Notifier()
    t_title = "测试: 多人邮件发送"
    t_content = "📌 **状态**：\n已支持多收件人\n请检查两个邮箱是否都收到了！"
    notifier.send(t_title, t_content)