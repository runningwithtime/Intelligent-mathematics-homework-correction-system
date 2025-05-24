# ===============================
# core/model_selector.py - 模型选择器
# ===============================
from enum import Enum
from typing import List, Dict, Any, Optional
import logging

class ModelType(Enum):
    """模型类型"""
    VISION = "vision"  # 视觉模型，用于图像分析
    TEXT = "text"      # 文本模型，用于反馈生成
    MATH = "math"      # 数学专用模型

class ModelInfo:
    """模型信息"""
    def __init__(self, name: str, model_type: ModelType, max_tokens: int, cost_per_token: float = 0.0):
        self.name = name
        self.type = model_type
        self.max_tokens = max_tokens
        self.cost_per_token = cost_per_token

class ModelSelector:
    """智能模型选择器"""

    def __init__(self):
        self.available_models = {
            "nvidia/llama-3.2-90b-vision-instruct": ModelInfo(
                "nvidia/llama-3.2-90b-vision-instruct",
                ModelType.VISION,
                4000
            ),
            "nvidia/llama-3.1-8b-instruct": ModelInfo(
                "nvidia/llama-3.1-8b-instruct",
                ModelType.TEXT,
                2000
            ),
            "nvidia/llama-3.1-70b-instruct": ModelInfo(
                "nvidia/llama-3.1-70b-instruct",
                ModelType.MATH,
                4000
            )
        }
        self.logger = logging.getLogger(__name__)

    def select_model(self, task_type: str, image_included: bool = False, complexity: str = "medium") -> str:
        """
        智能选择最适合的模型

        Args:
            task_type: 任务类型 (grading, feedback, analysis)
            image_included: 是否包含图像
            complexity: 复杂度 (low, medium, high)
        """
        if image_included and task_type == "grading":
            # 作业批改需要视觉模型
            return "nvidia/llama-3.2-90b-vision-instruct"

        elif task_type == "feedback":
            # 反馈生成使用文本模型
            if complexity == "high":
                return "nvidia/llama-3.1-70b-instruct"
            else:
                return "nvidia/llama-3.1-8b-instruct"

        elif task_type == "analysis":
            # 深度分析使用数学专用模型
            return "nvidia/llama-3.1-70b-instruct"

        # 默认返回中等模型
        return settings.get("models.primary", "nvidia/llama-3.1-8b-instruct")

    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """获取模型信息"""
        return self.available_models.get(model_name)