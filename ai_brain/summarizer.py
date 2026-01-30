import os
import base64
import fitz  # PyMuPDF
import docx
import pandas as pd
from pptx import Presentation
from openai import OpenAI
import sys

# 引用根目录配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


KEYS = config.AI_KEYS
CLIENTS = {}
try:
    if KEYS["zhipu"]:
        CLIENTS["zhipu"] = OpenAI(api_key=KEYS["zhipu"], base_url="https://open.bigmodel.cn/api/paas/v4/")
    if KEYS["aliyun"]:
        CLIENTS["aliyun"] = OpenAI(api_key=KEYS["aliyun"], base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    if KEYS["deepseek"]:
        CLIENTS["deepseek"] = OpenAI(api_key=KEYS["deepseek"], base_url="https://api.deepseek.com")
    if KEYS["silicon"]:
        CLIENTS["silicon"] = OpenAI(api_key=KEYS["silicon"], base_url="https://api.siliconflow.cn/v1")
except Exception as e:
    print(f"⚠️ API Client 初始化警告: {e}")

MODELS = {
    "commander": ("deepseek", "deepseek-chat"),   # 主力总结
    "strategist": ("aliyun", "qwen-max"),         # 备用总结
    "hunter": ("zhipu", "glm-4-flash"),           # 快速过滤 (免费/便宜)
    "vision": ("zhipu", "glm-4v-flash")           # 视觉识别
}

class BulletinSummarizer:
    def __init__(self):
        self.clients = CLIENTS
        self.models = MODELS

    def _call_ai(self, role, system_prompt, user_content):
        """通用 AI 调用函数"""
        provider_name, model_name = self.models.get(role, ("deepseek", "deepseek-chat"))
        client = self.clients.get(provider_name)

        # 如果指定的服务商没配 Key，尝试降级 (这里简单处理，直接返回 None)
        if not client:
            print(f"    ⚠️ 未配置 {provider_name} 的 API Key，跳过 {role}")
            return None

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.1,  # 低温度，保证输出稳定
                timeout=45
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"    ⚠️ {role} [{model_name}] 调用失败: {e}")
            return None

    # ==========================
    # 📂 附件解析模块 (增强版)
    # ==========================

    def _extract_pdf(self, filepath):
        text = ""
        try:
            with fitz.open(filepath) as doc:
                # 读前 10 页，防止超大 PDF 消耗过多 Token
                for page in doc[:10]:
                    text += page.get_text()
            return text[:5000]
        except: return "[PDF解析错误]"

    def _extract_word(self, filepath):
        text = ""
        try:
            doc = docx.Document(filepath)
            for para in doc.paragraphs: text += para.text + "\n"
            return text[:5000]
        except: return "[Word解析错误]"

    def _extract_excel(self, filepath):
        """读取 Excel 并在 Markdown 中转为文本表格"""
        try:
            # 🔴 [修改] 增加读取行数到 100，防止漏掉名单
            df = pd.read_excel(filepath, nrows=100).fillna("")

            if df.empty:
                return "[空Excel表格]"

            # 转换为 Markdown 格式
            return df.to_markdown(index=False)[:4000]
        except Exception as e:
            return f"[Excel解析错误: {str(e)}]"

    def _extract_ppt(self, filepath):
        text = ""
        try:
            prs = Presentation(filepath)
            for slide in prs.slides[:15]:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
            return text[:4000]
        except Exception as e:
            return f"[PPT解析错误: {str(e)}]"

    def _extract_image_content(self, filepath):
        print(f"    👁️ 正在识别图片内容: {os.path.basename(filepath)}...")
        try:
            with open(filepath, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

            client = self.clients.get("zhipu") # 强制使用智谱 Vision
            if not client: return "[未配置Vision模型]"

            response = client.chat.completions.create(
                model="glm-4v-flash",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "提取图片中的所有文字，保持原有排版结构。"},
                            {"type": "image_url", "image_url": {"url": encoded_string}}
                        ]
                    }
                ],
                timeout=30
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"    ⚠️ 图片识别失败: {e}")
            return "[图片无法识别]"

    def process_attachments(self, file_paths):
        combined_text = ""
        if not file_paths: return ""

        print(f"    📎 正在预处理 {len(file_paths)} 个附件...")
        for path in file_paths:
            if not os.path.exists(path): continue

            ext = os.path.splitext(path)[1].lower()
            content = ""

            # 根据后缀分发处理
            if ext == '.pdf': content = self._extract_pdf(path)
            elif ext in ['.docx', '.doc']: content = self._extract_word(path)
            elif ext in ['.xlsx', '.xls']: content = self._extract_excel(path)
            elif ext in ['.pptx', '.ppt']: content = self._extract_ppt(path)
            elif ext in ['.jpg', '.jpeg', '.png']: content = self._extract_image_content(path)

            if content:
                combined_text += f"\n\n--- 附件 ({os.path.basename(path)}) ---\n{content}\n"

        return combined_text

    # ==========================
    # 🧠 主逻辑 (核心修复)
    # ==========================

    def summarize(self, fetch_result, title=None):
        """
        核心总结入口
        :param fetch_result: fetcher.py 返回的字典 {'text':..., 'files':...}
        :param title: 公告标题 (用于白名单过滤)
        """
        if not fetch_result: return None

        web_text = fetch_result.get('text', '')
        files = fetch_result.get('files', [])

        # 1. 解析附件
        attach_text = self.process_attachments(files)

        # 2. 组装完整上下文
        safe_title = title if title else (web_text.split('\n')[0] if web_text else "无标题")
        full_context = f"【公告标题】: {safe_title}\n\n【网页正文】:\n{web_text}\n{attach_text}"

        if len(full_context) < 20: return "IGNORE"

        # ================= 🛡️ 过滤层 (Hunter) =================
        # ... (保持之前的过滤逻辑不变) ...
        important_keywords = ["通知", "公告", "公示", "名单", "日程", "安排", "招标", "中标", "竞赛", "讲座", "大创", "补考", "申报"]
        is_force_keep = any(k in safe_title for k in important_keywords)

        if not is_force_keep:
            filter_prompt = "..." # (这里保持你之前的代码)
            # ...

        # ================= 📝 总结层 (Prompt 船新升级) =================

        # 🔴 修改核心：从“总结大意”改为“关键要素提取”
        summary_prompt = """
        你是一个专为高校师生服务的【信息提取助手】。请仔细阅读输入内容，提取关键信息，不要过度概括细节。

        请严格按照以下 Markdown 格式输出：

        📌 **标题**：(原标题，去除非必要修饰)

        🎯 **核心划重点**：
        - (保留具体的研究方向、比赛赛道、招聘岗位等细分列表，不要只写大类！例如：不要只写"农业"，要写"农业(含智慧农业、采后创新等)")
        - (保留具体的硬性要求，如：排名要求、特定专业、必须具备的证书)
        - (保留具体的金额、名额限制)
        - (如果包含"操作指引"，请简述关键步骤，如"需在系统备注栏填写XXX")

        📞 **联系方式**：
        - (提取文中的联系人、电话、邮箱、QQ群、办公地点。如果没有，写"无")

        📎 **附件/链接**：
        - (提取文中出现的重要网址、报名链接、附件名称)

        ⏰ **截止时间**：(精确提取日期和具体时间点)
        """

        # 上下文给大一点
        summary = self._call_ai("commander", summary_prompt, full_context[:12000])

        if not summary:
            print("    ⚠️ Commander 失败，切换 Strategist...")
            summary = self._call_ai("strategist", summary_prompt, full_context[:12000])

        if not summary:
            return "⚠️ AI 总结失败，请直接查看原文。"

        return summary