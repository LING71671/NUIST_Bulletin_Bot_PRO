import smtplib
import requests
import json
import os
import mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from email.utils import formataddr
import sys

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

        # 智能处理多收件人
        raw_receiver = cfg["EMAIL"]["RECEIVER"]
        if "," in raw_receiver:
            self.receiver_emails = [email.strip() for email in raw_receiver.split(",")]
        else:
            self.receiver_emails = [raw_receiver.strip()]

        # 2. Qmsg
        self.enable_qmsg = cfg["QMSG"]["ENABLE"]
        self.qmsg_key = cfg["QMSG"]["KEY"]

        # 3. Webhook
        self.enable_webhook = cfg["WEBHOOK"]["ENABLE"]
        self.webhook_url = cfg["WEBHOOK"]["URL"]

    def send_email(self, title, content, attachments=None):
        """发送富文本邮件 (支持群发 + 附件)"""
        if not self.enable_email: return

        try:
            clean_content = content.replace("##", "").replace("**", "")
            message = MIMEMultipart()

            # 发件人/收件人/标题
            message['From'] = formataddr(("NUIST公告助手", self.sender_email))
            to_header_list = [formataddr(("同学", email)) for email in self.receiver_emails]
            message['To'] = ", ".join(to_header_list)
            message['Subject'] = Header(f"🔔 {title}", 'utf-8')

            # 正文
            html_content = f"""
            <div style="font-family: '微软雅黑', sans-serif; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px; max-width: 600px;">
                <h2 style="color: #007bff; border-bottom: 2px solid #007bff; padding-bottom: 10px;">{title}</h2>
                <div style="white-space: pre-wrap; line-height: 1.6; color: #333; font-size: 15px; background-color: #f8f9fa; padding: 15px; border-radius: 5px;">
                    {clean_content}
                </div>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #999; text-align: center;">
                    来自 NUIST Bulletin Bot 🤖 | AI 自动摘要
                </p>
            </div>
            """
            message.attach(MIMEText(html_content, 'html', 'utf-8'))

            # 🟢 [核心升级] 处理附件
            if attachments:
                for file_path in attachments:
                    if not os.path.exists(file_path): continue
                    try:
                        # 猜测文件类型
                        ctype, encoding = mimetypes.guess_type(file_path)
                        if ctype is None or encoding is not None:
                            ctype = 'application/octet-stream'
                        maintype, subtype = ctype.split('/', 1)

                        # 读取并编码文件
                        with open(file_path, 'rb') as f:
                            mime = MIMEBase(maintype, subtype)
                            mime.set_payload(f.read())

                        encoders.encode_base64(mime)

                        # 🟢 修复：使用 Header 编码中文文件名，防止乱码
                        filename = os.path.basename(file_path)
                        # 这里是关键：先用 Header 编码，然后 decode 为字符串格式给 add_header 用
                        encoded_filename = Header(filename, 'utf-8').encode()

                        mime.add_header('Content-Disposition', 'attachment', filename=encoded_filename)
                        message.attach(mime)
                        print(f"    📎 [邮件] 添加附件: {filename}")
                    except Exception as e:
                        print(f"    ⚠️ 附件 {file_path} 添加失败: {e}")

            # 发送
            server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            server.login(self.sender_email, self.email_password)
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
        except: pass

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
        except: pass

    def send(self, title, summary, attachments=None):
        self.send_email(title, summary, attachments)
        self.send_qmsg(title, summary)
        self.send_webhook(title, summary)

if __name__ == "__main__":
    pass