# ===============================
# api/handlers.py - API请求处理器
# ===============================
import asyncio
import logging
import tempfile
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from werkzeug.datastructures import FileStorage
from datetime import datetime

from data.database import db_manager
from data.models import Student, Homework, Question
from core.grading_engine import GradingEngine
from core.model_selector import ModelSelector
from mcp_client.client import MCPClient
from utils.image_processor import ImageProcessor
from utils.exceptions import MathGradingException, DatabaseError, ImageProcessingError
from config.settings import settings

logger = logging.getLogger(__name__)

class BaseHandler:
    """基础处理器类"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

class FileHandler(BaseHandler):
    """文件处理器"""

    async def handle_upload(self, file: FileStorage, student_name: str, grade_level: str) -> Dict[str, Any]:
        """处理文件上传"""
        try:
            # 验证文件
            if not file or file.filename == '':
                raise ValueError("无效的文件")

            # 读取文件数据
            file_data = file.read()

            # 验证图像
            validation_result = ImageProcessor.validate_image(file_data)
            if not validation_result["valid"]:
                raise ImageProcessingError(f"图像验证失败: {validation_result['error']}")

            # 创建临时文件
            temp_dir = Path(tempfile.gettempdir()) / "math_grading"
            temp_dir.mkdir(exist_ok=True)

            file_extension = Path(file.filename).suffix.lower()
            temp_file = temp_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"

            # 保存文件
            with open(temp_file, 'wb') as f:
                f.write(file_data)

            # 创建学生记录（如果不存在）
            try:
                student = db_manager.create_student(
                    name=student_name,
                    student_id=f"STU_{hash(student_name) % 10000:04d}",
                    grade=grade_level
                )
            except Exception:
                # 如果学生已存在，查找现有记录
                with db_manager.get_session() as session:
                    student = session.query(Student).filter(Student.name == student_name).first()
                    if not student:
                        raise DatabaseError("创建学生记录失败")

            # 创建作业记录
            homework = db_manager.create_homework(
                student_id=student.id,
                title=f"{file.filename}",
                grade_level=grade_level,
                image_path=str(temp_file)
            )

            self.logger.info(f"文件上传成功: {file.filename}, 作业ID: {homework.id}")

            return {
                "success": True,
                "homework_id": homework.id,
                "file_path": str(temp_file),
                "student_id": student.id
            }

        except Exception as e:
            self.logger.error(f"文件上传处理失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

class HomeworkHandler(BaseHandler):
    """作业处理器"""

    def list_homeworks(self, page: int = 1, per_page: int = 20, status: str = None) -> Dict[str, Any]:
        """获取作业列表"""
        try:
            with db_manager.get_session() as session:
                query = session.query(Homework).join(Student)

                # 状态过滤
                if status == 'graded':
                    query = query.filter(Homework.graded_at.isnot(None))
                elif status == 'ungraded':
                    query = query.filter(Homework.graded_at.is_(None))

                # 分页
                total = query.count()
                homeworks = query.offset((page - 1) * per_page).limit(per_page).all()

                homework_list = []
                for homework in homeworks:
                    homework_data = {
                        "id": homework.id,
                        "title": homework.title,
                        "student_name": homework.student.name,
                        "grade_level": homework.grade_level,
                        "submitted_at": homework.submitted_at.isoformat() if homework.submitted_at else None,
                        "graded_at": homework.graded_at.isoformat() if homework.graded_at else None,
                        "total_score": homework.total_score,
                        "max_score": homework.max_score,
                        "status": "已批改" if homework.graded_at else "未批改"
                    }
                    homework_list.append(homework_data)

                return {
                    "homeworks": homework_list,
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": total,
                        "pages": (total + per_page - 1) // per_page
                    }
                }

        except Exception as e:
            self.logger.error(f"获取作业列表失败: {e}")
            raise DatabaseError(f"获取作业列表失败: {e}")

    def get_homework(self, homework_id: str) -> Optional[Dict[str, Any]]:
        """获取作业详情"""
        try:
            with db_manager.get_session() as session:
                homework = session.query(Homework).filter(Homework.id == homework_id).first()

                if not homework:
                    return None

                # 获取问题列表
                questions = session.query(Question).filter(Question.homework_id == homework_id).all()

                question_list = []
                for question in questions:
                    question_data = {
                        "id": question.id,
                        "question_number": question.question_number,
                        "question_text": question.question_text,
                        "student_answer": question.student_answer,
                        "correct_answer": question.correct_answer,
                        "score": question.score,
                        "max_score": question.max_score,
                        "is_correct": question.is_correct,
                        "feedback": question.feedback
                    }
                    question_list.append(question_data)

                homework_data = {
                    "id": homework.id,
                    "title": homework.title,
                    "student_name": homework.student.name,
                    "student_id": homework.student.student_id,
                    "grade_level": homework.grade_level,
                    "image_path": homework.image_path,
                    "submitted_at": homework.submitted_at.isoformat() if homework.submitted_at else None,
                    "graded_at": homework.graded_at.isoformat() if homework.graded_at else None,
                    "total_score": homework.total_score,
                    "max_score": homework.max_score,
                    "questions": question_list
                }

                return homework_data

        except Exception as e:
            self.logger.error(f"获取作业详情失败: {e}")
            raise DatabaseError(f"获取作业详情失败: {e}")

    def get_homework_results(self, homework_id: str) -> Dict[str, Any]:
        """获取作业批改结果"""
        homework = self.get_homework(homework_id)
        if not homework:
            raise ValueError("作业不存在")

        # 计算统计信息
        questions = homework.get("questions", [])
        total_questions = len(questions)
        correct_count = sum(1 for q in questions if q.get("is_correct", False))
        total_score = sum(q.get("score", 0) for q in questions)
        max_total_score = sum(q.get("max_score", 0) for q in questions)

        statistics = {
            "total_questions": total_questions,
            "correct_count": correct_count,
            "wrong_count": total_questions - correct_count,
            "accuracy_rate": (correct_count / total_questions * 100) if total_questions > 0 else 0,
            "total_score": total_score,
            "max_total_score": max_total_score,
            "score_percentage": (total_score / max_total_score * 100) if max_total_score > 0 else 0
        }

        return {
            "homework": homework,
            "statistics": statistics
        }

    def get_homework_image_path(self, homework_id: str) -> Optional[str]:
        """获取作业图像路径"""
        try:
            with db_manager.get_session() as session:
                homework = session.query(Homework).filter(Homework.id == homework_id).first()
                return homework.image_path if homework else None
        except Exception as e:
            self.logger.error(f"获取图像路径失败: {e}")
            return None

    def delete_homework(self, homework_id: str) -> bool:
        """删除作业"""
        try:
            with db_manager.get_session() as session:
                homework = session.query(Homework).filter(Homework.id == homework_id).first()

                if not homework:
                    return False

                # 删除关联的问题
                session.query(Question).filter(Question.homework_id == homework_id).delete()

                # 删除图像文件
                if homework.image_path and Path(homework.image_path).exists():
                    Path(homework.image_path).unlink()

                # 删除作业记录
                session.delete(homework)
                session.commit()

                self.logger.info(f"作业已删除: {homework_id}")
                return True

        except Exception as e:
            self.logger.error(f"删除作业失败: {e}")
            raise DatabaseError(f"删除作业失败: {e}")

    def export_homework_results(self, homework_id: str, format_type: str = "json") -> Optional[str]:
        """导出作业结果"""
        try:
            homework_data = self.get_homework_results(homework_id)

            if not homework_data:
                return None

            # 创建导出文件
            export_dir = Path(tempfile.gettempdir()) / "math_grading_exports"
            export_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            if format_type == "json":
                file_path = export_dir / f"homework_{homework_id}_{timestamp}.json"
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(homework_data, f, ensure_ascii=False, indent=2)

            elif format_type == "txt":
                file_path = export_dir / f"homework_{homework_id}_{timestamp}.txt"
                with open(file_path, 'w', encoding='utf-8') as f:
                    homework = homework_data["homework"]
                    stats = homework_data["statistics"]

                    f.write(f"作业批改报告\n")
                    f.write(f"{'='*50}\n\n")
                    f.write(f"学生姓名: {homework['student_name']}\n")
                    f.write(f"年级: {homework['grade_level']}\n")
                    f.write(f"作业标题: {homework['title']}\n")
                    f.write(f"提交时间: {homework.get('submitted_at', 'N/A')}\n")
                    f.write(f"批改时间: {homework.get('graded_at', 'N/A')}\n\n")

                    f.write(f"统计信息:\n")
                    f.write(f"总题数: {stats['total_questions']}\n")
                    f.write(f"正确: {stats['correct_count']}\n")
                    f.write(f"错误: {stats['wrong_count']}\n")
                    f.write(f"正确率: {stats['accuracy_rate']:.1f}%\n")
                    f.write(f"得分: {stats['total_score']:.1f}/{stats['max_total_score']:.1f}\n\n")

                    f.write(f"详细结果:\n")
                    f.write(f"{'-'*50}\n")
                    for i, question in enumerate(homework['questions'], 1):
                        f.write(f"{i}. {question['question_text']}\n")
                        f.write(f"   学生答案: {question['student_answer']}\n")
                        f.write(f"   正确答案: {question['correct_answer']}\n")
                        f.write(f"   得分: {question['score']}/{question['max_score']}\n")
                        f.write(f"   反馈: {question['feedback']}\n\n")

            return str(file_path)

        except Exception as e:
            self.logger.error(f"导出作业结果失败: {e}")
            return None

class StudentHandler(BaseHandler):
    """学生处理器"""

    def list_students(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """获取学生列表"""
        try:
            with db_manager.get_session() as session:
                total = session.query(Student).count()
                students = session.query(Student).offset((page - 1) * per_page).limit(per_page).all()

                student_list = []
                for student in students:
                    homework_count = session.query(Homework).filter(Homework.student_id == student.id).count()
                    graded_count = session.query(Homework).filter(
                        Homework.student_id == student.id,
                        Homework.graded_at.isnot(None)
                    ).count()

                    student_data = {
                        "id": student.id,
                        "name": student.name,
                        "student_id": student.student_id,
                        "grade": student.grade,
                        "created_at": student.created_at.isoformat(),
                        "homework_count": homework_count,
                        "graded_count": graded_count
                    }
                    student_list.append(student_data)

                return {
                    "students": student_list,
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": total,
                        "pages": (total + per_page - 1) // per_page
                    }
                }

        except Exception as e:
            self.logger.error(f"获取学生列表失败: {e}")
            raise DatabaseError(f"获取学生列表失败: {e}")

    def create_student(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建学生"""
        try:
            name = data.get("name")
            student_id = data.get("student_id")
            grade = data.get("grade")

            if not all([name, student_id, grade]):
                raise ValueError("缺少必需的学生信息")

            student = db_manager.create_student(name, student_id, grade)

            return {
                "id": student.id,
                "name": student.name,
                "student_id": student.student_id,
                "grade": student.grade,
                "created_at": student.created_at.isoformat()
            }

        except Exception as e:
            self.logger.error(f"创建学生失败: {e}")
            raise DatabaseError(f"创建学生失败: {e}")

    def get_student(self, student_id: str) -> Optional[Dict[str, Any]]:
        """获取학생상세정보"""
        try:
            with db_manager.get_session() as session:
                student = session.query(Student).filter(Student.id == student_id).first()

                if not student:
                    return None

                # 统计信息
                homework_count = session.query(Homework).filter(Homework.student_id == student_id).count()
                graded_count = session.query(Homework).filter(
                    Homework.student_id == student_id,
                    Homework.graded_at.isnot(None)
                ).count()

                # 平均分
                avg_score_result = session.query(Homework).filter(
                    Homework.student_id == student_id,
                    Homework.graded_at.isnot(None)
                ).all()

                if avg_score_result:
                    total_score = sum(h.total_score for h in avg_score_result)
                    max_total_score = sum(h.max_score for h in avg_score_result)
                    avg_percentage = (total_score / max_total_score * 100) if max_total_score > 0 else 0
                else:
                    avg_percentage = 0

                return {
                    "id": student.id,
                    "name": student.name,
                    "student_id": student.student_id,
                    "grade": student.grade,
                    "created_at": student.created_at.isoformat(),
                    "statistics": {
                        "homework_count": homework_count,
                        "graded_count": graded_count,
                        "average_percentage": avg_percentage
                    }
                }

        except Exception as e:
            self.logger.error(f"获取学生详情失败: {e}")
            raise DatabaseError(f"获取学生详情失败: {e}")

    def get_student_homeworks(self, student_id: str) -> List[Dict[str, Any]]:
        """获取학생작업목록"""
        try:
            with db_manager.get_session() as session:
                homeworks = session.query(Homework).filter(Homework.student_id == student_id).all()

                homework_list = []
                for homework in homeworks:
                    homework_data = {
                        "id": homework.id,
                        "title": homework.title,
                        "grade_level": homework.grade_level,
                        "submitted_at": homework.submitted_at.isoformat() if homework.submitted_at else None,
                        "graded_at": homework.graded_at.isoformat() if homework.graded_at else None,
                        "total_score": homework.total_score,
                        "max_score": homework.max_score,
                        "status": "已批改" if homework.graded_at else "未批改"
                    }
                    homework_list.append(homework_data)

                return homework_list

        except Exception as e:
            self.logger.error(f"获取学生作业失败: {e}")
            raise DatabaseError(f"获取学生作业失败: {e}")

class GradingHandler(BaseHandler):
    """批改处理器"""

    def __init__(self):
        super().__init__()
        self.mcp_client = None
        self.grading_engine = None

    async def _ensure_initialized(self):
        """确保组件已初始化"""
        if not self.mcp_client:
            self.mcp_client = MCPClient()
            await self.mcp_client.connect()

        if not self.grading_engine:
            model_selector = ModelSelector()
            self.grading_engine = GradingEngine(self.mcp_client, model_selector)

    async def grade_homework(self, homework_id: str) -> Dict[str, Any]:
        """批改作业"""
        try:
            await self._ensure_initialized()

            # 获取作业信息
            with db_manager.get_session() as session:
                homework = session.query(Homework).filter(Homework.id == homework_id).first()

                if not homework:
                    raise ValueError("作业不存在")

                if not Path(homework.image_path).exists():
                    raise FileNotFoundError("作业图像文件不存在")

            # 执行批改
            results = await self.grading_engine.grade_homework(
                homework_id, homework.image_path, homework.grade_level
            )

            return results

        except Exception as e:
            self.logger.error(f"批改作业失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def generate_detailed_feedback(self, homework_id: str, question_id: str) -> Dict[str, Any]:
        """生成详细反馈"""
        try:
            await self._ensure_initialized()

            # 获取问题信息
            with db_manager.get_session() as session:
                question = session.query(Question).filter(Question.id == question_id).first()

                if not question:
                    raise ValueError("问题不存在")

            # 生成详细反馈
            feedback = await self.mcp_client.generate_detailed_feedback(
                question.question_text,
                question.student_answer,
                question.correct_answer
            )

            return {
                "success": True,
                "feedback": feedback,
                "question_id": question_id
            }

        except Exception as e:
            self.logger.error(f"生成详细反馈失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def generate_similar_problems(self, original_question: str, count: int = 3, difficulty: str = "same") -> Dict[str, Any]:
        """生成相似题目"""
        try:
            await self._ensure_initialized()

            problems = await self.mcp_client.generate_similar_problems(original_question, count)

            return {
                "success": True,
                "problems": problems,
                "count": len(problems)
            }

        except Exception as e:
            self.logger.error(f"生成相似题目失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def validate_expression(self, expression: str, expected_result: str = None) -> Dict[str, Any]:
        """验证数学表达式"""
        try:
            await self._ensure_initialized()

            result = await self.mcp_client.validate_math_expression(expression, expected_result)

            return result

        except Exception as e:
            self.logger.error(f"验证表达式失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

class StatisticsHandler(BaseHandler):
    """统计处理器"""

    def get_overview_statistics(self) -> Dict[str, Any]:
        """获取统计概览"""
        try:
            with db_manager.get_session() as session:
                # 基本统计
                total_students = session.query(Student).count()
                total_homeworks = session.query(Homework).count()
                graded_homeworks = session.query(Homework).filter(Homework.graded_at.isnot(None)).count()

                # 平均分统计
                graded_hw = session.query(Homework).filter(Homework.graded_at.isnot(None)).all()
                if graded_hw:
                    total_scores = sum(h.total_score for h in graded_hw)
                    max_scores = sum(h.max_score for h in graded_hw)
                    avg_percentage = (total_scores / max_scores * 100) if max_scores > 0 else 0
                else:
                    avg_percentage = 0

                # 年级分布
                grade_distribution = {}
                students_by_grade = session.query(Student.grade).all()
                for (grade,) in students_by_grade:
                    grade_distribution[grade] = grade_distribution.get(grade, 0) + 1

                return {
                    "total_students": total_students,
                    "total_homeworks": total_homeworks,
                    "graded_homeworks": graded_homeworks,
                    "pending_homeworks": total_homeworks - graded_homeworks,
                    "average_score_percentage": avg_percentage,
                    "grade_distribution": grade_distribution
                }

        except Exception as e:
            self.logger.error(f"获取统计概览失败: {e}")
            raise DatabaseError(f"获取统计概览失败: {e}")

    def get_student_statistics(self, student_id: str) -> Dict[str, Any]:
        """获取学生统计"""
        try:
            with db_manager.get_session() as session:
                student = session.query(Student).filter(Student.id == student_id).first()

                if not student:
                    raise ValueError("学生不存在")

                homeworks = session.query(Homework).filter(Homework.student_id == student_id).all()
                graded_homeworks = [h for h in homeworks if h.graded_at]

                if graded_homeworks:
                    scores = [h.total_score / h.max_score * 100 for h in graded_homeworks if h.max_score > 0]
                    avg_score = sum(scores) / len(scores) if scores else 0

                    # 进步趋势
                    score_trend = []
                    for homework in sorted(graded_homeworks, key=lambda x: x.graded_at):
                        percentage = (homework.total_score / homework.max_score * 100) if homework.max_score > 0 else 0
                        score_trend.append({
                            "date": homework.graded_at.isoformat(),
                            "score": percentage,
                            "title": homework.title
                        })
                else:
                    avg_score = 0
                    score_trend = []

                return {
                    "student_info": {
                        "name": student.name,
                        "grade": student.grade
                    },
                    "statistics": {
                        "total_homeworks": len(homeworks),
                        "graded_homeworks": len(graded_homeworks),
                        "average_score": avg_score,
                        "score_trend": score_trend
                    }
                }

        except Exception as e:
            self.logger.error(f"获取学生统计失败: {e}")
            raise DatabaseError(f"获取学生统计失败: {e}")

    def get_grade_statistics(self, grade_level: str) -> Dict[str, Any]:
        """获取年级统计"""
        try:
            with db_manager.get_session() as session:
                students = session.query(Student).filter(Student.grade == grade_level).all()

                if not students:
                    return {
                        "grade_level": grade_level,
                        "student_count": 0,
                        "statistics": {}
                    }

                student_ids = [s.id for s in students]
                homeworks = session.query(Homework).filter(Homework.student_id.in_(student_ids)).all()
                graded_homeworks = [h for h in homeworks if h.graded_at]

                if graded_homeworks:
                    scores = [h.total_score / h.max_score * 100 for h in graded_homeworks if h.max_score > 0]
                    avg_score = sum(scores) / len(scores) if scores else 0

                    # 分数分布
                    score_ranges = {"90-100": 0, "80-89": 0, "70-79": 0, "60-69": 0, "0-59": 0}
                    for score in scores:
                        if score >= 90:
                            score_ranges["90-100"] += 1
                        elif score >= 80:
                            score_ranges["80-89"] += 1
                        elif score >= 70:
                            score_ranges["70-79"] += 1
                        elif score >= 60:
                            score_ranges["60-69"] += 1
                        else:
                            score_ranges["0-59"] += 1
                else:
                    avg_score = 0
                    score_ranges = {"90-100": 0, "80-89": 0, "70-79": 0, "60-69": 0, "0-59": 0}

                return {
                    "grade_level": grade_level,
                    "student_count": len(students),
                    "statistics": {
                        "total_homeworks": len(homeworks),
                        "graded_homeworks": len(graded_homeworks),
                        "average_score": avg_score,
                        "score_distribution": score_ranges
                    }
                }

        except Exception as e:
            self.logger.error(f"获取年级统计失败: {e}")
            raise DatabaseError(f"获取年级统计失败: {e}")