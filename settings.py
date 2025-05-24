# config/settings.py - 修复版本
import os
from pathlib import Path

class Settings:
    def __init__(self):
        self.BASE_DIR = Path(__file__).parent.parent
        self.DATA_DIR = self.BASE_DIR / "data"
        self.DATA_DIR.mkdir(exist_ok=True)

        # 构建完整的配置字典
        self._config = {
            "mcp": {
                "timeout": 30,
                "retry_attempts": 3,
                "retry_delay": 2
            },
            "database": {
                "type": "sqlite",
                "path": str(self.DATA_DIR / "math_grading.db"),
                "url": f"sqlite:///{self.DATA_DIR / 'math_grading.db'}",
                "echo": False
            },
            "models": {
                "default_provider": "nvidia",
                "nvidia": {
                    "api_key": os.getenv("NVIDIA_API_KEY", "nvapi-xxx"),
                    "base_url": "https://integrate.api.nvidia.com/v1",
                    "model": "microsoft/phi-3.5-vision-instruct",
                    "max_tokens": 4000,
                    "temperature": 0.1
                }
            },
            "server": {
                "host": "localhost",
                "port": 8765
            }
        }

    def get(self, key: str, default=None):
        """获取配置值，支持点号分隔的嵌套键"""
        keys = key.split('.')
        value = self._config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def get_api_key(self) -> str:
        """获取API密钥"""
        # 首先尝试从环境变量获取
        api_key = os.getenv("NVIDIA_API_KEY")
        if api_key:
            return api_key

        # 然后尝试从api_key.txt文件获取
        try:
            api_key_file = self.BASE_DIR / "api_key.txt"
            if api_key_file.exists():
                return api_key_file.read_text().strip()
        except Exception:
            pass

        # 返回配置中的默认值
        return self.get("models.nvidia.api_key", "nvapi-xxx")

    @property
    def mcp(self):
        return self._config["mcp"]

    @property
    def database(self):
        return self._config["database"]

    @property
    def models(self):
        return self._config["models"]

    @property
    def server(self):
        return self._config["server"]

settings = Settings()