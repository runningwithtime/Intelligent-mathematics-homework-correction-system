# ===============================
# utils/logger.py - 日志配置
# ===============================
import logging
import logging.handlers
from pathlib import Path

from config.settings import settings


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
