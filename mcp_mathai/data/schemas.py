# ===============================
# data/schemas.py - 数据验证模式
# ===============================
from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
import re

class GradeLevel(str, Enum):
    """年级枚举"""
    GRADE_7 = "初一"
    GRADE_8 = "初二"
    GRADE_9 = "初三"
    GRADE_10 = "高一"
    GRADE_11 = "高二"
    GRADE_12 = "高三"

class DifficultyLevel(str, Enum):
    """难度等级枚举"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class ErrorType(str, Enum):
    """错误类型枚举"""
    NO_ANSWER = "未作答"
    CALCULATION_ERROR = "计算错误"
    METHOD_ERROR = "解法错误"
    LOGIC_ERROR = "逻辑错误"
    UNDERSTANDING_ERROR = "理解错误"
    INCOMPLETE_ANSWER = "答案不完整"
    FORMAT_ERROR = "表达方式错误"

class StudentSchema(BaseModel):
    """学生数据模式"""
    name: str = Field(..., min_length=1, max_length=100, description="学生姓名")
    student_id: str = Field(..., min_length=1, max_length=50, description="学号")
    grade: GradeLevel = Field(..., description="年级")

    @validator('name')
    def validate_name(cls, v):
        """验证姓名格式"""
        if not v or not v.strip():
            raise ValueError('姓名不能为空')

        # 移除多余空格
        v = re.sub(r'\s+', ' ', v.strip())

        # 检查是否包含特殊字符
        if not re.match(r'^[\u4e00-\u9fa5a-zA-Z\s]+$', v):
            raise ValueError('姓名只能包含中文、英文字母和空格')

        return v

    @validator('student_id')
    def validate_student_id(cls, v):
        """验证学号格式"""
        if not v or not v.strip():
            raise ValueError('学号不能为空')

        v = v.strip()

        # 学号格式检查（可以包含字母数字和下划线）
        if not re.match(r'^[A-Za-z0-9_-]+$', v):
            raise ValueError('学号格式不正确，只能包含字母、数字、下划线和短横线')

        return v

class HomeworkSchema(BaseModel):
    """作业数据模式"""
    student_id: str = Field(..., description="学生ID")
    title: str = Field(..., min_length=1, max_length=200, description="作业标题")
    grade_level: GradeLevel = Field(..., description="年级水平")
    subject: str = Field(default="数学", max_length=50, description="学科")
    image_path: str = Field(..., description="图像文件路径")

    @validator('title')
    def validate_title(cls, v):
        """验证作业标题"""
        if not v or not v.strip():
            raise ValueError('作业标题不能为空')

        return v.strip()

    @validator('image_path')
    def validate_image_path(cls, v):
        """验证图像路径"""
        if not v:
            raise ValueError('图像路径不能为空')

        # 检查文件扩展名
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        if not any(v.lower().endswith(ext) for ext in allowed_extensions):
            raise ValueError(f'不支持的图像格式，支持的格式: {", ".join(allowed_extensions)}')

        return v

class QuestionSchema(BaseModel):
    """题目数据模式"""
    question_number: int = Field(..., ge=1, description="题目编号")
    question_text: str = Field(..., min_length=1, description="题目内容")
    student_answer: Optional[str] = Field(default="", description="学生答案")
    correct_answer: Optional[str] = Field(default="", description="正确答案")
    score: float = Field(default=0, ge=0, le=100, description="得分")
    max_score: float = Field(default=10, gt=0, le=100, description="满分")
    is_correct: bool = Field(default=False, description="是否正确")
    feedback: Optional[str] = Field(default="", description="反馈")
    topic: Optional[str] = Field(default="综合", max_length=100, description="知识点")
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.MEDIUM, description="难度等级")
    error_type: Optional[ErrorType] = Field(default=None, description="错误类型")

    @validator('score', 'max_score')
    def validate_scores(cls, v):
        """验证分数"""
        if v < 0:
            raise ValueError('分数不能为负数')
        return round(v, 2)

    @root_validator
    def validate_score_relationship(cls, values):
        """验证分数关系"""
        score = values.get('score', 0)
        max_score = values.get('max_score', 10)

        if score > max_score:
            raise ValueError('得分不能超过满分')

        return values

    @validator('question_text', 'student_answer', 'correct_answer')
    def clean_text_fields(cls, v):
        """清理文本字段"""
        if v is None:
            return ""
        return v.strip()

class GradingRequestSchema(BaseModel):
    """批改请求数据模式"""
    homework_id: str = Field(..., description="作业ID")
    force_regrade: bool = Field(default=False, description="是否强制重新批改")
    model_preference: Optional[str] = Field(default=None, description="指定使用的模型")

    @validator('homework_id')
    def validate_homework_id(cls, v):
        """验证作业ID"""
        if not v or not v.strip():
            raise ValueError('作业ID不能为空')
        return v.strip()

class GradingResultSchema(BaseModel):
    """批改结果数据模式"""
    homework_id: str = Field(..., description="作业ID")
    success: bool = Field(..., description="是否成功")
    model_used: Optional[str] = Field(default=None, description="使用的模型")
    processing_time: Optional[float] = Field(default=None, ge=0, description="处理时间（秒）")
    questions: List[QuestionSchema] = Field(default_factory=list, description="题目列表")
    statistics: Optional[Dict[str, Any]] = Field(default_factory=dict, description="统计信息")
    recommendations: List[Dict[str, Any]] = Field(default_factory=list, description="学习建议")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

class AnalysisRequestSchema(BaseModel):
    """图像分析请求数据模式"""
    image_data: str = Field(..., description="Base64编码的图像数据")
    grade_level: GradeLevel = Field(..., description="年级水平")
    analysis_type: str = Field(default="full", description="分析类型")

    @validator('image_data')
    def validate_image_data(cls, v):
        """验证图像数据"""
        if not v:
            raise ValueError('图像数据不能为空')

        # 检查是否为有效的Base64编码
        import base64
        try:
            base64.b64decode(v)
        except Exception:
            raise ValueError('无效的Base64编码数据')

        return v

    @validator('analysis_type')
    def validate_analysis_type(cls, v):
        """验证分析类型"""
        allowed_types = ['quick', 'full', 'detailed']
        if v not in allowed_types:
            raise ValueError(f'无效的分析类型，支持的类型: {", ".join(allowed_types)}')
        return v

class FeedbackRequestSchema(BaseModel):
    """反馈生成请求数据模式"""
    question_text: str = Field(..., min_length=1, description="题目内容")
    student_answer: str = Field(..., description="学生答案")
    correct_answer: str = Field(..., description="正确答案")
    feedback_type: str = Field(default="detailed", description="反馈类型")
    grade_level: Optional[GradeLevel] = Field(default=None, description="年级水平")

    @validator('feedback_type')
    def validate_feedback_type(cls, v):
        """验证反馈类型"""
        allowed_types = ['brief', 'detailed', 'encouraging']
        if v not in allowed_types:
            raise ValueError(f'无效的反馈类型，支持的类型: {", ".join(allowed_types)}')
        return v

class StatisticsSchema(BaseModel):
    """统计数据模式"""
    total_questions: int = Field(ge=0, description="总题目数")
    correct_questions: int = Field(ge=0, description="正确题目数")
    wrong_questions: int = Field(ge=0, description="错误题目数")
    accuracy_rate: float = Field(ge=0, le=100, description="正确率(%)")
    total_score: float = Field(ge=0, description="总得分")
    max_total_score: float = Field(gt=0, description="总满分")
    score_rate: float = Field(ge=0, le=100, description="得分率(%)")
    topic_breakdown: Dict[str, Dict[str, Union[int, float]]] = Field(
        default_factory=dict, description="知识点分解"
    )
    error_type_distribution: Dict[str, int] = Field(
        default_factory=dict, description="错误类型分布"
    )
    difficulty_distribution: Dict[str, Dict[str, int]] = Field(
        default_factory=dict, description="难度分布"
    )

    @root_validator
    def validate_statistics(cls, values):
        """验证统计数据的一致性"""
        total = values.get('total_questions', 0)
        correct = values.get('correct_questions', 0)
        wrong = values.get('wrong_questions', 0)

        if correct + wrong != total:
            raise ValueError('正确题目数 + 错误题目数 应该等于总题目数')

        accuracy = values.get('accuracy_rate', 0)
        expected_accuracy = (correct / total * 100) if total > 0 else 0

        if abs(accuracy - expected_accuracy) > 0.1:  # 允许0.1%的误差
            raise ValueError('正确率计算不正确')

        return values

class RecommendationSchema(BaseModel):
    """学习建议数据模式"""
    type: str = Field(..., description="建议类型")
    priority: str = Field(..., description="优先级")
    title: str = Field(..., min_length=1, max_length=200, description="标题")
    content: str = Field(..., min_length=1, description="内容")
    actions: List[str] = Field(default_factory=list, description="建议行动")

    @validator('type')
    def validate_type(cls, v):
        """验证建议类型"""
        allowed_types = ['praise', 'improvement', 'attention', 'focus', 'method']
        if v not in allowed_types:
            raise ValueError(f'无效的建议类型，支持的类型: {", ".join(allowed_types)}')
        return v

    @validator('priority')
    def validate_priority(cls, v):
        """验证优先级"""
        allowed_priorities = ['low', 'medium', 'high']
        if v not in allowed_priorities:
            raise ValueError(f'无效的优先级，支持的优先级: {", ".join(allowed_priorities)}')
        return v

class ImageUploadSchema(BaseModel):
    """图像上传数据模式"""
    filename: str = Field(..., description="文件名")
    file_size: int = Field(..., gt=0, description="文件大小（字节）")
    content_type: str = Field(..., description="MIME类型")

    @validator('filename')
    def validate_filename(cls, v):
        """验证文件名"""
        if not v:
            raise ValueError('文件名不能为空')

        # 检查文件扩展名
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        if not any(v.lower().endswith(ext) for ext in allowed_extensions):
            raise ValueError(f'不支持的文件类型，支持的类型: {", ".join(allowed_extensions)}')

        return v

    @validator('file_size')
    def validate_file_size(cls, v):
        """验证文件大小"""
        max_size = 16 * 1024 * 1024  # 16MB
        if v > max_size:
            raise ValueError(f'文件大小超过限制（{max_size} 字节）')

        return v

    @validator('content_type')
    def validate_content_type(cls, v):
        """验证MIME类型"""
        allowed_types = ['image/jpeg', 'image/png', 'image/bmp']
        if v not in allowed_types:
            raise ValueError(f'不支持的MIME类型，支持的类型: {", ".join(allowed_types)}')

        return v

class PaginationSchema(BaseModel):
    """分页数据模式"""
    page: int = Field(default=1, ge=1, description="页码")
    per_page: int = Field(default=20, ge=1, le=100, description="每页数量")
    total: int = Field(ge=0, description="总数量")
    pages: int = Field(ge=0, description="总页数")

    @root_validator
    def validate_pagination(cls, values):
        """验证分页数据"""
        page = values.get('page', 1)
        per_page = values.get('per_page', 20)
        total = values.get('total', 0)

        # 计算总页数
        pages = (total + per_page - 1) // per_page if total > 0 else 0
        values['pages'] = pages

        # 验证当前页码
        if pages > 0 and page > pages:
            raise ValueError(f'页码超出范围，最大页码为 {pages}')

        return values

class ConfigSchema(BaseModel):
    """配置数据模式"""
    server_host: str = Field(default="localhost", description="服务器主机")
    server_port: int = Field(default=8765, ge=1024, le=65535, description="服务器端口")
    database_url: str = Field(..., description="数据库连接URL")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    max_file_size: int = Field(default=16*1024*1024, gt=0, description="最大文件大小")
    allowed_formats: List[str] = Field(
        default_factory=lambda: ["jpg", "jpeg", "png", "bmp"],
        description="允许的文件格式"
    )

    @validator('database_url')
    def validate_database_url(cls, v):
        """验证数据库URL"""
        if not v:
            raise ValueError('数据库URL不能为空')

        # 简单的URL格式检查
        if not (v.startswith('sqlite:') or v.startswith('mysql:') or v.startswith('postgresql:')):
            raise ValueError('不支持的数据库类型')

        return v

class ValidationMixin:
    """验证混合类，提供通用验证方法"""

    @staticmethod
    def validate_id(value: str, field_name: str = "ID") -> str:
        """验证ID格式"""
        if not value or not value.strip():
            raise ValueError(f'{field_name}不能为空')

        value = value.strip()

        # 检查ID格式（UUID或自定义格式）
        uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
        custom_pattern = r'^[A-Za-z0-9_-]{3,50}$'

        if not (re.match(uuid_pattern, value, re.IGNORECASE) or re.match(custom_pattern, value)):
            raise ValueError(f'无效的{field_name}格式')

        return value

    @staticmethod
    def validate_text_length(value: str, min_length: int = 0, max_length: int = 1000, field_name: str = "文本") -> str:
        """验证文本长度"""
        if value is None:
            value = ""

        value = value.strip()

        if len(value) < min_length:
            raise ValueError(f'{field_name}长度不能少于{min_length}个字符')

        if len(value) > max_length:
            raise ValueError(f'{field_name}长度不能超过{max_length}个字符')

        return value

    @staticmethod
    def validate_numeric_range(value: Union[int, float], min_val: Union[int, float] = None,
                               max_val: Union[int, float] = None, field_name: str = "数值") -> Union[int, float]:
        """验证数值范围"""
        if min_val is not None and value < min_val:
            raise ValueError(f'{field_name}不能小于{min_val}')

        if max_val is not None and value > max_val:
            raise ValueError(f'{field_name}不能大于{max_val}')

        return value

# 导出所有模式类
__all__ = [
    'GradeLevel', 'DifficultyLevel', 'ErrorType',
    'StudentSchema', 'HomeworkSchema', 'QuestionSchema',
    'GradingRequestSchema', 'GradingResultSchema',
    'AnalysisRequestSchema', 'FeedbackRequestSchema',
    'StatisticsSchema', 'RecommendationSchema',
    'ImageUploadSchema', 'PaginationSchema', 'ConfigSchema',
    'ValidationMixin'
]