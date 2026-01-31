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
import logging
import sys
import markdown
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# 初始化模块级日志
logger = logging.getLogger(__name__)

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

    # ==========================================
    # 🧱 原子组件：邮件构建
    # ==========================================

    def _markdown_to_html(self, text):
        """使用标准库 markdown 进行转换 (Pro Design)"""
        if not text: return ""
        
        # 扩展支持: extra (表格/脚注等), nl2br (换行转<br>)
        html = markdown.markdown(text, extensions=['extra', 'nl2br'])
        
        # --- 🎨 样式注入 (Mail Client Compatible) ---
        h3_style = 'color: #2c3e50; font-size: 16px; margin-top: 25px; margin-bottom: 15px; padding: 8px 12px; border-left: 4px solid #0056b3; background-color: #f8f9fa; border-radius: 0 4px 4px 0;'
        html = html.replace('<h3>', f'<h3 style="{h3_style}">')
        
        strong_style = 'color: #d9534f; background-color: #fdf2f2; padding: 0 4px; border-radius: 2px; font-weight: 600;'
        html = html.replace('<strong>', f'<strong style="{strong_style}">')
        
        ul_style = 'padding-left: 20px; color: #444; line-height: 1.8;'
        html = html.replace('<ul>', f'<ul style="{ul_style}">')
        
        a_style = 'color: #007bff; text-decoration: none; border-bottom: 1px dotted #007bff;'
        html = html.replace('<a href=', f'<a style="{a_style}" href=')
        
        return html

    def _generate_html_body(self, title, content):
        """生成精美的 HTML 邮件正文 (Pro Design)"""
        html_content = self._markdown_to_html(content)
        
        return f"""<!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
        </head>
        <body style="margin: 0; padding: 0; background-color: #f4f6f9; font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;">
            <div style="max-width: 640px; margin: 30px auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.08);">
                <div style="background: linear-gradient(135deg, #0056b3 0%, #004494 100%); padding: 30px 20px; text-align: center;">
                    <h2 style="color: #ffffff; margin: 0; font-size: 20px; line-height: 1.4; text-shadow: 0 1px 2px rgba(0,0,0,0.2);">{title}</h2>
                </div>
                <div style="padding: 30px; color: #333; line-height: 1.7; font-size: 15px;">
                    {html_content}
                </div>
                <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
                    <p style="margin: 0 0 10px 0; font-size: 12px; color: #999;">🤖 此邮件由 <strong>NUIST Bulletin Bot</strong> 自动生成</p>
                    <p style="margin: 0; font-size: 12px;">
                        <a href="https://github.com/LING71671/NUIST_Bulletin_Bot_PRO" style="color: #0056b3; text-decoration: none; font-weight: 500;">
                            ✨ 查看项目源码 (GitHub)
                        </a>
                    </p>
                </div>
            </div>
            <div style="text-align: center; padding: 20px; color: #aaa; font-size: 12px;">
                Powered by AI Summarizer
            </div>
        </body>
        </html>
        """

    def _create_email_message(self, title, html_body):
        """创建邮件对象并设置头部"""
        message = MIMEMultipart()
        message['From'] = formataddr(("NUIST公告助手", self.sender_email))
        to_header_list = [formataddr(("同学", email)) for email in self.receiver_emails]
        message['To'] = ", ".join(to_header_list)
        message['Subject'] = Header(f"🔔 {title}", 'utf-8')
        message.attach(MIMEText(html_body, 'html', 'utf-8'))
        return message

    def _add_single_attachment(self, message, file_path):
        """原子任务：添加单个附件"""
        if not os.path.exists(file_path): return

        try:
            ctype, encoding = mimetypes.guess_type(file_path)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)

            with open(file_path, 'rb') as f:
                mime = MIMEBase(maintype, subtype)
                mime.set_payload(f.read())

            encoders.encode_base64(mime)
            filename = os.path.basename(file_path)
            encoded_filename = Header(filename, 'utf-8').encode()
            mime.add_header('Content-Disposition', 'attachment', filename=encoded_filename)
            message.attach(mime)
            logger.info(f"    📎 [邮件] 添加附件: {filename}")
        except Exception as e:
            logger.warning(f"    ⚠️ 附件 {file_path} 添加失败: {e}")

    def _send_via_smtp(self, message, title):
        """原子任务：执行 SMTP 发送"""
        try:
            server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            server.login(self.sender_email, self.email_password)
            server.sendmail(self.sender_email, self.receiver_emails, message.as_string())
            server.quit()
            logger.info(f"    📧 [邮件] 群发成功 ({len(self.receiver_emails)}人): {title[:10]}...")
        except Exception as e:
            logger.error(f"    ❌ [邮件] 发送失败: {e}")
            raise e

    def send_email(self, title, content, attachments=None):
        if not self.enable_email: return
        try:
            html_body = self._generate_html_body(title, content)
            message = self._create_email_message(title, html_body)
            if attachments:
                for path in attachments:
                    self._add_single_attachment(message, path)
            self._send_via_smtp(message, title)
        except Exception as e:
            logger.error(f"    ❌ [邮件] 处理异常: {e}")
            raise e

    def send_qmsg(self, title, content):
        if not self.enable_qmsg or not self.qmsg_key: return
        try:
            txt_content = content.replace("**", "").replace("##", "").replace("📌", "[!]").replace("⏰", "[截止]")
            msg_text = f"【校内新公告】\n{title}\n\n{txt_content}\n\n(详细内容请查看邮件)"
            url = f"https://qmsg.zendee.cn/send/{self.qmsg_key}"
            data = {"msg": msg_text}
            requests.post(url, data=data, timeout=10)
            logger.info("    🐧 [Qmsg] QQ消息推送成功！")
        except Exception as e:
            logger.warning(f"    ⚠️ [Qmsg] 发送失败: {e}")

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
            logger.info("    🤖 [Webhook] 推送成功！")
        except Exception as e:
            logger.warning(f"    ⚠️ [Webhook] 发送失败: {e}")

    def send(self, title, summary, attachments=None):
        core_success = True
        if self.enable_email:
            try:
                self.send_email(title, summary, attachments)
            except Exception:
                core_success = False
        self.send_qmsg(title, summary)
        self.send_webhook(title, summary)
        return core_success

if __name__ == "__main__":
    pass
