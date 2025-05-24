# ===============================
# mcp_client/models.py - AI模型接口
# ===============================
import asyncio
import aiohttp
import json
import logging
import base64
from typing import Dict, Any, List, Optional
import time

from config.settings import settings
from utils.exceptions import APIConnectionError

logger = logging.getLogger(__name__)

class NVIDIAModelClient:
    """NVIDIA API客户端"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.get_api_key()
        self.api_base = settings.get("models.api_base")
        self.session = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300),  # 5分钟超时
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()

    async def call_vision_model(self, model_name: str, image_data: str, prompt: str, max_tokens: int = 2000) -> Dict[str, Any]:
        """调用视觉模型"""
        url = f"{self.api_base}/chat/completions"

        # 构建请求数据
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }
                    }
                ]
            }
        ]

        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.1,  # 较低的温度，保证结果稳定
            "top_p": 0.95,
            "stream": False
        }

        try:
            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"NVIDIA API调用失败: {response.status} - {error_text}")
                    raise APIConnectionError(f"API调用失败: {response.status}")

                result = await response.json()
                return result

        except aiohttp.ClientError as e:
            logger.error(f"网络错误: {e}")
            raise APIConnectionError(f"网络连接错误: {e}")

    async def call_text_model(self, model_name: str, prompt: str, max_tokens: int = 1000) -> Dict[str, Any]:
        """调用文本模型"""
        url = f"{self.api_base}/chat/completions"

        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "top_p": 0.95,
            "stream": False
        }

        try:
            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"NVIDIA API调用失败: {response.status} - {error_text}")
                    raise APIConnectionError(f"API调用失败: {response.status}")

                result = await response.json()
                return result

        except aiohttp.ClientError as e:
            logger.error(f"网络错误: {e}")
            raise APIConnectionError(f"网络连接错误: {e}")

class MathGradingAI:
    """数学批改AI接口"""

    def __init__(self, api_key: str = None):
        self.client = NVIDIAModelClient(api_key)

    async def analyze_homework_image(self, image_data: str, grade_level: str, model_name: str) -> Dict[str, Any]:
        """分析作业图像"""
        prompt = self._build_homework_analysis_prompt(grade_level)

        start_time = time.time()

        async with self.client as client:
            response = await client.call_vision_model(model_name, image_data, prompt)

        processing_time = time.time() - start_time

        # 解析响应
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        try:
            # 尝试解析JSON格式的响应
            if content.strip().startswith('{'):
                result = json.loads(content)
            else:
                # 如果不是JSON，进行文本解析
                result = self._parse_text_response(content)

            result["processing_time"] = processing_time
            result["success"] = True

            return result

        except Exception as e:
            logger.error(f"解析模型响应失败: {e}")
            return {
                "success": False,
                "error_message": f"解析响应失败: {e}",
                "raw_response": content
            }

    async def generate_detailed_feedback(self, question_text: str, student_answer: str, correct_answer: str, model_name: str = None) -> str:
        """生成详细反馈"""
        model_name = model_name or settings.get("models.fallback")

        prompt = f"""请为学生的数学答案提供详细的教学反馈。

题目：{question_text}
学生答案：{student_answer}
正确答案：{correct_answer}

请提供：
1. 简明的错误指出
2. 正确的解题步骤
3. 学习建议
4. 鼓励性的话语

请用温和、鼓励的语气，帮助学生理解错误并改进。"""

        async with self.client as client:
            response = await client.call_text_model(model_name, prompt)

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content.strip()

    def _build_homework_analysis_prompt(self, grade_level: str) -> str:
        """构建作业分析提示词"""
        return f"""你是一个专业的{grade_level}数学老师。请仔细分析这张数学作业图片，并按照以下要求进行批改：

1. 识别图片中的所有数学题目
2. 识别学生的答案
3. 判断答案的正确性
4. 为错误答案提供简短反馈

请以JSON格式返回结果，包含以下字段：
{{
    "questions": [
        {{
            "question_number": 1,
            "question_text": "题目内容",
            "student_answer": "学生答案",
            "correct_answer": "正确答案",
            "score": 分数(0-10),
            "max_score": 10,
            "is_correct": true/false,
            "feedback": "简短反馈",
            "topic": "知识点",
            "difficulty": "easy/medium/hard"
        }}
    ],
    "total_questions": 题目总数
}}

注意：
- 请准确识别图片中的数学符号和数字
- 考虑{grade_level}的知识水平
- 给出公正、准确的评分
- 反馈要具有教学价值"""

    def _parse_text_response(self, content: str) -> Dict[str, Any]:
        """解析文本格式的响应"""
        # 这是一个简单的文本解析器，实际使用中可能需要更复杂的逻辑
        lines = content.split('\n')
        questions = []

        current_question = {}
        question_number = 1

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if '题目' in line or '问题' in line:
                if current_question:
                    questions.append(current_question)
                current_question = {
                    "question_number": question_number,
                    "question_text": line,
                    "student_answer": "",
                    "correct_answer": "",
                    "score": 0,
                    "max_score": 10,
                    "is_correct": False,
                    "feedback": "",
                    "topic": "未分类",
                    "difficulty": "medium"
                }
                question_number += 1
            elif '学生答案' in line or '答案' in line:
                current_question["student_answer"] = line.split('：')[-1] if '：' in line else line
            elif '正确' in line:
                current_question["correct_answer"] = line.split('：')[-1] if '：' in line else line
                current_question["is_correct"] = True
                current_question["score"] = 10
            elif '错误' in line:
                current_question["is_correct"] = False
                current_question["score"] = 0

        if current_question:
            questions.append(current_question)

        return {
            "questions": questions,
            "total_questions": len(questions)
        }