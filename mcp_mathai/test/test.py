#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统组件检查脚本 - 独立运行，检查各组件状态
"""

import sys
import asyncio
from pathlib import Path

def check_imports():
    """检查关键模块导入"""
    print("=== 检查模块导入 ===")

    modules_to_check = [
        'config.settings',
        'utils.logger',
        'mcp_client.client',
        'core.grading_engine',
        'core.model_selector',
        'data.database',
        'utils.image_processor'
    ]

    for module in modules_to_check:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError as e:
            print(f"❌ {module}: {e}")
        except Exception as e:
            print(f"⚠️ {module}: {e}")

def check_config():
    """检查配置文件"""
    print("\n=== 检查配置 ===")

    try:
        from config.settings import settings
        print(f"✅ 配置加载成功")

        # 检查关键配置项
        key_configs = ['mcp', 'database', 'models']
        for key in key_configs:
            if hasattr(settings, key):
                print(f"✅ 配置项 {key} 存在")
            else:
                print(f"❌ 配置项 {key} 缺失")

    except Exception as e:
        print(f"❌ 配置加载失败: {e}")

def check_database():
    """检查数据库"""
    print("\n=== 检查数据库 ===")

    try:
        from data.database import db_manager

        # 检查数据库文件
        if hasattr(db_manager, 'db_path'):
            db_path = Path(db_manager.db_path)
            if db_path.exists():
                print(f"✅ 数据库文件存在: {db_path}")
            else:
                print(f"❌ 数据库文件不存在: {db_path}")

        # 尝试连接
        # db_manager.test_connection()  # 如果有这个方法
        print(f"✅ 数据库模块加载成功")

    except Exception as e:
        print(f"❌ 数据库检查失败: {e}")

async def check_mcp_client():
    """检查MCP客户端"""
    print("\n=== 检查MCP客户端 ===")

    try:
        from mcp_client.client import MCPClient

        client = MCPClient()
        print(f"✅ MCP客户端创建成功")

        # 尝试连接
        try:
            await client.connect()
            print(f"✅ MCP连接成功")

            # 如果有ping方法
            if hasattr(client, 'ping'):
                await client.ping()
                print(f"✅ MCP通信测试成功")

        except Exception as conn_e:
            print(f"❌ MCP连接失败: {conn_e}")

    except Exception as e:
        print(f"❌ MCP客户端检查失败: {e}")

def check_grading_engine():
    """检查批改引擎"""
    print("\n=== 检查批改引擎 ===")

    try:
        from core.grading_engine import GradingEngine
        from core.model_selector import ModelSelector

        model_selector = ModelSelector()
        print(f"✅ 模型选择器创建成功")

        # 注意：这里不传入mcp_client，只测试创建
        # engine = GradingEngine(None, model_selector)
        print(f"✅ 批改引擎模块加载成功")

    except Exception as e:
        print(f"❌ 批改引擎检查失败: {e}")

def check_image_processor():
    """检查图像处理器"""
    print("\n=== 检查图像处理器 ===")

    try:
        from utils.image_processor import ImageProcessor

        # 创建测试图像数据
        test_image_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100

        # 测试验证功能
        result = ImageProcessor.validate_image(test_image_data)
        print(f"✅ 图像处理器功能测试: {result}")

    except Exception as e:
        print(f"❌ 图像处理器检查失败: {e}")

def check_file_permissions():
    """检查文件权限"""
    print("\n=== 检查文件权限 ===")

    current_dir = Path.cwd()
    print(f"当前目录: {current_dir}")

    # 检查关键目录权限
    dirs_to_check = [
        'config',
        'data',
        'core',
        'utils',
        'mcp_client'
    ]

    for dir_name in dirs_to_check:
        dir_path = current_dir / dir_name
        if dir_path.exists():
            if dir_path.is_dir():
                print(f"✅ 目录 {dir_name} 存在且可访问")
            else:
                print(f"❌ {dir_name} 存在但不是目录")
        else:
            print(f"❌ 目录 {dir_name} 不存在")

def check_environment():
    """检查运行环境"""
    print("\n=== 检查运行环境 ===")

    print(f"Python版本: {sys.version}")
    print(f"当前工作目录: {Path.cwd()}")

    # 检查关键环境变量
    import os
    env_vars = ['PATH', 'PYTHONPATH']
    for var in env_vars:
        value = os.getenv(var, '未设置')
        print(f"{var}: {value[:100]}..." if len(value) > 100 else f"{var}: {value}")

async def main():
    """主检查函数"""
    print("数学批改系统 - 组件状态检查")
    print("=" * 50)

    check_environment()
    check_file_permissions()
    check_imports()
    check_config()
    check_database()
    await check_mcp_client()
    check_grading_engine()
    check_image_processor()

    print("\n" + "=" * 50)
    print("检查完成！请查看上述结果，重点关注❌标记的问题。")

if __name__ == "__main__":
    asyncio.run(main())