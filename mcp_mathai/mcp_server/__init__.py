# ===============================
# mcp_server/__init__.py
# ===============================
"""MCP服务器模块"""

from .server import MathGradingMCPServer
from .tools import math_grading_tools, MathGradingTools

__all__ = [
    "MathGradingMCPServer",
    "math_grading_tools",
    "MathGradingTools"
]

# ===============================
# mcp_client/__init__.py
# ===============================
"""MCP客户端模块"""

from mcp_client.client import MCPClient, create_mcp_client, get_global_client
from mcp_client.models import NVIDIAModelClient, MathGradingAI

__all__ = [
    "MCPClient",
    "create_mcp_client",
    "get_global_client",
    "NVIDIAModelClient",
    "MathGradingAI"
]

# ===============================
# config/__init__.py
# ===============================
"""配置模块"""

from config.settings import settings, Settings

__all__ = ["settings", "Settings"]

# ===============================
# data/__init__.py
# ===============================
"""数据模块"""

from data.models import Student, Homework, Question, GradingSession, Base
from data.database import DatabaseManager, db_manager

__all__ = [
    "Student", "Homework", "Question", "GradingSession", "Base",
    "DatabaseManager", "db_manager"
]

# ===============================
# core/__init__.py
# ===============================
"""核心模块"""

from core.grading_engine import GradingEngine
from core.model_selector import ModelSelector, ModelType, ModelInfo

__all__ = [
    "GradingEngine",
    "ModelSelector",
    "ModelType",
    "ModelInfo"
]

# ===============================
# utils/__init__.py
# ===============================
"""工具模块"""

from utils.exceptions import (
    MathGradingException,
    ModelSelectionError,
    ImageProcessingError,
    APIConnectionError,
    DatabaseError
)
from utils.logger import setup_logger

__all__ = [
    "MathGradingException",
    "ModelSelectionError",
    "ImageProcessingError",
    "APIConnectionError",
    "DatabaseError",
    "setup_logger"
]