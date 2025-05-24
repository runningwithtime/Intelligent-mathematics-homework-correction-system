# ===============================
# 在您的 data/database.py 文件中
# 修改数据库Session配置
# ===============================
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from config.settings import settings
from data.database import db_manager, logger
from data.models import Homework, Student
from utils.exceptions import MathGradingException


class DatabaseManager:
    def __init__(self):
        db_config = settings.database

        self.engine = create_engine(
            db_config["url"],
            echo=db_config.get("echo", False),
            pool_size=10,
            pool_recycle=3600
        )

        # 关键修复：添加 expire_on_commit=False
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,  # 这是关键！防止对象在commit后过期
            autoflush=True,
            autocommit=False
        )

        self.Session = scoped_session(self.SessionLocal)

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    def create_student(self, name: str, student_id: str, grade: str):
        """创建学生记录 - 修复版"""
        session = self.get_session()
        try:
            # 检查是否已存在
            existing = session.query(Student).filter_by(name=name).first()
            if existing:
                logger.info(f"学生已存在: {name}, ID: {existing.id}")
                return existing

            # 创建新学生
            student = Student(
                name=name,
                student_id=student_id,
                grade=grade,
                created_at=datetime.now()
            )
            session.add(student)
            session.commit()

            logger.info(f"创建学生成功: {name}, ID: {student.id}")
            return student

        except Exception as e:
            session.rollback()
            logger.error(f"创建学生失败: {e}")
            raise e
        finally:
            session.close()

    def create_homework(self, student_id: int, title: str, grade_level: str, image_path: str):
        """创建作业记录 - 修复版"""
        session = self.get_session()
        try:
            homework = Homework(
                student_id=student_id,
                title=title,
                grade_level=grade_level,
                image_path=image_path,
                created_at=datetime.now()
            )
            session.add(homework)
            session.commit()

            logger.info(f"创建作业成功: {title}, ID: {homework.id}")
            return homework

        except Exception as e:
            session.rollback()
            logger.error(f"创建作业失败: {e}")
            raise e
        finally:
            session.close()


# ===============================
# 或者，如果您想要更优雅的解决方案
# 使用上下文管理器
# ===============================

from contextlib import contextmanager

class DatabaseManager:
    def __init__(self):
        db_config = settings.database

        self.engine = create_engine(
            db_config["url"],
            echo=db_config.get("echo", False)
        )

        self.SessionLocal = sessionmaker(
            bind=self.engine,
            expire_on_commit=False  # 关键配置
        )

    @contextmanager
    def get_db_session(self):
        """数据库会话上下文管理器"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def create_student_and_homework(self, student_name: str, grade_level: str,
                                    homework_title: str, image_path: str):
        """在单个session中创建学生和作业 - 最佳实践"""
        with self.get_db_session() as session:
            # 检查学生是否存在
            student = session.query(Student).filter_by(name=student_name).first()
            if not student:
                student = Student(
                    name=student_name,
                    student_id=f"STU_{hash(student_name) % 10000:04d}",
                    grade=grade_level,
                    created_at=datetime.now()
                )
                session.add(student)
                session.flush()  # 获取ID但不提交

            # 创建作业
            homework = Homework(
                student_id=student.id,  # 现在这里不会出错
                title=homework_title,
                grade_level=grade_level,
                image_path=image_path,
                created_at=datetime.now()
            )
            session.add(homework)

            # 返回时对象仍然有效，因为expire_on_commit=False
            return student, homework


# ===============================
# 在gui.py中使用新的方法
# ===============================

async def _async_grade_homework(self) -> Dict[str, Any]:
    """异步批改作业 - 使用新的数据库方法"""
    try:
        # MCP客户端初始化代码保持不变...

        student_name = self.student_name_var.get().strip()
        grade_level = self.grade_var.get()

        try:
            # 使用新的方法，一次性处理学生和作业创建
            student, homework = db_manager.create_student_and_homework(
                student_name=student_name,
                grade_level=grade_level,
                homework_title=f"{Path(self.current_image_path).stem}",
                image_path=self.current_image_path
            )

            # 现在访问ID不会有问题
            logger.info(f"学生ID: {student.id}, 作业ID: {homework.id}")

            # 执行批改
            results = await self.grading_engine.grade_homework(
                homework.id, self.current_image_path, grade_level
            )

            return results

        except Exception as db_error:
            logger.error(f"数据库操作失败: {db_error}")
            return await self._simple_grade_homework()

    except Exception as e:
        logger.error(f"异步批改失败: {e}", exc_info=True)
        raise MathGradingException(f"批改过程出现错误: {str(e)}")