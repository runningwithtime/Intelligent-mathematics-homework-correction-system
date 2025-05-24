# gui_patch.py - GUI修复补丁
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
