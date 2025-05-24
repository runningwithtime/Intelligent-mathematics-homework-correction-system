# ===============================
# data/database.py - 数据库操作
# ===============================
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
import logging

from config.settings import settings
from data.models import Base, Student, Homework, Question

logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库管理器"""

    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, echo=settings.get("database.echo", False))
        # self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,  # 关键修复！
            autoflush=True,
            autocommit=False
        )

        # 创建表
        Base.metadata.create_all(bind=self.engine)
        logger.info("数据库初始化完成")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """获取数据库会话"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            session.close()

    def create_student(self, name: str, student_id: str, grade: str) -> Student:
        """创建学生"""
        with self.get_session() as session:
            student = Student(name=name, student_id=student_id, grade=grade)
            session.add(student)
            session.flush()
            return student

    def create_homework(self, student_id: str, title: str, grade_level: str, image_path: str) -> Homework:
        """创建作业"""
        with self.get_session() as session:
            homework = Homework(
                student_id=student_id,
                title=title,
                grade_level=grade_level,
                image_path=image_path
            )
            session.add(homework)
            session.flush()
            return homework

    def save_grading_results(self, homework_id: str, results: list, session_data: dict):
        """保存批改结果"""
        with self.get_session() as session:
            # 更新作业信息
            homework = session.query(Homework).filter(Homework.id == homework_id).first()
            if homework:
                homework.graded_at = datetime.utcnow()
                homework.total_score = session_data.get('total_score', 0)
                homework.max_score = session_data.get('max_score', 0)

            # 保存题目结果
            for i, result in enumerate(results):
                question = Question(
                    homework_id=homework_id,
                    question_number=i + 1,
                    question_text=result.get('question_text', ''),
                    student_answer=result.get('student_answer', ''),
                    correct_answer=result.get('correct_answer', ''),
                    score=result.get('score', 0),
                    max_score=result.get('max_score', 10),
                    is_correct=result.get('is_correct', False),
                    feedback=result.get('feedback', '')
                )
                session.add(question)

# 全局数据库实例
db_manager = DatabaseManager(settings.get("database.url"))