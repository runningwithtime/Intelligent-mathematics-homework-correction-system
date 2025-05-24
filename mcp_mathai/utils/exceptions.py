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