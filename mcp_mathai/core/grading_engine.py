# ===============================
# core/grading_engine.py
# ===============================

import asyncio
import base64
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger("grading_engine")

class GradingEngine:
    """原有的批改引擎接口 - 保持兼容性"""

    def __init__(self, mcp_client, model_selector):
        self.mcp_client = mcp_client
        self.model_selector = model_selector
        self.nvidia_api_key = settings.get_api_key()
        logger.info("初始化批改引擎")

    async def grade_homework(self, homework_id: int, image_path: str, grade_level: str) -> Dict[str, Any]:
        """批改作业 - 兼容接口"""
        logger.info(f"开始批改作业: ID={homework_id}, 年级={grade_level}")

        # 检查是否应该使用真正的AI批改
        if await self._should_use_ai_grading():
            logger.info("使用AI批改引擎")
            return await self._ai_grade_homework(homework_id, image_path, grade_level)
        else:
            logger.warning("AI服务不可用，使用基础批改模式")
            return await self._basic_grade_homework(homework_id, image_path, grade_level)

    async def _should_use_ai_grading(self) -> bool:
        """检查是否应该使用AI批改"""
        try:
            # 检查MCP客户端连接
            if not self.mcp_client:
                return False

            # 检查API密钥
            if not self.nvidia_api_key or self.nvidia_api_key == "nvapi-xxx":
                logger.warning("NVIDIA API密钥未配置")
                return False

            # 尝试简单的API调用测试
            test_response = await self._test_nvidia_api()
            return test_response

        except Exception as e:
            logger.error(f"AI服务检查失败: {e}")
            return False

    async def _test_nvidia_api(self) -> bool:
        """测试NVIDIA API连接"""
        try:
            # 简单的测试请求
            test_data = {
                "model": settings.get("models.nvidia.model"),
                "messages": [{"role": "user", "content": "测试连接"}],
                "max_tokens": 10
            }

            # 通过MCP客户端测试
            response = await self.mcp_client.call_tool("nvidia_chat", test_data)
            logger.info("NVIDIA API连接测试成功")
            return True

        except Exception as e:
            logger.warning(f"NVIDIA API连接测试失败: {e}")
            return False

    async def _ai_grade_homework(self, homework_id: int, image_path: str, grade_level: str) -> Dict[str, Any]:
        """真正的AI批改流程"""
        start_time = datetime.now()
        logger.info("🚀 开始AI批改流程")

        try:
            # 步骤1: 图像预处理
            logger.info("📸 步骤1: 图像预处理")
            processed_image = await self._process_image(image_path)

            # 步骤2: AI图像识别
            logger.info("🤖 步骤2: AI图像识别")
            ocr_results = await self._ai_image_recognition(processed_image, grade_level)

            # 步骤3: AI题目分析
            logger.info("📝 步骤3: AI题目分析")
            analyzed_questions = await self._ai_analyze_questions(ocr_results, grade_level)

            # 步骤4: AI批改
            logger.info("✏️ 步骤4: AI智能批改")
            graded_questions = await self._ai_grade_questions(analyzed_questions, grade_level)

            # 步骤5: 生成AI反馈
            logger.info("💬 步骤5: 生成AI反馈")
            ai_feedback = await self._generate_ai_feedback(graded_questions, grade_level)

            # 步骤6: 生成练习题
            logger.info("📚 步骤6: 生成练习题")
            practice_problems = await self._generate_practice_problems(graded_questions, grade_level)

            # 编译结果
            processing_time = (datetime.now() - start_time).total_seconds()
            final_results = self._compile_ai_results(
                graded_questions, ai_feedback, practice_problems,
                processing_time, grade_level
            )

            logger.info(f"✅ AI批改完成，用时: {processing_time:.2f}秒")
            return final_results

        except Exception as e:
            logger.error(f"❌ AI批改失败: {e}")
            # 如果AI批改失败，降级到基础模式
            return await self._basic_grade_homework(homework_id, image_path, grade_level)

    async def _process_image(self, image_path: str) -> Dict[str, Any]:
        """图像预处理"""
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # 转换为base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            return {
                "path": image_path,
                "base64": image_base64,
                "size": len(image_data)
            }

        except Exception as e:
            logger.error(f"图像处理失败: {e}")
            raise

    async def _ai_image_recognition(self, processed_image: Dict[str, Any], grade_level: str) -> Dict[str, Any]:
        """AI图像识别"""
        try:
            prompt = f"""
            请分析这张{grade_level}数学作业图片，识别出所有题目和学生答案。

            返回JSON格式：
            {{
                "questions": [
                    {{
                        "number": 1,
                        "question_text": "题目内容",
                        "student_answer": "学生答案",
                        "confidence": 0.95
                    }}
                ],
                "total_questions": 题目数量
            }}
            """

            request_data = {
                "model": settings.get("models.nvidia.model"),
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{processed_image['base64']}"}
                            }
                        ]
                    }
                ],
                "max_tokens": 2000,
                "temperature": 0.1
            }

            response = await self.mcp_client.call_tool("nvidia_vision", request_data)

            # 解析响应
            if isinstance(response, str):
                try:
                    return json.loads(response)
                except:
                    return {"questions": [], "total_questions": 0, "error": "解析失败"}

            return response

        except Exception as e:
            logger.error(f"AI图像识别失败: {e}")
            raise

    async def _ai_analyze_questions(self, ocr_results: Dict[str, Any], grade_level: str) -> List[Dict[str, Any]]:
        """AI分析题目"""
        try:
            questions = ocr_results.get("questions", [])
            analyzed = []

            for q in questions:
                prompt = f"""
                分析这道{grade_level}数学题：
                题目：{q.get('question_text', '')}
                学生答案：{q.get('student_answer', '')}

                返回JSON：
                {{
                    "question_type": "题目类型",
                    "topic": "知识点",
                    "difficulty": "难度",
                    "correct_answer": "正确答案",
                    "solution_steps": ["解题步骤"]
                }}
                """

                request_data = {
                    "model": settings.get("models.nvidia.model"),
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.1
                }

                analysis = await self.mcp_client.call_tool("nvidia_chat", request_data)

                if isinstance(analysis, str):
                    try:
                        analysis = json.loads(analysis)
                    except:
                        analysis = {"question_type": "计算题", "topic": "未知", "difficulty": "中等"}

                # 合并数据
                analyzed_q = {**q, **analysis}
                analyzed.append(analyzed_q)

            return analyzed

        except Exception as e:
            logger.error(f"AI题目分析失败: {e}")
            raise

    async def _ai_grade_questions(self, questions: List[Dict[str, Any]], grade_level: str) -> List[Dict[str, Any]]:
        """AI批改题目"""
        try:
            graded = []

            for q in questions:
                prompt = f"""
                批改这道{grade_level}数学题：
                题目：{q.get('question_text', '')}
                正确答案：{q.get('correct_answer', '')}
                学生答案：{q.get('student_answer', '')}

                返回JSON：
                {{
                    "is_correct": true/false,
                    "score": 得分,
                    "max_score": 10,
                    "feedback": "详细反馈",
                    "errors": ["错误点"]
                }}
                """

                request_data = {
                    "model": settings.get("models.nvidia.model"),
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 800,
                    "temperature": 0.1
                }

                grading = await self.mcp_client.call_tool("nvidia_chat", request_data)

                if isinstance(grading, str):
                    try:
                        grading = json.loads(grading)
                    except:
                        grading = {"is_correct": False, "score": 0, "max_score": 10, "feedback": "批改失败"}

                graded_q = {**q, **grading}
                graded.append(graded_q)

            return graded

        except Exception as e:
            logger.error(f"AI批改失败: {e}")
            raise

    async def _generate_ai_feedback(self, graded_questions: List[Dict[str, Any]], grade_level: str) -> Dict[str, Any]:
        """生成AI反馈"""
        try:
            correct_count = sum(1 for q in graded_questions if q.get('is_correct', False))
            total_questions = len(graded_questions)

            prompt = f"""
            为{grade_level}学生生成综合学习反馈：
            总题数：{total_questions}
            正确数：{correct_count}
            
            返回JSON：
            {{
                "overall_assessment": "整体评价",
                "strengths": ["优势"],
                "weaknesses": ["不足"],
                "suggestions": ["建议"]
            }}
            """

            request_data = {
                "model": settings.get("models.nvidia.model"),
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.3
            }

            feedback = await self.mcp_client.call_tool("nvidia_chat", request_data)

            if isinstance(feedback, str):
                try:
                    return json.loads(feedback)
                except:
                    return {"overall_assessment": "批改完成", "suggestions": ["继续努力"]}

            return feedback

        except Exception as e:
            logger.error(f"AI反馈生成失败: {e}")
            return {"overall_assessment": "批改完成", "suggestions": ["继续努力"]}

    async def _generate_practice_problems(self, graded_questions: List[Dict[str, Any]], grade_level: str) -> List[Dict[str, Any]]:
        """生成练习题"""
        try:
            # 找出错误的知识点
            error_topics = []
            for q in graded_questions:
                if not q.get('is_correct', False):
                    topic = q.get('topic', '基础运算')
                    if topic not in error_topics:
                        error_topics.append(topic)

            if not error_topics:
                return []

            practice_problems = []
            for topic in error_topics[:2]:  # 最多2个知识点
                prompt = f"""
                为{grade_level}学生生成关于"{topic}"的练习题：
                
                返回JSON：
                {{
                    "topic": "{topic}",
                    "problems": [
                        {{
                            "question": "题目",
                            "answer": "答案",
                            "hint": "提示"
                        }}
                    ]
                }}
                """

                request_data = {
                    "model": settings.get("models.nvidia.model"),
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.5
                }

                problems = await self.mcp_client.call_tool("nvidia_chat", request_data)

                if isinstance(problems, str):
                    try:
                        problems = json.loads(problems)
                        practice_problems.append(problems)
                    except:
                        pass

            return practice_problems

        except Exception as e:
            logger.error(f"练习题生成失败: {e}")
            return []

    def _compile_ai_results(self, graded_questions: List[Dict[str, Any]],
                            ai_feedback: Dict[str, Any],
                            practice_problems: List[Dict[str, Any]],
                            processing_time: float,
                            grade_level: str) -> Dict[str, Any]:
        """编译AI批改结果"""

        # 转换为标准格式
        results = []
        for q in graded_questions:
            result = {
                "question_text": q.get("question_text", ""),
                "student_answer": q.get("student_answer", ""),
                "correct_answer": q.get("correct_answer", ""),
                "score": q.get("score", 0),
                "max_score": q.get("max_score", 10),
                "is_correct": q.get("is_correct", False),
                "initial_feedback": q.get("feedback", ""),
                "enhanced_feedback": q.get("feedback", "") + "\n" + "\n".join(q.get("errors", [])),
                "topic": q.get("topic", "基础数学"),
                "difficulty": q.get("difficulty", "中等"),
                "question_type": q.get("question_type", "计算题")
            }
            results.append(result)

        # 计算统计信息
        total_questions = len(results)
        correct_count = sum(1 for r in results if r["is_correct"])
        total_score = sum(r["score"] for r in results)
        max_total_score = sum(r["max_score"] for r in results)

        return {
            "success": True,
            "mode": "ai_powered",  # 重要：标识这是AI处理的结果
            "results": results,
            "statistics": {
                "total_questions": total_questions,
                "correct_count": correct_count,
                "accuracy_rate": (correct_count / total_questions * 100) if total_questions > 0 else 0,
                "total_score": total_score,
                "max_total_score": max_total_score,
                "score_percentage": (total_score / max_total_score * 100) if max_total_score > 0 else 0,
                "topic_breakdown": {}  # 可以进一步完善
            },
            "ai_feedback": ai_feedback,
            "practice_problems": practice_problems,
            "processing_time": processing_time,
            "grade_level": grade_level,
            "ai_features_used": [
                "AI图像识别",
                "智能题目分析",
                "AI批改引擎",
                "个性化反馈",
                "针对性练习题"
            ]
        }

    async def _basic_grade_homework(self, homework_id: int, image_path: str, grade_level: str) -> Dict[str, Any]:
        """基础批改模式 - 当AI不可用时使用"""
        logger.warning("使用基础批改模式")

        # 基本的图像处理
        try:
            with open(image_path, 'rb') as f:
                image_size = len(f.read())
        except:
            image_size = 0

        # 模拟基本结果
        mock_results = {
            "success": True,
            "mode": "basic",  # 标识为基础模式
            "results": [
                {
                    "question_text": f"检测到{grade_level}数学作业",
                    "student_answer": "图像分析中...",
                    "correct_answer": "需要AI服务支持",
                    "score": 5,
                    "max_score": 10,
                    "is_correct": False,
                    "initial_feedback": "系统正在基础模式下运行",
                    "enhanced_feedback": "请检查:\n1. NVIDIA API密钥配置\n2. 网络连接状态\n3. MCP服务状态",
                    "topic": grade_level,
                    "difficulty": "未知",
                    "question_type": "混合题型"
                }
            ],
            "statistics": {
                "total_questions": 1,
                "correct_count": 0,
                "accuracy_rate": 0.0,
                "total_score": 5.0,
                "max_total_score": 10.0,
                "score_percentage": 50.0
            },
            "ai_feedback": {
                "overall_assessment": "系统运行在基础模式，功能受限",
                "suggestions": ["配置AI服务以获得完整功能"]
            },
            "practice_problems": [],
            "processing_time": 0.1,
            "grade_level": grade_level,
            "ai_features_used": ["基础图像检测"]
        }

        return mock_results


# ===============================
# 为了向后兼容，也创建 RealGradingEngine 别名
# ===============================

RealGradingEngine = GradingEngine  # 别名，指向同一个类

# ===============================
# 导出所有需要的类
# ===============================

__all__ = ['GradingEngine', 'RealGradingEngine']