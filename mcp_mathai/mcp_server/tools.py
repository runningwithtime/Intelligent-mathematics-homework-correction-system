# ===============================
# mcp_server/tools.py - MCP工具定义
# ===============================
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import json
import logging
import base64
from pathlib import Path

logger = logging.getLogger(__name__)

class MCPTool(BaseModel):
    """MCP工具基类"""
    name: str
    description: str
    parameters: Dict[str, Any]

class AnalyzeHomeworkRequest(BaseModel):
    """分析作业请求"""
    image_data: str = Field(description="Base64编码的图像数据")
    grade_level: str = Field(description="年级水平", example="高一")
    subject: str = Field(default="数学", description="学科")
    analysis_type: str = Field(default="full", description="分析类型: full, quick, detailed")

class AnalyzeHomeworkResponse(BaseModel):
    """分析作业响应"""
    success: bool
    questions: List[Dict[str, Any]]
    total_questions: int
    processing_time: float
    error_message: Optional[str] = None

class GenerateFeedbackRequest(BaseModel):
    """生成反馈请求"""
    question_text: str = Field(description="题目内容")
    student_answer: str = Field(description="学生答案")
    correct_answer: str = Field(description="正确答案")
    feedback_type: str = Field(default="detailed", description="反馈类型: brief, detailed, encouraging")

class GenerateFeedbackResponse(BaseModel):
    """生成反馈响应"""
    success: bool
    feedback: str
    suggestions: List[str]
    difficulty_level: str
    error_message: Optional[str] = None

class ExtractTextRequest(BaseModel):
    """提取文本请求"""
    image_data: str = Field(description="Base64编码的图像数据")
    extraction_type: str = Field(default="math", description="提取类型: math, text, mixed")

class ExtractTextResponse(BaseModel):
    """提取文本响应"""
    success: bool
    extracted_text: str
    confidence: float
    regions: List[Dict[str, Any]]
    error_message: Optional[str] = None

class MathGradingTools:
    """数学批改系统MCP工具集"""

    def __init__(self):
        self.tools = self._define_tools()

    def _define_tools(self) -> List[MCPTool]:
        """定义所有可用工具"""
        return [
            MCPTool(
                name="analyze_homework",
                description="分析数学作业图像，识别题目并进行批改",
                parameters={
                    "type": "object",
                    "properties": {
                        "image_data": {
                            "type": "string",
                            "description": "Base64编码的作业图像数据"
                        },
                        "grade_level": {
                            "type": "string",
                            "description": "学生年级水平",
                            "enum": ["初一", "初二", "初三", "高一", "高二", "高三"]
                        },
                        "subject": {
                            "type": "string",
                            "description": "学科类型",
                            "default": "数学"
                        },
                        "analysis_type": {
                            "type": "string",
                            "description": "分析详细程度",
                            "enum": ["quick", "full", "detailed"],
                            "default": "full"
                        }
                    },
                    "required": ["image_data", "grade_level"]
                }
            ),

            MCPTool(
                name="generate_detailed_feedback",
                description="为错误答案生成详细的教学反馈",
                parameters={
                    "type": "object",
                    "properties": {
                        "question_text": {
                            "type": "string",
                            "description": "题目内容"
                        },
                        "student_answer": {
                            "type": "string",
                            "description": "学生的答案"
                        },
                        "correct_answer": {
                            "type": "string",
                            "description": "正确答案"
                        },
                        "feedback_type": {
                            "type": "string",
                            "description": "反馈类型",
                            "enum": ["brief", "detailed", "encouraging"],
                            "default": "detailed"
                        }
                    },
                    "required": ["question_text", "student_answer", "correct_answer"]
                }
            ),

            MCPTool(
                name="extract_text_from_image",
                description="从图像中提取文本内容",
                parameters={
                    "type": "object",
                    "properties": {
                        "image_data": {
                            "type": "string",
                            "description": "Base64编码的图像数据"
                        },
                        "extraction_type": {
                            "type": "string",
                            "description": "提取类型",
                            "enum": ["math", "text", "mixed"],
                            "default": "math"
                        }
                    },
                    "required": ["image_data"]
                }
            ),

            MCPTool(
                name="validate_math_expression",
                description="验证数学表达式的正确性",
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "数学表达式"
                        },
                        "expected_result": {
                            "type": "string",
                            "description": "期望结果"
                        },
                        "grade_level": {
                            "type": "string",
                            "description": "年级水平"
                        }
                    },
                    "required": ["expression"]
                }
            ),

            MCPTool(
                name="generate_similar_problems",
                description="基于错误题目生成相似的练习题",
                parameters={
                    "type": "object",
                    "properties": {
                        "original_question": {
                            "type": "string",
                            "description": "原始题目"
                        },
                        "difficulty_level": {
                            "type": "string",
                            "description": "难度级别",
                            "enum": ["easier", "same", "harder"],
                            "default": "same"
                        },
                        "count": {
                            "type": "integer",
                            "description": "生成题目数量",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 3
                        }
                    },
                    "required": ["original_question"]
                }
            )
        ]

    def get_tool_by_name(self, name: str) -> Optional[MCPTool]:
        """根据名称获取工具"""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def get_all_tools(self) -> List[MCPTool]:
        """获取所有工具"""
        return self.tools

    def get_tools_schema(self) -> Dict[str, Any]:
        """获取工具的JSON Schema格式"""
        schema = {
            "tools": []
        }

        for tool in self.tools:
            tool_schema = {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.parameters
            }
            schema["tools"].append(tool_schema)

        return schema

# 全局工具实例
math_grading_tools = MathGradingTools()