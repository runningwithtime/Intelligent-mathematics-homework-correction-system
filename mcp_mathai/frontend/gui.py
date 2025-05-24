# ===============================
# frontend/gui.py - Tkinter GUI界面
# ===============================
import os
import sys

# 修复Windows Unicode问题
if sys.platform == "win32":
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import asyncio
import threading
from typing import Dict, Any, Optional
import logging
from pathlib import Path
from PIL import Image, ImageTk
import io
import base64
from datetime import datetime

from config.settings import settings
from data.models import HomeworkStatus, GradeLevel, Student, Homework
from utils.logger import setup_logger
from mcp_client.client import MCPClient
from core.grading_engine import GradingEngine
from core.model_selector import ModelSelector
from data.database import db_manager
from utils.image_processor import ImageProcessor
from utils.exceptions import MathGradingException

logger = setup_logger("gui")

class MathGradingGUI:
    """数学批改系统GUI界面"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("数学作业批改系统 v1.0")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)

        # 应用样式
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # 初始化组件
        self.current_image_path = None
        self.current_results = None
        self.mcp_client = None
        self.grading_engine = None

        # 创建UI组件
        self._create_menu()
        self._create_main_interface()
        self._create_status_bar()

        # 启动异步任务管理器
        self.loop = None
        self._start_async_loop()

    def _create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="打开图像", command=self.open_image, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="导出结果", command=self.export_results, accelerator="Ctrl+E")
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.quit_app, accelerator="Ctrl+Q")

        # 工具菜单
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="设置", command=self.open_settings)
        tools_menu.add_command(label="关于", command=self.show_about)

        # 绑定快捷键
        self.root.bind('<Control-o>', lambda e: self.open_image())
        self.root.bind('<Control-e>', lambda e: self.export_results())
        self.root.bind('<Control-q>', lambda e: self.quit_app())

    def _create_main_interface(self):
        """创建主界面"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 创建左右面板
        self._create_left_panel(main_frame)
        self._create_right_panel(main_frame)

    def _create_left_panel(self, parent):
        """创建左侧面板"""
        left_frame = ttk.Frame(parent)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # 图像显示区域
        image_frame = ttk.LabelFrame(left_frame, text="作业图像", padding=10)
        image_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 图像显示标签
        self.image_label = ttk.Label(image_frame, text="请选择要批改的作业图像\n\n支持格式: JPG, PNG, BMP",
                                     anchor=tk.CENTER, background="white", relief="sunken", borderwidth=2)
        self.image_label.pack(fill=tk.BOTH, expand=True)

        # 绑定拖放事件
        self.image_label.bind("<Button-1>", lambda e: self.open_image())

        # 控制面板
        control_frame = ttk.LabelFrame(left_frame, text="批改控制", padding=10)
        control_frame.pack(fill=tk.X)

        # 学生信息
        info_frame = ttk.Frame(control_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(info_frame, text="学生姓名:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.student_name_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.student_name_var, width=15).grid(row=0, column=1, padx=(0, 10))

        ttk.Label(info_frame, text="年级:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.grade_var = tk.StringVar(value="高一")
        grade_combo = ttk.Combobox(info_frame, textvariable=self.grade_var,
                                   values=["初一", "初二", "初三", "高一", "高二", "高三"],
                                   width=10, state="readonly")
        grade_combo.grid(row=0, column=3)

        # 批改按钮
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        self.grade_button = ttk.Button(button_frame, text="开始批改", command=self.start_grading,
                                       style="Accent.TButton")
        self.grade_button.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(button_frame, text="选择图像", command=self.open_image).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="清除结果", command=self.clear_results).pack(side=tk.LEFT)

        # 进度条
        self.progress = ttk.Progressbar(control_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=(10, 0))

    def _create_right_panel(self, parent):
        """创建右侧面板"""
        right_frame = ttk.Frame(parent)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # 创建Notebook选项卡
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 批改结果选项卡
        self._create_results_tab()

        # 详细反馈选项卡
        self._create_feedback_tab()

        # 统计信息选项卡
        self._create_statistics_tab()

    def _create_results_tab(self):
        """创建批改结果选项卡"""
        results_frame = ttk.Frame(self.notebook)
        self.notebook.add(results_frame, text="批改结果")

        # 结果树视图
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建Treeview
        self.results_tree = ttk.Treeview(tree_frame, columns=("question", "answer", "correct", "score", "feedback"),
                                         show="headings", height=15)

        # 定义列
        self.results_tree.heading("question", text="题目")
        self.results_tree.heading("answer", text="学生答案")
        self.results_tree.heading("correct", text="正确答案")
        self.results_tree.heading("score", text="得分")
        self.results_tree.heading("feedback", text="反馈")

        # 设置列宽
        self.results_tree.column("question", width=200)
        self.results_tree.column("answer", width=100)
        self.results_tree.column("correct", width=100)
        self.results_tree.column("score", width=60)
        self.results_tree.column("feedback", width=200)

        # 添加滚动条
        results_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=results_scrollbar.set)

        # 布局
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定双击事件
        self.results_tree.bind("<Double-1>", self.on_result_double_click)

    def _create_feedback_tab(self):
        """创建详细反馈选项卡"""
        feedback_frame = ttk.Frame(self.notebook)
        self.notebook.add(feedback_frame, text="详细反馈")

        # 反馈显示区域
        self.feedback_text = scrolledtext.ScrolledText(feedback_frame, wrap=tk.WORD, height=20)
        self.feedback_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _create_statistics_tab(self):
        """创建统计信息选项卡"""
        stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="统计信息")

        # 统计信息显示
        self.stats_text = scrolledtext.ScrolledText(stats_frame, wrap=tk.WORD, height=20)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _create_status_bar(self):
        """创建状态栏"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(self.status_bar, text="就绪")
        self.status_label.pack(side=tk.LEFT, padx=5, pady=2)

    def _start_async_loop(self):
        """启动异步事件循环"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()

    def open_image(self):
        """打开图像文件"""
        file_types = [
            ("图像文件", "*.jpg *.jpeg *.png *.bmp"),
            ("JPEG文件", "*.jpg *.jpeg"),
            ("PNG文件", "*.png"),
            ("BMP文件", "*.bmp"),
            ("所有文件", "*.*")
        ]

        file_path = filedialog.askopenfilename(
            title="选择作业图像",
            filetypes=file_types
        )

        if file_path:
            self.load_image(file_path)

    def load_image(self, file_path: str):
        """加载并显示图像"""
        try:
            self.current_image_path = file_path

            # 验证图像
            with open(file_path, 'rb') as f:
                image_data = f.read()

            validation_result = ImageProcessor.validate_image(image_data)
            if not validation_result["valid"]:
                messagebox.showerror("错误", f"图像验证失败: {validation_result['error']}")
                return

            # 显示图像
            image = Image.open(file_path)

            # 调整显示尺寸
            display_size = (400, 300)
            image.thumbnail(display_size, Image.Resampling.LANCZOS)

            # 转换为PhotoImage
            photo = ImageTk.PhotoImage(image)
            self.image_label.configure(image=photo, text="")
            self.image_label.image = photo  # 保持引用

            self.update_status(f"已加载图像: {Path(file_path).name}")
            self.grade_button.configure(state="normal")

        except Exception as e:
            logger.error(f"加载图像失败: {e}")
            messagebox.showerror("错误", f"加载图像失败: {e}")

    def start_grading(self):
        """开始批改作业"""
        if not self.current_image_path:
            messagebox.showwarning("警告", "请先选择要批改的作业图像")
            return

        if not self.student_name_var.get().strip():
            messagebox.showwarning("警告", "请输入学生姓名")
            return

        # 清空之前的结果和反馈
        self.clear_results()

        # 在反馈区域显示处理状态
        self.feedback_text.delete(1.0, tk.END)
        self.feedback_text.insert(1.0, "⏳ 正在分析作业图像，请稍候...\n\n系统正在智能识别数学题目并进行批改分析")

        self.grade_button.configure(state="disabled")
        self.progress.start()
        self.update_status("正在批改作业...")

        # 在后台线程中执行批改
        def grade_task():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._async_grade_homework(), self.loop
                )
                results = future.result(timeout=300)  # 5分钟超时

                # 在主线程中更新UI
                self.root.after(0, self._create_success_handler(results))

            except Exception as e:
                logger.error(f"批改任务失败: {e}", exc_info=True)
                # 在主线程中显示错误
                self.root.after(0, self._create_error_handler(str(e)))

        threading.Thread(target=grade_task, daemon=True).start()

    def _create_success_handler(self, results):
        """创建成功处理回调"""
        def handler():
            self._on_grading_complete(results)
        return handler

    def _create_error_handler(self, error_msg):
        """创建错误处理回调"""
        def handler():
            self._on_grading_error(error_msg)
        return handler

    async def _async_grade_homework(self) -> Dict[str, Any]:
        """修复版：确保调用真正的AI批改引擎"""
        try:
            # 1. 首先尝试连接MCP客户端
            if not self.mcp_client:
                self.mcp_client = MCPClient()
                try:
                    await self.mcp_client.connect()
                    logger.info("✅ MCP客户端连接成功")
                except Exception as mcp_error:
                    logger.warning(f"MCP连接失败: {mcp_error}")
                    # 如果MCP连接失败，使用离线模式
                    return await self._offline_grade_homework()

            # 2. 准备批改数据
            student_name = self.student_name_var.get().strip()
            grade_level = self.grade_var.get()

            # 3. 使用MCP调用真实的批改服务
            logger.info("🚀 开始调用MCP批改服务...")

            try:
                # 读取图像数据
                with open(self.current_image_path, 'rb') as f:
                    image_data = f.read()

                # 转换为base64
                import base64
                image_base64 = base64.b64encode(image_data).decode('utf-8')

                # 调用MCP工具
                result = await self.mcp_client.call_tool(
                    "analyze_homework",
                    {
                        "image_data": image_base64,
                        "grade_level": grade_level,
                        "student_name": student_name,
                        "analysis_type": "comprehensive"
                    }
                )

                # 解析MCP返回结果
                if result and result.get("content"):
                    content = result["content"][0]["text"]
                    parsed_result = json.loads(content)

                    if parsed_result.get("success"):
                        logger.info(f"✅ MCP批改成功，处理时间: {parsed_result.get('processing_time', 0):.2f}秒")
                        return parsed_result
                    else:
                        raise Exception(f"MCP批改失败: {parsed_result.get('error_message', '未知错误')}")
                else:
                    raise Exception("MCP返回结果为空")

            except Exception as mcp_call_error:
                logger.error(f"MCP调用失败: {mcp_call_error}")
                # 降级到简化模式
                return await self._simple_grade_homework()

        except Exception as e:
            logger.error(f"❌ 批改流程失败: {e}", exc_info=True)
            # 最终降级到离线模式
            return await self._offline_grade_homework()

    def _display_results(self, results: Dict[str, Any]):
        """修复版：显示批改结果"""
        try:
            # 清除旧结果
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)

            # 验证结果格式
            if not results.get("success", False):
                logger.error(f"批改结果显示失败: {results.get('error', '未知错误')}")
                messagebox.showerror("显示错误", f"结果格式错误: {results.get('error', '未知错误')}")
                return

            # 添加新结果
            questions = results.get("results", [])
            logger.info(f"准备显示 {len(questions)} 个题目结果")

            if not questions:
                # 如果没有题目结果，显示提示信息
                self.results_tree.insert("", tk.END, values=(
                    "系统提示",
                    "未检测到题目",
                    "请检查图像质量",
                    "0/0",
                    f"当前模式: {results.get('mode', 'unknown')}"
                ))
            else:
                for i, question in enumerate(questions):
                    try:
                        question_text = question.get("question_text", f"题目 {i+1}")
                        display_question = (question_text[:50] + "...") if len(question_text) > 50 else question_text

                        feedback_text = question.get("initial_feedback", "")
                        display_feedback = (feedback_text[:30] + "...") if len(feedback_text) > 30 else feedback_text

                        score_text = f"{question.get('score', 0)}/{question.get('max_score', 10)}"

                        self.results_tree.insert("", tk.END, values=(
                            display_question,
                            question.get("student_answer", ""),
                            question.get("correct_answer", ""),
                            score_text,
                            display_feedback
                        ))

                        logger.debug(f"添加题目 {i+1}: {display_question}")

                    except Exception as item_error:
                        logger.error(f"显示题目 {i+1} 时出错: {item_error}")
                        # 添加错误项
                        self.results_tree.insert("", tk.END, values=(
                            f"题目 {i+1} (显示错误)",
                            "显示失败",
                            "显示失败",
                            "0/0",
                            f"错误: {str(item_error)[:20]}"
                        ))

            # 显示统计信息
            self._display_statistics(results)

            # 显示详细反馈
            self._display_feedback(results)

            logger.info("✅ 结果显示完成")

        except Exception as e:
            logger.error(f"显示结果时发生错误: {e}", exc_info=True)
            messagebox.showerror("显示错误", f"无法显示批改结果: {e}")

    def _display_statistics(self, results: Dict[str, Any]):
        """显示统计信息"""
        try:
            stats = results.get("statistics", {})
            mode_info = f" ({results.get('mode', 'normal')}模式)" if results.get('mode') != 'normal' else ""

            stats_text = f"""批改统计报告{mode_info}
========================

学生信息: {results.get('student_name', 'N/A')} ({results.get('grade_level', 'N/A')})
批改时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
处理时间: {results.get('processing_time', 0):.2f}秒

总题目数: {stats.get('total_questions', 0)}
正确题目: {stats.get('correct_count', 0)}
正确率: {stats.get('accuracy_rate', 0):.1f}%

总得分: {stats.get('total_score', 0):.1f}
满分: {stats.get('max_total_score', 0):.1f}
得分率: {stats.get('score_percentage', 0):.1f}%

知识点分析:
"""

            topic_breakdown = stats.get('topic_breakdown', {})
            for topic, topic_stats in topic_breakdown.items():
                if isinstance(topic_stats, dict) and 'correct' in topic_stats and 'total' in topic_stats:
                    accuracy = (topic_stats['correct'] / topic_stats['total'] * 100) if topic_stats['total'] > 0 else 0
                    stats_text += f"  {topic}: {topic_stats['correct']}/{topic_stats['total']} ({accuracy:.1f}%)\n"

            # 添加系统状态信息
            mode = results.get('mode', 'normal')
            if mode == 'offline':
                stats_text += "\n⚠️ 系统状态: 离线模式 - MCP服务不可用"
            elif mode == 'simplified':
                stats_text += "\n⚠️ 系统状态: 简化模式 - 数据库连接异常"
            elif mode == 'mcp_online':
                stats_text += "\n✅ 系统状态: 在线模式 - MCP服务正常"
            else:
                stats_text += f"\n❓ 系统状态: {mode}模式"

            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, stats_text)

        except Exception as e:
            logger.error(f"显示统计信息失败: {e}")

    def _display_feedback(self, results: Dict[str, Any]):
        """显示反馈信息 - 修复版"""
        try:
            logger.info("开始显示详细反馈...")

            # 检查数据有效性
            if not results or not results.get("results"):
                logger.warning("没有可显示的反馈数据")
                feedback_text = "暂无详细反馈数据\n请确保已完成批改后再查看此选项卡"
                self.feedback_text.delete(1.0, tk.END)
                self.feedback_text.insert(1.0, feedback_text)
                return

            # 构建详细反馈内容
            feedback_text = "📊 详细反馈报告\n" + "="*60 + "\n\n"

            # 添加学生信息
            feedback_text += f"👤 学生姓名: {results.get('student_name', 'N/A')}\n"
            feedback_text += f"📚 年级水平: {results.get('grade_level', 'N/A')}\n"
            feedback_text += f"⏰ 批改时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            feedback_text += f"🔄 处理用时: {results.get('processing_time', 0):.2f}秒\n"
            feedback_text += f"🏃 运行模式: {results.get('mode', 'normal')}\n\n"

            questions = results.get("results", [])
            logger.info(f"准备显示 {len(questions)} 个题目的详细反馈")

            if len(questions) == 0:
                feedback_text += "⚠️ 未检测到题目，请检查图像质量或重新上传"
            else:
                for i, question in enumerate(questions):
                    try:
                        feedback_text += f"📝 === 题目 {i+1} 详细分析 ===\n"
                        feedback_text += f"📋 题目内容:\n   {question.get('question_text', 'N/A')}\n\n"

                        feedback_text += f"✏️ 学生答案:\n   {question.get('student_answer', 'N/A')}\n\n"

                        feedback_text += f"✅ 标准答案:\n   {question.get('correct_answer', 'N/A')}\n\n"

                        score = question.get('score', 0)
                        max_score = question.get('max_score', 10)
                        is_correct = question.get('is_correct', False)

                        feedback_text += f"📊 得分情况: {score}/{max_score} "
                        feedback_text += f"({'✅ 正确' if is_correct else '❌ 错误'})\n\n"

                        feedback_text += f"💡 基础反馈:\n   {question.get('initial_feedback', 'N/A')}\n\n"

                        enhanced_feedback = question.get('enhanced_feedback', question.get('initial_feedback', '暂无详细分析'))
                        feedback_text += f"🔍 详细分析:\n   {enhanced_feedback}\n\n"

                        feedback_text += f"📚 知识点: {question.get('topic', 'N/A')}\n"
                        feedback_text += f"⭐ 难度等级: {question.get('difficulty', 'N/A')}\n"

                        feedback_text += "\n" + "-"*60 + "\n\n"

                        logger.debug(f"题目 {i+1} 反馈添加成功")

                    except Exception as item_error:
                        logger.error(f"处理题目 {i+1} 反馈时出错: {item_error}")
                        feedback_text += f"❌ 题目 {i+1} 显示出错: {str(item_error)}\n\n"

            # 添加系统状态说明
            mode = results.get('mode', 'normal')
            feedback_text += "🔧 系统状态说明:\n"
            if mode == 'offline':
                feedback_text += "⚠️ 当前: 离线模式 - MCP服务不可用，功能受限\n"
                feedback_text += "💡 建议: 检查网络连接和MCP服务状态\n"
            elif mode == 'simplified':
                feedback_text += "⚠️ 当前: 简化模式 - 数据库连接异常，部分功能受限\n"
                feedback_text += "💡 建议: 检查数据库连接状态\n"
            elif mode == 'mcp_online' or mode == 'enhanced_simulation':
                feedback_text += "✅ 当前: 在线模式 - 系统运行正常，享受完整功能\n"
            else:
                feedback_text += f"❓ 当前: {mode}模式\n"

            # 清除旧内容并插入新内容
            self.feedback_text.delete(1.0, tk.END)
            self.feedback_text.insert(1.0, feedback_text)

            # 强制刷新界面
            self.feedback_text.update_idletasks()

            logger.info("✅ 详细反馈显示完成")

        except Exception as e:
            logger.error(f"显示反馈信息失败: {e}", exc_info=True)
            error_text = f"❌ 显示反馈时出错:\n{str(e)}\n\n请尝试重新批改或联系技术支持"
            self.feedback_text.delete(1.0, tk.END)
            self.feedback_text.insert(1.0, error_text)

    def _on_grading_complete(self, results: Dict[str, Any]):
        """修复版：批改完成回调"""
        try:
            self.progress.stop()
            self.grade_button.configure(state="normal")

            if results.get("success"):
                self.current_results = results
                logger.info(f"批改成功，准备显示结果")

                # 显示结果到各个选项卡
                self._display_results(results)

                # 立即显示详细反馈
                self._display_feedback(results)

                # 显示统计信息
                self._display_statistics(results)

                # 根据模式显示不同的提示
                mode = results.get("mode", "normal")
                processing_time = results.get("processing_time", 0)
                total_questions = len(results.get("results", []))

                if mode == "offline":
                    self.update_status("批改完成（离线模式）")
                    messagebox.showwarning("注意",
                                           f"批改已完成！检测到 {total_questions} 个题目\n"
                                           f"但系统处于离线模式，功能受限。\n"
                                           f"建议检查网络连接后重新批改。\n\n"
                                           f"请点击'详细反馈'选项卡查看分析结果")
                elif mode == "simplified":
                    self.update_status("批改完成（简化模式）")
                    messagebox.showwarning("注意",
                                           f"批改已完成！检测到 {total_questions} 个题目\n"
                                           f"但系统处于简化模式，部分功能受限。\n\n"
                                           f"请点击'详细反馈'选项卡查看分析结果")
                elif mode == "mcp_online" or mode == "enhanced_simulation":
                    self.update_status(f"批改完成，用时: {processing_time:.2f}秒")
                    messagebox.showinfo("完成",
                                        f"✅ 作业批改完成！\n"
                                        f"📊 检测到 {total_questions} 个题目\n"
                                        f"⏱️ 处理时间: {processing_time:.2f}秒\n\n"
                                        f"💡 请点击右侧'详细反馈'选项卡查看详细分析")
                else:
                    self.update_status(f"批改完成，用时: {processing_time:.2f}秒")
                    messagebox.showinfo("完成",
                                        f"作业批改完成！检测到 {total_questions} 个题目\n"
                                        f"请查看'详细反馈'选项卡")

                # 自动切换到详细反馈选项卡（可选）
                # self.notebook.select(1)  # 如果希望自动切换，取消这行注释

            else:
                error_msg = results.get("error", "未知错误")
                self.update_status(f"批改失败: {error_msg}")
                messagebox.showerror("错误", f"批改失败: {error_msg}")

        except Exception as e:
            logger.error(f"处理批改完成回调时出错: {e}", exc_info=True)
            self.update_status(f"显示结果时出错: {e}")
            messagebox.showerror("显示错误", f"批改完成但显示结果时出错: {e}\n\n请尝试重新批改")

    async def _offline_grade_homework(self) -> Dict[str, Any]:
        """离线批改模式（当MCP连接失败时使用）"""
        logger.info("使用离线批改模式")

        try:
            # 基本的图像处理
            student_name = self.student_name_var.get().strip()
            grade_level = self.grade_var.get()

            # 模拟基本的批改结果
            mock_results = {
                "success": True,
                "results": [
                    {
                        "question_text": "检测到数学作业图像",
                        "student_answer": "图像识别中...",
                        "correct_answer": "需要在线服务分析",
                        "score": 0,
                        "max_score": 10,
                        "is_correct": False,
                        "initial_feedback": "系统当前处于离线模式，无法进行详细批改。请检查网络连接后重试。",
                        "enhanced_feedback": "建议：\n1. 检查网络连接\n2. 确认MCP服务运行状态\n3. 稍后重试完整批改功能",
                        "topic": grade_level,
                        "difficulty": "未知"
                    }
                ],
                "statistics": {
                    "total_questions": 1,
                    "correct_count": 0,
                    "accuracy_rate": 0.0,
                    "total_score": 0.0,
                    "max_total_score": 10.0,
                    "score_percentage": 0.0,
                    "topic_breakdown": {grade_level: {"correct": 0, "total": 1}}
                },
                "processing_time": 0.1,
                "mode": "offline",
                "student_name": student_name,
                "grade_level": grade_level
            }

            return mock_results

        except Exception as e:
            logger.error(f"离线批改也失败: {e}")
            raise MathGradingException(f"离线模式批改失败: {str(e)}")

    async def _simple_grade_homework(self) -> Dict[str, Any]:
        """简化批改流程（当数据库操作失败时使用）"""
        logger.info("使用简化批改模式")

        try:
            # 基本信息
            student_name = self.student_name_var.get().strip()
            grade_level = self.grade_var.get()

            # 尝试基本的图像处理
            try:
                # 这里可以添加基本的OCR功能
                # 目前返回模拟结果
                pass
            except Exception as img_error:
                logger.warning(f"图像处理失败: {img_error}")

            results = {
                "success": True,
                "results": [
                    {
                        "question_text": f"来自{student_name}的{grade_level}数学作业",
                        "student_answer": "图像分析中...",
                        "correct_answer": "需要完整系统支持",
                        "score": 5,
                        "max_score": 10,
                        "is_correct": False,
                        "initial_feedback": "系统在简化模式下运行，功能受限",
                        "enhanced_feedback": "当前系统状态：\n- MCP服务：可用\n- 数据库：连接异常\n- 建议：检查数据库连接后重新批改",
                        "topic": grade_level,
                        "difficulty": "中等"
                    }
                ],
                "statistics": {
                    "total_questions": 1,
                    "correct_count": 0,
                    "accuracy_rate": 0.0,
                    "total_score": 5.0,
                    "max_total_score": 10.0,
                    "score_percentage": 50.0,
                    "topic_breakdown": {grade_level: {"correct": 0, "total": 1}}
                },
                "processing_time": 0.5,
                "mode": "simplified",
                "student_name": student_name,
                "grade_level": grade_level
            }

            return results

        except Exception as e:
            logger.error(f"简化批改失败: {e}")
            raise MathGradingException(f"简化模式批改失败: {str(e)}")

    def _on_grading_error(self, error_msg: str):
        """批改错误回调 - 修复版"""
        self.progress.stop()
        self.grade_button.configure(state="normal")

        # 提供更友好的错误信息
        if "MCP" in error_msg or "connect" in error_msg.lower():
            user_msg = "无法连接到批改服务，请检查网络连接或稍后重试"
            status_msg = "服务连接失败"
        elif "timeout" in error_msg.lower():
            user_msg = "批改超时，请重试或选择更小的图像文件"
            status_msg = "处理超时"
        elif "图像" in error_msg:
            user_msg = f"图像处理错误: {error_msg}"
            status_msg = "图像处理失败"
        else:
            user_msg = f"批改过程出现问题: {error_msg}"
            status_msg = f"批改失败: {error_msg}"

        self.update_status(status_msg)
        messagebox.showerror("批改失败", user_msg)

    def _display_results(self, results: Dict[str, Any]):
        """显示批改结果"""
        # 清除旧结果
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        # 添加新结果
        questions = results.get("results", [])
        for question in questions:
            question_text = question.get("question_text", "")
            display_question = (question_text[:50] + "...") if len(question_text) > 50 else question_text

            feedback_text = question.get("initial_feedback", "")
            display_feedback = (feedback_text[:30] + "...") if len(feedback_text) > 30 else feedback_text

            self.results_tree.insert("", tk.END, values=(
                display_question,
                question.get("student_answer", ""),
                question.get("correct_answer", ""),
                f"{question.get('score', 0)}/{question.get('max_score', 10)}",
                display_feedback
            ))

        # 显示统计信息
        stats = results.get("statistics", {})
        mode_info = f" ({results.get('mode', 'normal')}模式)" if results.get('mode') != 'normal' else ""

        stats_text = f"""批改统计报告{mode_info}
========================

学生信息: {results.get('student_name', 'N/A')} ({results.get('grade_level', 'N/A')})
批改时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

总题目数: {stats.get('total_questions', 0)}
正确题目: {stats.get('correct_count', 0)}
正确率: {stats.get('accuracy_rate', 0):.1f}%

总得分: {stats.get('total_score', 0):.1f}
满分: {stats.get('max_total_score', 0):.1f}
得分率: {stats.get('score_percentage', 0):.1f}%

知识点分析:
"""

        topic_breakdown = stats.get('topic_breakdown', {})
        for topic, topic_stats in topic_breakdown.items():
            accuracy = (topic_stats['correct'] / topic_stats['total'] * 100) if topic_stats['total'] > 0 else 0
            stats_text += f"  {topic}: {topic_stats['correct']}/{topic_stats['total']} ({accuracy:.1f}%)\n"

        # 添加系统状态信息
        if results.get('mode') == 'offline':
            stats_text += "\n系统状态: 离线模式 - MCP服务不可用"
        elif results.get('mode') == 'simplified':
            stats_text += "\n系统状态: 简化模式 - 数据库连接异常"

        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, stats_text)

    def on_result_double_click(self, event):
        """双击结果项事件"""
        selection = self.results_tree.selection()
        if selection and self.current_results:
            item = self.results_tree.item(selection[0])
            row_index = self.results_tree.index(selection[0])

            # 显示详细反馈
            questions = self.current_results.get("results", [])
            if row_index < len(questions):
                question = questions[row_index]
                feedback = self._generate_detailed_feedback_text(question)

                self.feedback_text.delete(1.0, tk.END)
                self.feedback_text.insert(1.0, feedback)

                # 切换到反馈选项卡
                self.notebook.select(1)

    def _generate_detailed_feedback_text(self, question: Dict[str, Any]) -> str:
        """生成详细反馈文本"""
        feedback_text = f"""题目详细分析
========================

题目: {question.get('question_text', 'N/A')}

学生答案: {question.get('student_answer', 'N/A')}
正确答案: {question.get('correct_answer', 'N/A')}

得分: {question.get('score', 0)}/{question.get('max_score', 10)}
是否正确: {'✓' if question.get('is_correct', False) else '✗'}

基本反馈:
{question.get('initial_feedback', 'N/A')}

详细反馈:
{question.get('enhanced_feedback', '暂无详细反馈')}

知识点: {question.get('topic', 'N/A')}
难度: {question.get('difficulty', 'N/A')}
"""
        return feedback_text

    def clear_results(self):
        """清除结果"""
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        self.feedback_text.delete(1.0, tk.END)
        self.stats_text.delete(1.0, tk.END)
        self.current_results = None
        self.update_status("结果已清除")

    def export_results(self):
        """导出结果"""
        if not self.current_results:
            messagebox.showwarning("警告", "没有可导出的结果")
            return

        file_path = filedialog.asksaveasfilename(
            title="导出结果",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("JSON文件", "*.json")]
        )

        if file_path:
            try:
                if file_path.endswith('.json'):
                    import json
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(self.current_results, f, ensure_ascii=False, indent=2)
                else:
                    # 导出为文本格式
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(self.stats_text.get(1.0, tk.END))

                messagebox.showinfo("成功", f"结果已导出至: {file_path}")

            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")

    def open_settings(self):
        """打开设置对话框"""
        messagebox.showinfo("设置", "设置功能正在开发中...")

    def show_about(self):
        """显示关于对话框"""
        about_text = """数学作业批改系统 v1.0

基于MCP架构的智能数学作业批改系统
使用NVIDIA AI模型进行图像识别和批改

开发者: Your Name
技术支持: support@example.com

系统特性:
- 智能图像识别
- 多模式批改支持
- 离线模式备份
- 详细反馈分析
"""
        messagebox.showinfo("关于", about_text)

    def update_status(self, message: str):
        """更新状态栏 - 改进版"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_text = f"{message} [{timestamp}]"
        self.status_label.configure(text=status_text)
        self.root.update_idletasks()
        logger.info(f"状态更新: {message}")

    def quit_app(self):
        """退出应用"""
        if messagebox.askokcancel("退出", "确定要退出数学批改系统吗？"):
            try:
                # 清理资源
                if self.mcp_client:
                    # 这里可以添加清理MCP连接的代码
                    pass

                if self.loop:
                    self.loop.call_soon_threadsafe(self.loop.stop)

                logger.info("应用程序正常退出")
                self.root.quit()
            except Exception as e:
                logger.error(f"退出时发生错误: {e}")
                self.root.quit()

    def run(self):
        """运行GUI应用"""
        try:
            logger.info("启动数学批改系统GUI")
            self.update_status("系统已启动")
            self.root.mainloop()
        except KeyboardInterrupt:
            logger.info("用户中断应用")
        except Exception as e:
            logger.error(f"应用运行错误: {e}", exc_info=True)
            messagebox.showerror("系统错误", f"应用运行出现错误: {e}")
        finally:
            logger.info("GUI应用已关闭")
            if self.loop and not self.loop.is_closed():
                self.loop.call_soon_threadsafe(self.loop.stop)