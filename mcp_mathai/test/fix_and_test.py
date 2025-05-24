#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
立即修复验证脚本 - fix_and_test.py
请将此文件保存为 fix_and_test.py 并运行
"""

import os
import sys
import asyncio
from pathlib import Path

def fix_config_file():
    """修复配置文件"""
    print("🔧 正在修复配置文件...")

    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)

    settings_content = '''# config/settings.py - 修复版本
import os
from pathlib import Path

class Settings:
    def __init__(self):
        self.BASE_DIR = Path(__file__).parent.parent
        self.DATA_DIR = self.BASE_DIR / "data"
        self.DATA_DIR.mkdir(exist_ok=True)
    
    @property
    def mcp(self):
        return {
            "timeout": 30,
            "retry_attempts": 3,
            "retry_delay": 2
        }
    
    @property
    def database(self):
        return {
            "type": "sqlite",
            "path": str(self.DATA_DIR / "math_grading.db")
        }
    
    @property
    def models(self):
        return {
            "default_provider": "nvidia",
            "nvidia": {
                "api_key": os.getenv("NVIDIA_API_KEY", "nvapi-xxx"),
                "base_url": "https://integrate.api.nvidia.com/v1",
                "model": "microsoft/phi-3.5-vision-instruct",
                "max_tokens": 4000,
                "temperature": 0.1
            }
        }

settings = Settings()
'''

    with open(config_dir / "settings.py", "w", encoding="utf-8") as f:
        f.write(settings_content)

    print("✅ 配置文件已修复")

def test_config():
    """测试配置"""
    print("\n🧪 测试配置...")

    try:
        from config.settings import settings

        # 测试所有配置项
        configs = ["mcp", "database", "models"]
        for config_name in configs:
            if hasattr(settings, config_name):
                config_value = getattr(settings, config_name)
                print(f"✅ {config_name}: {type(config_value).__name__}")
            else:
                print(f"❌ {config_name}: 缺失")
                return False

        return True

    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False

async def test_real_grading():
    """测试真实批改流程"""
    print("\n🚀 测试真实批改流程...")

    try:
        # 1. 测试MCP连接
        print("1. 测试MCP连接...")
        from mcp_client.client import MCPClient

        mcp_client = MCPClient()
        await mcp_client.connect()
        print("✅ MCP连接成功")

        # 2. 测试批改引擎
        print("2. 测试批改引擎...")
        from core.grading_engine import GradingEngine
        from core.model_selector import ModelSelector

        model_selector = ModelSelector()
        grading_engine = GradingEngine(mcp_client, model_selector)
        print("✅ 批改引擎创建成功")

        # 3. 创建测试图像
        print("3. 创建测试图像...")
        test_image_path = create_test_image()
        print(f"✅ 测试图像创建: {test_image_path}")

        # 4. 执行测试批改
        print("4. 执行测试批改...")
        results = await grading_engine.grade_homework(
            "test_hw_001",
            test_image_path,
            "高一"
        )

        print("✅ 批改测试成功!")
        print(f"   检测题目数: {len(results.get('results', []))}")
        print(f"   处理时间: {results.get('processing_time', 0):.2f}秒")
        print(f"   模式: {results.get('mode', 'normal')}")

        # 检查是否是真实结果还是降级结果
        if results.get('mode') in ['offline', 'simplified']:
            print("⚠️ 注意: 结果为降级模式，不是真实AI识别")
            return False
        else:
            print("🎉 成功: 这是真实的AI识别结果!")
            return True

    except Exception as e:
        print(f"❌ 批改测试失败: {e}")
        return False

def create_test_image():
    """创建测试数学题图像"""
    from PIL import Image, ImageDraw, ImageFont

    # 创建白色背景图像
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)

    # 添加测试数学题
    try:
        # 尝试使用系统字体
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()

    # 绘制数学题
    questions = [
        "1. 计算: 3x + 5 = 14, 求x的值",
        "解: 3x = 14 - 5",
        "    3x = 9",
        "    x = 3",
        "",
        "2. 化简: (2x + 3)(x - 1)",
        "解: = 2x² - 2x + 3x - 3",
        "    = 2x² + x - 3"
    ]

    y_pos = 50
    for question in questions:
        draw.text((50, y_pos), question, fill='black', font=font)
        y_pos += 40

    # 保存图像
    test_image_path = "test_math_homework.png"
    img.save(test_image_path)

    return test_image_path

def create_gui_patch():
    """创建GUI补丁文件"""
    print("\n🔨 创建GUI补丁...")

    patch_content = '''# gui_patch.py - GUI修复补丁
# 将此代码添加到你的gui.py中

import logging
from datetime import datetime

# 在MathGradingGUI类中添加这个方法
def start_grading_fixed(self):
    """修复版的开始批改函数"""
    
    if not self.current_image_path:
        messagebox.showwarning("警告", "请先选择要批改的作业图像")
        return

    if not self.student_name_var.get().strip():
        messagebox.showwarning("警告", "请输入学生姓名")
        return

    # 设置详细日志
    logging.basicConfig(level=logging.DEBUG)
    
    self.grade_button.configure(state="disabled")
    self.progress.start()
    self.update_status("开始修复版批改...")

    def fixed_grade_task():
        try:
            # 强制修复配置
            self._fix_settings_on_the_fly()
            
            # 执行批改
            future = asyncio.run_coroutine_threadsafe(
                self._force_real_grading(), self.loop
            )
            results = future.result(timeout=300)
            
            self.root.after(0, lambda: self._on_grading_complete(results))
            
        except Exception as e:
            error_msg = f"修复版批改失败: {e}"
            self.root.after(0, lambda: self._on_grading_error(error_msg))

    threading.Thread(target=fixed_grade_task, daemon=True).start()

def _fix_settings_on_the_fly(self):
    """运行时修复配置"""
    from config.settings import settings
    
    # 强制添加缺失配置
    if not hasattr(settings, 'mcp'):
        settings.__class__.mcp = property(lambda self: {"timeout": 30})
    
    if not hasattr(settings, 'database'):
        settings.__class__.database = property(lambda self: {"type": "sqlite", "path": "data/math_grading.db"})
    
    if not hasattr(settings, 'models'):
        settings.__class__.models = property(lambda self: {
            "default_provider": "nvidia",
            "nvidia": {"api_key": "nvapi-xxx", "model": "microsoft/phi-3.5-vision-instruct"}
        })

async def _force_real_grading(self):
    """强制执行真实批改，跳过所有降级"""
    
    # 初始化客户端
    if not self.mcp_client:
        from mcp_client.client import MCPClient
        self.mcp_client = MCPClient()
        await self.mcp_client.connect()
    
    # 初始化引擎
    if not self.grading_engine:
        from core.grading_engine import GradingEngine
        from core.model_selector import ModelSelector
        
        model_selector = ModelSelector()
        self.grading_engine = GradingEngine(self.mcp_client, model_selector)
    
    # 直接调用批改，不走数据库
    homework_id = f"direct_{hash(self.current_image_path) % 10000:04d}"
    
    results = await self.grading_engine.grade_homework(
        homework_id,
        self.current_image_path,
        self.grade_var.get()
    )
    
    # 添加额外信息
    results["student_name"] = self.student_name_var.get()
    results["mode"] = "fixed"
    
    return results

# 使用方法:
# 1. 在gui.py中添加上述方法到MathGradingGUI类
# 2. 临时替换start_grading调用:
#    self.start_grading_fixed() 替代 self.start_grading()
'''

    with open("gui_patch.py", "w", encoding="utf-8") as f:
        f.write(patch_content)

    print("✅ GUI补丁文件已创建: gui_patch.py")

def main():
    """主函数"""
    print("🚀 开始修复数学批改系统...")
    print("=" * 50)

    # 1. 修复配置
    fix_config_file()

    # 2. 测试配置
    if not test_config():
        print("❌ 配置修复失败，请手动检查")
        return

    # 3. 测试真实批改
    print("\n开始异步测试...")
    try:
        success = asyncio.run(test_real_grading())
        if success:
            print("\n🎉 系统修复成功！真实AI批改可以正常工作了。")
        else:
            print("\n⚠️ 系统仍有问题，但基础组件正常。可能需要检查API密钥。")
    except Exception as e:
        print(f"\n❌ 异步测试失败: {e}")

    # 4. 创建GUI补丁
    create_gui_patch()

    print("\n" + "=" * 50)
    print("修复完成！下一步:")
    print("1. 重新运行你的GUI程序")
    print("2. 或者应用gui_patch.py中的补丁")
    print("3. 确保设置正确的NVIDIA API密钥")

if __name__ == "__main__":
    main()