# ===============================
# check_system.py - 系统配置检查脚本
# ===============================

import os
import sys
from pathlib import Path
import asyncio
import aiohttp
import logging

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger("system_check")

class SystemChecker:
    """系统配置检查器"""

    def __init__(self):
        self.checks_passed = 0
        self.total_checks = 0
        self.errors = []
        self.warnings = []

    def check_item(self, name: str, condition: bool, error_msg: str = "", warning_msg: str = ""):
        """检查单个项目"""
        self.total_checks += 1

        if condition:
            print(f"✅ {name}")
            self.checks_passed += 1
        else:
            print(f"❌ {name}")
            if error_msg:
                self.errors.append(error_msg)

        if warning_msg:
            print(f"⚠️  {warning_msg}")
            self.warnings.append(warning_msg)

    def check_directory_structure(self):
        """检查目录结构"""
        print("\n📁 检查目录结构...")

        required_dirs = [
            "config",
            "core",
            "data",
            "frontend",
            "mcp_server",
            "mcp_client",
            "utils",
            "api"
        ]

        for dir_name in required_dirs:
            dir_path = Path(dir_name)
            self.check_item(
                f"目录 {dir_name}",
                dir_path.exists() and dir_path.is_dir(),
                f"缺少目录: {dir_name}"
            )

    def check_required_files(self):
        """检查必需文件"""
        print("\n📄 检查必需文件...")

        required_files = [
            "main.py",
            "config/settings.py",
            "core/grading_engine.py",
            "data/database.py",
            "frontend/gui.py",
            "mcp_server/server.py",
            "mcp_client/client.py",
            "utils/logger.py"
        ]

        for file_path in required_files:
            path = Path(file_path)
            self.check_item(
                f"文件 {file_path}",
                path.exists() and path.is_file(),
                f"缺少文件: {file_path}"
            )

    def check_api_key_configuration(self):
        """检查API密钥配置"""
        print("\n🔑 检查API密钥配置...")

        # 检查环境变量
        env_key = os.getenv("NVIDIA_API_KEY")
        has_env_key = bool(env_key and env_key != "nvapi-xxx")

        # 检查文件配置
        api_key_file = Path("api_key.txt")
        has_file_key = False
        if api_key_file.exists():
            try:
                file_key = api_key_file.read_text().strip()
                has_file_key = bool(file_key and file_key != "nvapi-xxx")
            except:
                pass

        # 检查settings配置
        settings_key = settings.get_api_key()
        has_settings_key = bool(settings_key and settings_key != "nvapi-xxx")

        self.check_item(
            "环境变量 NVIDIA_API_KEY",
            has_env_key,
            warning_msg="未设置环境变量，将使用其他配置方式" if not has_env_key else ""
        )

        self.check_item(
            "api_key.txt 文件",
            has_file_key or has_env_key,
            warning_msg="api_key.txt文件不存在或无效" if not has_file_key and not has_env_key else ""
        )

        self.check_item(
            "API密钥总体配置",
            has_env_key or has_file_key or has_settings_key,
            "未找到有效的NVIDIA API密钥配置！请设置NVIDIA_API_KEY环境变量或创建api_key.txt文件"
        )

        if has_env_key or has_file_key or has_settings_key:
            print(f"📝 当前使用的API密钥: {settings_key[:10]}...{settings_key[-4:] if len(settings_key) > 14 else ''}")

    async def check_nvidia_api_connectivity(self):
        """检查NVIDIA API连接性"""
        print("\n🌐 检查NVIDIA API连接...")

        api_key = settings.get_api_key()
        if not api_key or api_key == "nvapi-xxx":
            self.check_item(
                "NVIDIA API连接测试",
                False,
                "API密钥未配置，跳过连接测试"
            )
            return

        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            test_data = {
                "model": "microsoft/phi-3.5-vision-instruct",
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 5
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        "https://integrate.api.nvidia.com/v1/chat/completions",
                        headers=headers,
                        json=test_data,
                        timeout=30
                ) as response:

                    if response.status == 200:
                        self.check_item("NVIDIA API连接测试", True)
                        result = await response.json()
                        print(f"📡 API响应正常，模型: {result.get('model', 'unknown')}")
                    else:
                        error_text = await response.text()
                        self.check_item(
                            "NVIDIA API连接测试",
                            False,
                            f"API调用失败 {response.status}: {error_text}"
                        )

        except asyncio.TimeoutError:
            self.check_item(
                "NVIDIA API连接测试",
                False,
                "API连接超时，请检查网络连接"
            )
        except Exception as e:
            self.check_item(
                "NVIDIA API连接测试",
                False,
                f"API连接异常: {str(e)}"
            )

    def check_python_dependencies(self):
        """检查Python依赖"""
        print("\n📦 检查Python依赖...")

        required_packages = [
            "sqlalchemy",
            "aiohttp",
            "asyncio",
            "tkinter",
            "PIL",
            "pathlib"
        ]

        for package in required_packages:
            try:
                __import__(package)
                self.check_item(f"包 {package}", True)
            except ImportError:
                self.check_item(
                    f"包 {package}",
                    False,
                    f"缺少Python包: {package}，请运行 pip install {package}"
                )

    def check_database_configuration(self):
        """检查数据库配置"""
        print("\n🗄️ 检查数据库配置...")

        db_config = settings.database
        db_path = Path(db_config.get("path", ""))

        self.check_item(
            "数据库配置",
            bool(db_config),
            "数据库配置缺失"
        )

        # 检查数据库目录
        if db_path.parent.exists():
            self.check_item("数据库目录", True)
        else:
            self.check_item(
                "数据库目录",
                False,
                f"数据库目录不存在: {db_path.parent}"
            )

        # 检查数据库文件（可能还不存在）
        if db_path.exists():
            print(f"📄 数据库文件已存在: {db_path}")
        else:
            print(f"📄 数据库文件将被创建: {db_path}")

    def generate_report(self):
        """生成检查报告"""
        print("\n" + "="*50)
        print("📊 系统检查报告")
        print("="*50)

        print(f"✅ 通过检查: {self.checks_passed}/{self.total_checks}")

        if self.errors:
            print(f"\n❌ 错误 ({len(self.errors)}):")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")

        if self.warnings:
            print(f"\n⚠️ 警告 ({len(self.warnings)}):")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")

        if self.checks_passed == self.total_checks:
            print("\n🎉 系统配置检查完成，可以启动应用！")
            return True
        else:
            print(f"\n⚠️ 存在 {len(self.errors)} 个问题需要解决")
            return False

    async def run_all_checks(self):
        """运行所有检查"""
        print("🔍 开始系统配置检查...\n")

        self.check_directory_structure()
        self.check_required_files()
        self.check_python_dependencies()
        self.check_api_key_configuration()
        await self.check_nvidia_api_connectivity()
        self.check_database_configuration()

        return self.generate_report()


# ===============================
# setup_guide.py - 安装设置指南
# ===============================

def print_setup_guide():
    """打印设置指南"""
    guide = """
🚀 数学批改系统设置指南
================================

1. 📝 配置NVIDIA API密钥
   方法A: 环境变量
   export NVIDIA_API_KEY="nvapi-your-actual-key-here"
   
   方法B: 创建api_key.txt文件
   echo "nvapi-your-actual-key-here" > api_key.txt
   
   获取API密钥: https://build.nvidia.com/

2. 📦 安装Python依赖
   pip install sqlalchemy aiohttp pillow tkinter

3. 🗄️ 初始化数据库
   python -c "from data.models import db_manager; db_manager.create_tables(); db_manager.init_default_data()"

4. 🧪 运行系统检查
   python check_system.py

5. 🚀 启动应用
   python main.py

================================

📚 快速问题解决:

Q: ImportError: cannot import name 'GradingEngine'
A: 已修复，请使用最新的grading_engine.py

Q: 一直显示"简化批改模式"
A: 检查NVIDIA API密钥配置和网络连接

Q: Session绑定错误
A: 在database.py中设置expire_on_commit=False

Q: MCP连接失败
A: 确保MCP服务器代码正确实现

================================
"""
    print(guide)


# ===============================
# 快速修复脚本
# ===============================

def quick_fix():
    """快速修复常见问题"""
    print("🔧 运行快速修复...")

    # 创建必要的目录
    required_dirs = ["data", "logs", "temp"]
    for dir_name in required_dirs:
        Path(dir_name).mkdir(exist_ok=True)
        print(f"✅ 创建目录: {dir_name}")

    # 检查API密钥
    if not settings.get_api_key() or settings.get_api_key() == "nvapi-xxx":
        print("⚠️ 请配置NVIDIA API密钥:")
        print("   export NVIDIA_API_KEY='your-api-key'")
        print("   或创建 api_key.txt 文件")

    print("🔧 快速修复完成")


# ===============================
# 主程序
# ===============================

async def main():
    """主检查程序"""
    import argparse

    parser = argparse.ArgumentParser(description="数学批改系统配置检查")
    parser.add_argument("--setup", action="store_true", help="显示设置指南")
    parser.add_argument("--fix", action="store_true", help="运行快速修复")

    args = parser.parse_args()

    if args.setup:
        print_setup_guide()
        return

    if args.fix:
        quick_fix()
        return

    # 运行系统检查
    checker = SystemChecker()
    success = await checker.run_all_checks()

    if success:
        print("\n🎯 建议:")
        print("   python main.py  # 启动应用")
    else:
        print("\n🎯 建议:")
        print("   python check_system.py --setup  # 查看设置指南")
        print("   python check_system.py --fix    # 运行快速修复")

if __name__ == "__main__":
    asyncio.run(main())