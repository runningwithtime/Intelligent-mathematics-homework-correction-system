# ===============================
# api/routes.py - API路由定义
# ===============================
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import asyncio
import logging
import threading
from typing import Dict, Any
from pathlib import Path
import tempfile
import os

from .handlers import (
    HomeworkHandler,
    StudentHandler,
    GradingHandler,
    FileHandler,
    StatisticsHandler
)
from config.settings import settings
from utils.logger import setup_logger
from utils.exceptions import MathGradingException

logger = setup_logger("api")

def create_app() -> Flask:
    """创建Flask应用"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'math-grading-secret-key'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

    # 启用CORS
    CORS(app)

    # 初始化处理器
    homework_handler = HomeworkHandler()
    student_handler = StudentHandler()
    grading_handler = GradingHandler()
    file_handler = FileHandler()
    statistics_handler = StatisticsHandler()

    # 启动异步事件循环
    loop = asyncio.new_event_loop()

    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    threading.Thread(target=run_loop, daemon=True).start()

    # ============ 错误处理器 ============

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "API端点未找到", "code": 404}), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"内部服务器错误: {error}")
        return jsonify({"error": "内部服务器错误", "code": 500}), 500

    @app.errorhandler(MathGradingException)
    def handle_grading_exception(error):
        logger.error(f"批改系统错误: {error}")
        return jsonify({"error": str(error), "code": 400}), 400

    # ============ 健康检查 ============

    @app.route('/health', methods=['GET'])
    def health_check():
        """健康检查接口"""
        return jsonify({
            "status": "healthy",
            "service": "math-grading-api",
            "version": "1.0.0"
        })

    # ============ 文件上传和管理 ============

    @app.route('/api/upload', methods=['POST'])
    def upload_homework():
        """上传作业图像"""
        try:
            if 'file' not in request.files:
                return jsonify({"error": "没有上传文件"}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({"error": "文件名为空"}), 400

            # 获取额外参数
            student_name = request.form.get('student_name', '')
            grade_level = request.form.get('grade_level', '高一')

            # 异步处理文件上传
            future = asyncio.run_coroutine_threadsafe(
                file_handler.handle_upload(file, student_name, grade_level), loop
            )
            result = future.result(timeout=30)

            if result['success']:
                return jsonify({
                    "success": True,
                    "homework_id": result['homework_id'],
                    "message": "文件上传成功"
                })
            else:
                return jsonify({
                    "success": False,
                    "error": result['error']
                }), 400

        except Exception as e:
            logger.error(f"文件上传失败: {e}")
            return jsonify({"error": f"上传失败: {e}"}), 500

    @app.route('/api/homework/<homework_id>/image', methods=['GET'])
    def get_homework_image(homework_id: str):
        """获取作业图像"""
        try:
            image_path = homework_handler.get_homework_image_path(homework_id)
            if image_path and Path(image_path).exists():
                return send_file(image_path)
            else:
                return jsonify({"error": "图像文件不存在"}), 404
        except Exception as e:
            logger.error(f"获取图像失败: {e}")
            return jsonify({"error": str(e)}), 500

    # ============ 批改相关接口 ============

    @app.route('/api/homework/<homework_id>/grade', methods=['POST'])
    def grade_homework(homework_id: str):
        """批改指定作业"""
        try:
            # 异步执行批改
            future = asyncio.run_coroutine_threadsafe(
                grading_handler.grade_homework(homework_id), loop
            )
            result = future.result(timeout=300)  # 5分钟超时

            return jsonify(result)

        except asyncio.TimeoutError:
            return jsonify({"error": "批改超时，请稍后重试"}), 408
        except Exception as e:
            logger.error(f"批改失败: {e}")
            return jsonify({"error": f"批改失败: {e}"}), 500

    @app.route('/api/homework/<homework_id>/results', methods=['GET'])
    def get_homework_results(homework_id: str):
        """获取作业批改结果"""
        try:
            results = homework_handler.get_homework_results(homework_id)
            return jsonify(results)
        except Exception as e:
            logger.error(f"获取结果失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/homework/<homework_id>/feedback', methods=['POST'])
    def generate_detailed_feedback(homework_id: str):
        """生成详细反馈"""
        try:
            data = request.get_json()
            question_id = data.get('question_id')

            if not question_id:
                return jsonify({"error": "缺少question_id参数"}), 400

            # 异步生成反馈
            future = asyncio.run_coroutine_threadsafe(
                grading_handler.generate_detailed_feedback(homework_id, question_id), loop
            )
            result = future.result(timeout=60)

            return jsonify(result)

        except Exception as e:
            logger.error(f"生成反馈失败: {e}")
            return jsonify({"error": str(e)}), 500

    # ============ 学生管理接口 ============

    @app.route('/api/students', methods=['GET'])
    def list_students():
        """获取学生列表"""
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)

            students = student_handler.list_students(page, per_page)
            return jsonify(students)
        except Exception as e:
            logger.error(f"获取学生列表失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/students', methods=['POST'])
    def create_student():
        """创建学生"""
        try:
            data = request.get_json()
            student = student_handler.create_student(data)
            return jsonify(student), 201
        except Exception as e:
            logger.error(f"创建学生失败: {e}")
            return jsonify({"error": str(e)}), 400

    @app.route('/api/students/<student_id>', methods=['GET'])
    def get_student(student_id: str):
        """获取学生详情"""
        try:
            student = student_handler.get_student(student_id)
            if student:
                return jsonify(student)
            else:
                return jsonify({"error": "学生不存在"}), 404
        except Exception as e:
            logger.error(f"获取学生详情失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/students/<student_id>/homeworks', methods=['GET'])
    def get_student_homeworks(student_id: str):
        """获取学生作业列表"""
        try:
            homeworks = student_handler.get_student_homeworks(student_id)
            return jsonify(homeworks)
        except Exception as e:
            logger.error(f"获取学生作业失败: {e}")
            return jsonify({"error": str(e)}), 500

    # ============ 作业管理接口 ============

    @app.route('/api/homeworks', methods=['GET'])
    def list_homeworks():
        """获取作业列表"""
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            status = request.args.get('status')  # graded, ungraded, all

            homeworks = homework_handler.list_homeworks(page, per_page, status)
            return jsonify(homeworks)
        except Exception as e:
            logger.error(f"获取作业列表失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/homeworks/<homework_id>', methods=['GET'])
    def get_homework(homework_id: str):
        """获取作业详情"""
        try:
            homework = homework_handler.get_homework(homework_id)
            if homework:
                return jsonify(homework)
            else:
                return jsonify({"error": "作业不存在"}), 404
        except Exception as e:
            logger.error(f"获取作业详情失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/homeworks/<homework_id>', methods=['DELETE'])
    def delete_homework(homework_id: str):
        """删除作业"""
        try:
            success = homework_handler.delete_homework(homework_id)
            if success:
                return jsonify({"message": "作业已删除"})
            else:
                return jsonify({"error": "作业不存在"}), 404
        except Exception as e:
            logger.error(f"删除作业失败: {e}")
            return jsonify({"error": str(e)}), 500

    # ============ 统计分析接口 ============

    @app.route('/api/statistics/overview', methods=['GET'])
    def get_statistics_overview():
        """获取统计概览"""
        try:
            stats = statistics_handler.get_overview_statistics()
            return jsonify(stats)
        except Exception as e:
            logger.error(f"获取统计概览失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/statistics/student/<student_id>', methods=['GET'])
    def get_student_statistics(student_id: str):
        """获取学生统计信息"""
        try:
            stats = statistics_handler.get_student_statistics(student_id)
            return jsonify(stats)
        except Exception as e:
            logger.error(f"获取学生统计失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/statistics/grade/<grade_level>', methods=['GET'])
    def get_grade_statistics(grade_level: str):
        """获取年级统计信息"""
        try:
            stats = statistics_handler.get_grade_statistics(grade_level)
            return jsonify(stats)
        except Exception as e:
            logger.error(f"获取年级统计失败: {e}")
            return jsonify({"error": str(e)}), 500

    # ============ 工具接口 ============

    @app.route('/api/tools/similar-problems', methods=['POST'])
    def generate_similar_problems():
        """生成相似题目"""
        try:
            data = request.get_json()
            original_question = data.get('original_question')
            count = data.get('count', 3)
            difficulty = data.get('difficulty', 'same')

            if not original_question:
                return jsonify({"error": "缺少原始题目"}), 400

            # 异步生成相似题目
            future = asyncio.run_coroutine_threadsafe(
                grading_handler.generate_similar_problems(original_question, count, difficulty), loop
            )
            result = future.result(timeout=60)

            return jsonify(result)

        except Exception as e:
            logger.error(f"生成相似题目失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/tools/validate-expression', methods=['POST'])
    def validate_math_expression():
        """验证数学表达式"""
        try:
            data = request.get_json()
            expression = data.get('expression')
            expected_result = data.get('expected_result')

            if not expression:
                return jsonify({"error": "缺少数学表达式"}), 400

            # 异步验证表达式
            future = asyncio.run_coroutine_threadsafe(
                grading_handler.validate_expression(expression, expected_result), loop
            )
            result = future.result(timeout=30)

            return jsonify(result)

        except Exception as e:
            logger.error(f"验证表达式失败: {e}")
            return jsonify({"error": str(e)}), 500

    # ============ 导出功能 ============

    @app.route('/api/export/homework/<homework_id>', methods=['GET'])
    def export_homework_results(homework_id: str):
        """导出作业结果"""
        try:
            format_type = request.args.get('format', 'json')  # json, txt, pdf

            file_path = homework_handler.export_homework_results(homework_id, format_type)

            if file_path and Path(file_path).exists():
                return send_file(file_path, as_attachment=True)
            else:
                return jsonify({"error": "导出失败"}), 500

        except Exception as e:
            logger.error(f"导出结果失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/export/student/<student_id>', methods=['GET'])
    def export_student_report(student_id: str):
        """导出学生报告"""
        try:
            format_type = request.args.get('format', 'pdf')

            file_path = student_handler.export_student_report(student_id, format_type)

            if file_path and Path(file_path).exists():
                return send_file(file_path, as_attachment=True)
            else:
                return jsonify({"error": "导出失败"}), 500

        except Exception as e:
            logger.error(f"导出学生报告失败: {e}")
            return jsonify({"error": str(e)}), 500

    # ============ 系统配置接口 ============

    @app.route('/api/config', methods=['GET'])
    def get_system_config():
        """获取系统配置"""
        try:
            config = {
                "models": {
                    "primary": settings.get("models.primary"),
                    "fallback": settings.get("models.fallback")
                },
                "image": {
                    "max_size": settings.get("image.max_size"),
                    "allowed_formats": settings.get("image.allowed_formats")
                },
                "server": {
                    "max_connections": settings.get("server.max_connections")
                }
            }
            return jsonify(config)
        except Exception as e:
            logger.error(f"获取配置失败: {e}")
            return jsonify({"error": str(e)}), 500

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(
        host=settings.get("server.host", "localhost"),
        port=settings.get("server.port", 8765) + 1,
        debug=True
    )