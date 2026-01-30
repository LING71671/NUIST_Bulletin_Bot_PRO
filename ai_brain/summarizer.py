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
                temperature=0.1,
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
                for page in doc[:10]: # 限制前10页
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
        try:
            df = pd.read_excel(filepath, nrows=100).fillna("")
            if df.empty: return "[空Excel表格]"
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

            client = self.clients.get("zhipu")
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

    # ==========================================
    # 📉 复杂度优化：使用字典映射代替 if-else
    # ==========================================

    def process_attachments(self, file_paths):
        """处理附件内容 (低复杂度版)"""
        if not file_paths: return ""

        combined_text = ""
        print(f"    📎 正在预处理 {len(file_paths)} 个附件...")

        # 定义后缀与处理函数的映射表
        extractors = {
            '.pdf': self._extract_pdf,
            '.docx': self._extract_word,
            '.doc': self._extract_word,
            '.xlsx': self._extract_excel,
            '.xls': self._extract_excel,
            '.pptx': self._extract_ppt,
            '.ppt': self._extract_ppt,
            '.jpg': self._extract_image_content,
            '.jpeg': self._extract_image_content,
            '.png': self._extract_image_content
        }

        for path in file_paths:
            if not os.path.exists(path): continue

            ext = os.path.splitext(path)[1].lower()

            # 查表调用，代替 if-else
            handler = extractors.get(ext)

            if handler:
                content = handler(path)
                if content:
                    combined_text += f"\n\n--- 附件 ({os.path.basename(path)}) ---\n{content}\n"

        return combined_text

    # ==========================
    # 🧠 主逻辑
    # ==========================

    def summarize(self, fetch_result, title=None):
        if not fetch_result: return None

        web_text = fetch_result.get('text', '')
        files = fetch_result.get('files', [])

        # 1. 解析附件
        attach_text = self.process_attachments(files)

        # 2. 组装
        safe_title = title if title else (web_text.split('\n')[0] if web_text else "无标题")
        full_context = f"【公告标题】: {safe_title}\n\n【网页正文】:\n{web_text}\n{attach_text}"

        if len(full_context) < 20: return "IGNORE"

        # ================= 🛡️ 过滤层 (Hunter) =================

        # 白名单机制
        important_keywords = ["通知", "公告", "公示", "名单", "日程", "安排", "招标", "中标", "竞赛", "讲座", "大创", "补考", "申报"]
        is_force_keep = any(k in safe_title for k in important_keywords)

        if is_force_keep:
            print(f"    🛡️ 触发白名单，跳过过滤: {safe_title}")
        else:
            # 补全了之前省略的 Prompt
            filter_prompt = """
            你是一个学校通知审核员。请判断以下网页内容是否包含【实质性的通知、新闻、活动或公示信息】。
            
            🔴 判定为 NO (无价值) 的情况：
            1. 仅包含网站导航菜单、页脚、版权声明、友情链接。
            2. 页面提示“404”、“无访问权限”、“系统维护”、“测试页面”。
            3. 正文几乎为空，或仅有“附件”二字但无具体说明。
            4. 纯粹的商业广告。
            
            🟢 判定为 YES (有价值) 的情况：
            1. 包含具体的活动时间、地点、参与人员名单。
            2. 包含科研项目申报、截止日期、招标参数。
            3. 包含具体的新闻报道、会议纪要。
            
            请仅回答 YES 或 NO。
            """

            is_valuable = self._call_ai("hunter", filter_prompt, full_context[:2500])

            if is_valuable and is_valuable.strip().upper().startswith("NO"):
                return "IGNORE"

        # ================= 📝 总结层 (Prompt 增强版) =================

        # 补全了之前省略的 Prompt
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

        summary = self._call_ai("commander", summary_prompt, full_context[:12000])

        if not summary:
            print("    ⚠️ Commander 失败，切换 Strategist...")
            summary = self._call_ai("strategist", summary_prompt, full_context[:12000])

        if not summary:
            return "⚠️ AI 总结失败，请直接查看原文。"

        return summary