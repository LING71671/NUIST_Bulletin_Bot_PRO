import os
import base64
import fitz  # PyMuPDF
import docx
import pandas as pd
from pptx import Presentation
from openai import OpenAI
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # 这一行是为了能让子目录的文件找到根目录的 config
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
    "commander": ("deepseek", "deepseek-chat"),
    "strategist": ("aliyun", "qwen-max"),
    "hunter": ("zhipu", "glm-4-flash"),
    "vision": ("zhipu", "glm-4v-flash")
}

# ==========================================
# 🧠 核心逻辑类
# ==========================================

class BulletinSummarizer:
    def __init__(self):
        self.clients = CLIENTS
        self.models = MODELS

    def _call_ai(self, role, system_prompt, user_content):
        provider_name, model_name = self.models.get(role, ("deepseek", "deepseek-chat"))
        client = self.clients.get(provider_name)
        if not client: return None

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.1, # ⚠️ 调低温度，让判断更死板准确
                timeout=45
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"    ⚠️ {role} 调用失败: {e}")
            return None

    # === 📄 文本/PDF 解析 ===
    def _extract_pdf(self, filepath):
        text = ""
        try:
            with fitz.open(filepath) as doc:
                for page in doc[:5]: text += page.get_text()
            return text[:3000]
        except: return "[PDF解析错误]"

    def _extract_word(self, filepath):
        text = ""
        try:
            doc = docx.Document(filepath)
            for para in doc.paragraphs: text += para.text + "\n"
            return text[:3000]
        except: return "[Word解析错误]"

    # === 📊 表格/PPT 解析 ===
    def _extract_excel(self, filepath):
        """读取 Excel 并在 Markdown 中转为文本表格"""
        try:
            # 读取 Excel，将 NaN (空单元格) 替换为 "[空]"，方便 AI 识别这是个空表
            df = pd.read_excel(filepath, nrows=30).fillna("")

            # 检查是否几乎没有数据 (行数少 或 大部分是空)
            if df.empty:
                return "[空Excel表格]"

            return df.to_markdown(index=False)[:3000]
        except Exception as e:
            return f"[Excel解析错误: {str(e)}]"

    def _extract_ppt(self, filepath):
        text = ""
        try:
            prs = Presentation(filepath)
            for slide in prs.slides[:10]:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
            return text[:3000]
        except Exception as e:
            return f"[PPT解析错误: {str(e)}]"

    # === 👁️ 图片解析 ===
    def _extract_image_content(self, filepath):
        print(f"    👁️ 正在识别图片内容: {os.path.basename(filepath)}...")
        try:
            with open(filepath, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

            client = self.clients.get("zhipu")
            response = client.chat.completions.create(
                model="glm-4v-flash",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "提取图片文字。"},
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

            if ext == '.pdf':
                content = self._extract_pdf(path)
            elif ext in ['.docx']:
                content = self._extract_word(path)
            elif ext in ['.xlsx', '.xls']:
                content = self._extract_excel(path)
            elif ext in ['.pptx']:
                content = self._extract_ppt(path)
            elif ext in ['.jpg', '.jpeg', '.png']:
                content = self._extract_image_content(path)

            if content:
                combined_text += f"\n\n--- 附件 ({os.path.basename(path)}) 内容 ---\n{content}"

        return combined_text

    def summarize(self, fetch_result):
        if not fetch_result: return None

        web_text = fetch_result.get('text', '')
        files = fetch_result.get('files', [])
        attach_text = self.process_attachments(files)
        full_context = f"【网页正文】:\n{web_text}\n{attach_text}"

        if len(full_context) < 10: return "IGNORE"

        # 1. 过滤垃圾信息
        filter_prompt = "判断内容是否为无意义广告/占位符？回答YES(有价值)或NO(无价值)。"
        is_valuable = self._call_ai("hunter", filter_prompt, full_context[:800])
        if is_valuable and "NO" in is_valuable.upper(): return "IGNORE"

        # 2. 总结 (新增：空表检测逻辑)
        summary_prompt = """
        你是一个学校公告助手。请分析输入内容（含网页正文和附件内容）。
        
        🔴 **最高优先级判定规则**：
        如果附件内容主要是一个**等待填写的空白表格、表单或模板**（例如：只有表头没有数据行的Excel、包含"姓名/学号"留空的申请表、Word模板），且正文中没有其他实质性通知内容。
        >>> 请不要生成摘要，直接返回： **有{需要填写文件的数量}个{文件格式}需要填写**
        
        🔵 **正常情况（如果包含具体通知内容）**：
        请生成结构化摘要，格式如下：
        📌 **标题**：(一句话概括)
        📝 **划重点**：
        - (要点1)
        - (要点2)
        ⏰ **截止时间**：(日期或"无")
        """

        # 尝试使用 Commander (DeepSeek)
        summary = self._call_ai("commander", summary_prompt, full_context[:8000])

        # 容错降级
        if not summary:
            print("    ⚠️ Commander 失败，切换 Strategist...")
            summary = self._call_ai("strategist", summary_prompt, full_context[:10000])

        return summary