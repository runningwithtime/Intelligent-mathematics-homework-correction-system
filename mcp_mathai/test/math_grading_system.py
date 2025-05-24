# ===============================
# 项目结构
# ===============================
"""
math_grading_system/
├── config/
│   ├── __init__.py
│   ├── settings.py          # 配置管理
│   └── database.py          # 数据库配置
├── mcp_server/
│   ├── __init__.py
│   ├── server.py           # MCP服务器（提供工具）
│   └── tools.py            # MCP工具定义
├── mcp_client/
│   ├── __init__.py
│   ├── client.py           # MCP客户端（使用AI模型）
│   └── models.py           # AI模型接口
├── core/
│   ├── __init__.py
│   ├── grading_engine.py   # 批改引擎
│   ├── model_selector.py   # 模型选择器
│   └── result_processor.py # 结果处理器
├── data/
│   ├── __init__.py
│   ├── models.py           # 数据模型
│   ├── database.py         # 数据库操作
│   └── schemas.py          # 数据验证
├── api/
│   ├── __init__.py
│   ├── routes.py           # API路由
│   └── handlers.py         # 请求处理器
├── frontend/
│   ├── __init__.py
│   ├── gui.py             # Tkinter GUI
│   └── web.py             # Web界面（可选）
├── utils/
│   ├── __init__.py
│   ├── image_processor.py  # 图像处理
│   ├── logger.py          # 日志工具
│   └── exceptions.py      # 自定义异常
├── tests/
│   └── ...               # 测试文件
├── requirements.txt
├── setup.py
└── main.py               # 主启动文件
"""

# ===============================
# config/settings.py - 配置管理
# ===============================
import os
from pathlib import Path
from typing import Dict, Any, Optional
import json

class Settings:
    """系统配置管理"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config_file = self.project_root / "config.json"
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "server": {
                "host": "localhost",
                "port": 8765,
                "max_connections": 100
            },
            "database": {
                "url": "sqlite:///math_grading.db",
                "echo": False
            },
            "models": {
                "primary": "nvidia/llama-3.2-90b-vision-instruct",
                "fallback": "nvidia/llama-3.1-8b-instruct",
                "api_base": "https://integrate.api.nvidia.com/v1"
            },
            "logging": {
                "level": "INFO",
                "file": "logs/app.log"
            },
            "image": {
                "max_size": 10 * 1024 * 1024,  # 10MB
                "allowed_formats": ["jpg", "jpeg", "png", "bmp"],
                "resize_threshold": 1920
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                # 合并配置
                default_config.update(user_config)
            except Exception as e:
                print(f"配置文件加载失败，使用默认配置: {e}")
        
        return default_config
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            value = value.get(k, {})
        return value if value != {} else default
    
    def get_api_key(self) -> str:
        """获取API密钥"""
        # 优先从环境变量获取
        api_key = os.getenv('NVIDIA_API_KEY')
        if api_key:
            return api_key
        
        # 从文件获取
        possible_files = [
            self.project_root / "nvidia_api_key.txt",
            self.project_root / "api_key.txt",
            Path.home() / "nvidia_api_key.txt"
        ]
        
        for file_path in possible_files:
            if file_path.exists():
                try:
                    return file_path.read_text().strip()
                except Exception:
                    continue
        
        raise FileNotFoundError("未找到NVIDIA API密钥")

# 全局设置实例
settings = Settings()

# ===============================
# data/models.py - 数据模型
# ===============================
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid

Base = declarative_base()

class Student(Base):
    """学生模型"""
    __tablename__ = "students"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    student_id = Column(String(50), unique=True, nullable=False)
    grade = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    homeworks = relationship("Homework", back_populates="student")

class Homework(Base):
    """作业模型"""
    __tablename__ = "homeworks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String, ForeignKey("students.id"), nullable=False)
    title = Column(String(200), nullable=False)
    subject = Column(String(50), default="数学")
    grade_level = Column(String(20), nullable=False)
    image_path = Column(String(500), nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    graded_at = Column(DateTime, nullable=True)
    total_score = Column(Float, default=0)
    max_score = Column(Float, default=0)
    
    # 关系
    student = relationship("Student", back_populates="homeworks")
    questions = relationship("Question", back_populates="homework")

class Question(Base):
    """题目模型"""
    __tablename__ = "questions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    homework_id = Column(String, ForeignKey("homeworks.id"), nullable=False)
    question_number = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    student_answer = Column(Text, nullable=True)
    correct_answer = Column(Text, nullable=True)
    score = Column(Float, default=0)
    max_score = Column(Float, default=10)
    is_correct = Column(Boolean, default=False)
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    homework = relationship("Homework", back_populates="questions")

class GradingSession(Base):
    """批改会话模型"""
    __tablename__ = "grading_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    homework_id = Column(String, ForeignKey("homeworks.id"), nullable=False)
    model_used = Column(String(100), nullable=False)
    processing_time = Column(Float, nullable=True)  # 处理时间（秒）
    status = Column(String(20), default="processing")  # processing, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

# ===============================
# data/database.py - 数据库操作
# ===============================
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, echo=settings.get("database.echo", False))
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # 创建表
        Base.metadata.create_all(bind=self.engine)
        logger.info("数据库初始化完成")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """获取数据库会话"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            session.close()
    
    def create_student(self, name: str, student_id: str, grade: str) -> Student:
        """创建学生"""
        with self.get_session() as session:
            student = Student(name=name, student_id=student_id, grade=grade)
            session.add(student)
            session.flush()
            return student
    
    def create_homework(self, student_id: str, title: str, grade_level: str, image_path: str) -> Homework:
        """创建作业"""
        with self.get_session() as session:
            homework = Homework(
                student_id=student_id,
                title=title,
                grade_level=grade_level,
                image_path=image_path
            )
            session.add(homework)
            session.flush()
            return homework
    
    def save_grading_results(self, homework_id: str, results: list, session_data: dict):
        """保存批改结果"""
        with self.get_session() as session:
            # 更新作业信息
            homework = session.query(Homework).filter(Homework.id == homework_id).first()
            if homework:
                homework.graded_at = datetime.utcnow()
                homework.total_score = session_data.get('total_score', 0)
                homework.max_score = session_data.get('max_score', 0)
            
            # 保存题目结果
            for i, result in enumerate(results):
                question = Question(
                    homework_id=homework_id,
                    question_number=i + 1,
                    question_text=result.get('question_text', ''),
                    student_answer=result.get('student_answer', ''),
                    correct_answer=result.get('correct_answer', ''),
                    score=result.get('score', 0),
                    max_score=result.get('max_score', 10),
                    is_correct=result.get('is_correct', False),
                    feedback=result.get('feedback', '')
                )
                session.add(question)

# 全局数据库实例
db_manager = DatabaseManager(settings.get("database.url"))

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

# ===============================
# core/grading_engine.py - 批改引擎
# ===============================
import asyncio
from typing import Dict, List, Any, Tuple
import logging
import time

class GradingEngine:
    """批改引擎 - 系统核心"""
    
    def __init__(self, mcp_client, model_selector: ModelSelector):
        self.mcp_client = mcp_client
        self.model_selector = model_selector
        self.logger = logging.getLogger(__name__)
    
    async def grade_homework(self, homework_id: str, image_path: str, grade_level: str) -> Dict[str, Any]:
        """批改作业 - 主要接口"""
        start_time = time.time()
        
        try:
            self.logger.info(f"开始批改作业: {homework_id}")
            
            # 1. 选择合适的模型
            model_name = self.model_selector.select_model("grading", image_included=True)
            self.logger.info(f"选择模型: {model_name}")
            
            # 2. 图像预处理
            processed_image = await self._preprocess_image(image_path)
            
            # 3. 调用AI模型分析
            analysis_result = await self.mcp_client.analyze_homework(
                processed_image, grade_level, model_name
            )
            
            # 4. 后处理结果
            processed_results = await self._process_results(analysis_result)
            
            # 5. 生成详细反馈
            enhanced_results = await self._generate_enhanced_feedback(processed_results)
            
            # 6. 计算统计信息
            stats = self._calculate_statistics(enhanced_results)
            
            processing_time = time.time() - start_time
            
            # 7. 保存到数据库
            await self._save_results(homework_id, enhanced_results, stats, processing_time)
            
            return {
                "homework_id": homework_id,
                "model_used": model_name,
                "processing_time": processing_time,
                "statistics": stats,
                "results": enhanced_results,
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"批改失败: {e}")
            return {
                "homework_id": homework_id,
                "error": str(e),
                "success": False
            }
    
    async def _preprocess_image(self, image_path: str) -> str:
        """图像预处理"""
        # 这里可以调用您原有的图像处理代码
        from utils.image_processor import ImageProcessor
        
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        return ImageProcessor.preprocess_image(image_data)
    
    async def _process_results(self, raw_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """处理原始结果"""
        questions = raw_results.get('questions', [])
        processed = []
        
        for i, question in enumerate(questions):
            processed_question = {
                "question_id": f"q_{i+1}",
                "question_text": question.get('question_text', ''),
                "student_answer": question.get('student_answer', ''),
                "correct_answer": question.get('correct_answer', ''),
                "score": float(question.get('score', 0)),
                "max_score": float(question.get('max_score', 10)),
                "is_correct": question.get('is_correct', False),
                "initial_feedback": question.get('feedback', ''),
                "difficulty": question.get('difficulty', 'medium'),
                "topic": question.get('topic', '未分类')
            }
            processed.append(processed_question)
        
        return processed
    
    async def _generate_enhanced_feedback(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成增强反馈"""
        enhanced_results = []
        
        for result in results:
            if not result['is_correct']:
                # 为错误答案生成详细反馈
                enhanced_feedback = await self.mcp_client.generate_detailed_feedback(
                    result['question_text'],
                    result['student_answer'],
                    result['correct_answer']
                )
                result['enhanced_feedback'] = enhanced_feedback
            
            enhanced_results.append(result)
        
        return enhanced_results
    
    def _calculate_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算统计信息"""
        total_questions = len(results)
        correct_count = sum(1 for r in results if r['is_correct'])
        total_score = sum(r['score'] for r in results)
        max_total_score = sum(r['max_score'] for r in results)
        
        # 按主题分类统计
        topic_stats = {}
        for result in results:
            topic = result.get('topic', '未分类')
            if topic not in topic_stats:
                topic_stats[topic] = {'correct': 0, 'total': 0, 'score': 0, 'max_score': 0}
            
            topic_stats[topic]['total'] += 1
            topic_stats[topic]['score'] += result['score']
            topic_stats[topic]['max_score'] += result['max_score']
            if result['is_correct']:
                topic_stats[topic]['correct'] += 1
        
        return {
            "total_questions": total_questions,
            "correct_count": correct_count,
            "accuracy_rate": (correct_count / total_questions * 100) if total_questions > 0 else 0,
            "total_score": total_score,
            "max_total_score": max_total_score,
            "score_percentage": (total_score / max_total_score * 100) if max_total_score > 0 else 0,
            "topic_breakdown": topic_stats
        }
    
    async def _save_results(self, homework_id: str, results: List[Dict], stats: Dict, processing_time: float):
        """保存结果到数据库"""
        session_data = {
            "total_score": stats["total_score"],
            "max_score": stats["max_total_score"],
            "processing_time": processing_time
        }
        
        db_manager.save_grading_results(homework_id, results, session_data)

# ===============================
# utils/exceptions.py - 自定义异常
# ===============================
class MathGradingException(Exception):
    """批改系统基础异常"""
    pass

class ModelSelectionError(MathGradingException):
    """模型选择错误"""
    pass

class ImageProcessingError(MathGradingException):
    """图像处理错误"""
    pass

class APIConnectionError(MathGradingException):
    """API连接错误"""
    pass

class DatabaseError(MathGradingException):
    """数据库错误"""
    pass

# ===============================
# utils/logger.py - 日志配置
# ===============================
import logging
import logging.handlers
from pathlib import Path

def setup_logger(name: str = None) -> logging.Logger:
    """设置日志器"""
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, settings.get("logging.level", "INFO")))
    
    # 创建格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器
    log_file = Path(settings.get("logging.file", "logs/app.log"))
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

# ===============================
# main.py - 主启动文件
# ===============================
import asyncio
import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from utils.logger import setup_logger
from mcp_server.server import MathGradingMCPServer
from mcp_client.client import MCPClient
from frontend.gui import MathGradingGUI
from api.routes import create_app

logger = setup_logger("main")

async def start_server():
    """启动MCP服务器"""
    try:
        api_key = settings.get_api_key()
        server = MathGradingMCPServer(
            api_key,
            settings.get("server.host"),
            settings.get("server.port")
        )
        await server.start_server()
    except Exception as e:
        logger.error(f"启动服务器失败: {e}")
        return False
    return True

def start_gui():
    """启动GUI客户端"""
    try:
        app = MathGradingGUI()
        app.run()
    except Exception as e:
        logger.error(f"启动GUI失败: {e}")

def start_web():
    """启动Web服务"""
    try:
        app = create_app()
        app.run(
            host=settings.get("server.host"),
            port=settings.get("server.port") + 1,
            debug=True
        )
    except Exception as e:
        logger.error(f"启动Web服务失败: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数学作业批改系统")
    parser.add_argument("--mode", choices=["server", "gui", "web", "all"], 
                       default="all", help="启动模式")
    
    args = parser.parse_args()
    
    logger.info(f"启动模式: {args.mode}")
    
    if args.mode == "server":
        asyncio.run(start_server())
    elif args.mode == "gui":
        start_gui()
    elif args.mode == "web":
        start_web()
    elif args.mode == "all":
        # 启动所有服务
        logger.info("启动完整系统...")
        # 这里可以使用多进程或线程来同时启动多个服务
        start_gui()  # 默认启动GUI

if __name__ == "__main__":
    main()

# ===============================
# requirements.txt
# ===============================
"""
# 核心依赖
asyncio
websockets>=11.0
aiohttp>=3.8.0
sqlalchemy>=1.4.0
pydantic>=1.10.0

# AI模型相关
openai>=1.0.0
requests>=2.28.0

# 图像处理
Pillow>=9.0.0
opencv-python>=4.6.0
numpy>=1.21.0

# GUI
tkinter

# Web框架（可选）
flask>=2.2.0
fastapi>=0.95.0
uvicorn>=0.20.0

# 工具库
python-dotenv>=0.19.0
pathlib
uuid
base64
json
logging
"""

print("✅ 完整系统架构已生成！")
print("📁 包含以下主要模块：")
print("  - 配置管理系统")
print("  - 数据库设计和ORM")
print("  - 智能模型选择器")
print("  - 核心批改引擎")
print("  - 工具类和异常处理")
print("  - 完整的项目结构")
print("🚀 请按照项目结构创建对应文件并复制相应代码")