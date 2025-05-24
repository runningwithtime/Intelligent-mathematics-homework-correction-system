# ===============================
# data/models.py - 完整的数据库模型设计
# ===============================

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime,
    ForeignKey, JSON, Enum, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from datetime import datetime
import enum

Base = declarative_base()

# ===============================
# 枚举类型定义
# ===============================

class GradeLevel(enum.Enum):
    """年级枚举"""
    GRADE_7 = "初一"
    GRADE_8 = "初二"
    GRADE_9 = "初三"
    GRADE_10 = "高一"
    GRADE_11 = "高二"
    GRADE_12 = "高三"

class HomeworkStatus(enum.Enum):
    """作业状态"""
    PENDING = "待批改"
    PROCESSING = "批改中"
    COMPLETED = "已完成"
    FAILED = "批改失败"

class QuestionType(enum.Enum):
    """题目类型"""
    MULTIPLE_CHOICE = "选择题"
    FILL_BLANK = "填空题"
    CALCULATION = "计算题"
    PROOF = "证明题"
    APPLICATION = "应用题"
    GRAPH = "图形题"

class DifficultyLevel(enum.Enum):
    """难度等级"""
    EASY = "简单"
    MEDIUM = "中等"
    HARD = "困难"

# ===============================
# 主要数据表
# ===============================

class Student(Base):
    """学生表"""
    __tablename__ = 'students'

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(50), unique=True, nullable=False, comment="学号")
    name = Column(String(100), nullable=False, comment="姓名")
    grade = Column(Enum(GradeLevel), nullable=False, comment="年级")
    class_name = Column(String(50), comment="班级")
    school = Column(String(200), comment="学校")

    # 统计信息
    total_homeworks = Column(Integer, default=0, comment="总作业数")
    total_score = Column(Float, default=0.0, comment="总得分")
    average_score = Column(Float, default=0.0, comment="平均分")

    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    homeworks = relationship("Homework", back_populates="student", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Student(id={self.id}, name='{self.name}', grade='{self.grade.value}')>"

class Homework(Base):
    """作业表"""
    __tablename__ = 'homeworks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)

    title = Column(String(200), nullable=False, comment="作业标题")
    description = Column(Text, comment="作业描述")
    grade_level = Column(Enum(GradeLevel), nullable=False, comment="年级")
    subject = Column(String(50), default="数学", comment="科目")

    # 图像信息
    image_path = Column(String(500), nullable=False, comment="原始图像路径")
    image_size = Column(String(50), comment="图像尺寸")
    image_format = Column(String(10), comment="图像格式")

    # 批改状态
    status = Column(Enum(HomeworkStatus), default=HomeworkStatus.PENDING, comment="批改状态")

    # 分数统计
    total_questions = Column(Integer, default=0, comment="总题目数")
    correct_questions = Column(Integer, default=0, comment="正确题目数")
    total_score = Column(Float, default=0.0, comment="总得分")
    max_possible_score = Column(Float, default=0.0, comment="满分")
    accuracy_rate = Column(Float, default=0.0, comment="正确率")
    score_percentage = Column(Float, default=0.0, comment="得分率")

    # 处理信息
    processing_time = Column(Float, comment="处理时间(秒)")
    processed_at = Column(DateTime, comment="批改完成时间")
    error_message = Column(Text, comment="错误信息")

    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    student = relationship("Student", back_populates="homeworks")
    questions = relationship("Question", back_populates="homework", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Homework(id={self.id}, title='{self.title}', status='{self.status.value}')>"

class Question(Base):
    """题目表"""
    __tablename__ = 'questions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    homework_id = Column(Integer, ForeignKey('homeworks.id'), nullable=False)

    # 题目信息
    question_number = Column(Integer, comment="题目序号")
    question_text = Column(Text, comment="题目内容")
    question_type = Column(Enum(QuestionType), comment="题目类型")
    topic = Column(String(100), comment="知识点")
    difficulty = Column(Enum(DifficultyLevel), comment="难度等级")

    # 答案信息
    student_answer = Column(Text, comment="学生答案")
    correct_answer = Column(Text, comment="正确答案")
    is_correct = Column(Boolean, default=False, comment="是否正确")

    # 分数
    score = Column(Float, default=0.0, comment="得分")
    max_score = Column(Float, default=10.0, comment="满分")

    # 反馈
    initial_feedback = Column(Text, comment="初始反馈")
    enhanced_feedback = Column(Text, comment="详细反馈")

    # 识别信息
    ocr_confidence = Column(Float, comment="OCR识别置信度")
    image_region = Column(JSON, comment="图像区域坐标")

    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    homework = relationship("Homework", back_populates="questions")

    def __repr__(self):
        return f"<Question(id={self.id}, type='{self.question_type}', correct={self.is_correct})>"

class KnowledgePoint(Base):
    """知识点表"""
    __tablename__ = 'knowledge_points'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, comment="知识点名称")
    category = Column(String(100), comment="知识点分类")
    grade_level = Column(Enum(GradeLevel), comment="适用年级")
    description = Column(Text, comment="知识点描述")

    # 统计信息
    total_questions = Column(Integer, default=0, comment="总题目数")
    correct_count = Column(Integer, default=0, comment="正确次数")
    error_rate = Column(Float, default=0.0, comment="错误率")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    def __repr__(self):
        return f"<KnowledgePoint(name='{self.name}', category='{self.category}')>"

class GradingSession(Base):
    """批改会话表"""
    __tablename__ = 'grading_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), unique=True, nullable=False, comment="会话ID")

    # 会话信息
    start_time = Column(DateTime, default=datetime.now, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    duration = Column(Float, comment="持续时间(秒)")

    # 处理统计
    total_homeworks = Column(Integer, default=0, comment="处理作业数")
    successful_count = Column(Integer, default=0, comment="成功数量")
    failed_count = Column(Integer, default=0, comment="失败数量")

    # 模型信息
    model_name = Column(String(100), comment="使用的模型")
    model_version = Column(String(50), comment="模型版本")

    # 系统信息
    system_mode = Column(String(50), comment="系统模式")  # normal, offline, simplified
    error_logs = Column(JSON, comment="错误日志")

    def __repr__(self):
        return f"<GradingSession(id='{self.session_id}', homeworks={self.total_homeworks})>"

class SystemLog(Base):
    """系统日志表"""
    __tablename__ = 'system_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 日志信息
    level = Column(String(20), nullable=False, comment="日志级别")  # INFO, WARNING, ERROR
    message = Column(Text, nullable=False, comment="日志消息")
    module = Column(String(100), comment="模块名称")
    function = Column(String(100), comment="函数名称")

    # 关联信息
    homework_id = Column(Integer, ForeignKey('homeworks.id'), comment="关联作业ID")
    session_id = Column(String(100), comment="会话ID")

    # 额外数据
    extra_data = Column(JSON, comment="额外数据")
    stack_trace = Column(Text, comment="错误堆栈")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    def __repr__(self):
        return f"<SystemLog(level='{self.level}', module='{self.module}')>"

class UserSettings(Base):
    """用户设置表"""
    __tablename__ = 'user_settings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), unique=True, nullable=False, comment="用户ID")

    # 界面设置
    theme = Column(String(50), default="default", comment="界面主题")
    language = Column(String(10), default="zh", comment="语言设置")

    # 批改设置
    default_grade = Column(Enum(GradeLevel), comment="默认年级")
    auto_save = Column(Boolean, default=True, comment="自动保存")
    show_detailed_feedback = Column(Boolean, default=True, comment="显示详细反馈")

    # 模型设置
    preferred_model = Column(String(100), comment="首选模型")
    processing_timeout = Column(Integer, default=300, comment="处理超时时间")

    # JSON格式的其他设置
    custom_settings = Column(JSON, comment="自定义设置")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<UserSettings(user_id='{self.user_id}', theme='{self.theme}')>"

# ===============================
# 索引定义
# ===============================

# 学生表索引
Index('idx_student_id', Student.student_id)
Index('idx_student_name', Student.name)
Index('idx_student_grade', Student.grade)

# 作业表索引
Index('idx_homework_student', Homework.student_id)
Index('idx_homework_status', Homework.status)
Index('idx_homework_created', Homework.created_at)
Index('idx_homework_grade', Homework.grade_level)

# 题目表索引
Index('idx_question_homework', Question.homework_id)
Index('idx_question_type', Question.question_type)
Index('idx_question_topic', Question.topic)
Index('idx_question_correct', Question.is_correct)

# 日志表索引
Index('idx_log_level', SystemLog.level)
Index('idx_log_module', SystemLog.module)
Index('idx_log_created', SystemLog.created_at)
Index('idx_log_homework', SystemLog.homework_id)

# ===============================
# 数据库初始化和管理
# ===============================

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import settings

class DatabaseManager:
    """数据库管理器"""

    def __init__(self):
        self.engine = create_engine(
            settings.database["url"],
            echo=settings.database.get("echo", False),
            pool_size=20,
            pool_recycle=3600
        )

        self.SessionLocal = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,  # 重要：防止对象过期
            autoflush=True,
            autocommit=False
        )

    def create_tables(self):
        """创建所有表"""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self):
        """删除所有表"""
        Base.metadata.drop_all(bind=self.engine)

    def get_session(self):
        """获取数据库会话"""
        return self.SessionLocal()

    def init_default_data(self):
        """初始化默认数据"""
        session = self.get_session()
        try:
            # 初始化知识点数据
            default_knowledge_points = [
                ("整数运算", "基础运算", GradeLevel.GRADE_7),
                ("分数运算", "基础运算", GradeLevel.GRADE_7),
                ("小数运算", "基础运算", GradeLevel.GRADE_7),
                ("代数表达式", "代数", GradeLevel.GRADE_8),
                ("方程求解", "代数", GradeLevel.GRADE_8),
                ("几何图形", "几何", GradeLevel.GRADE_8),
                ("函数概念", "函数", GradeLevel.GRADE_9),
                ("二次函数", "函数", GradeLevel.GRADE_9),
                ("三角函数", "三角", GradeLevel.GRADE_10),
                ("立体几何", "几何", GradeLevel.GRADE_11),
                ("导数应用", "微积分", GradeLevel.GRADE_12),
            ]

            for name, category, grade in default_knowledge_points:
                existing = session.query(KnowledgePoint).filter_by(name=name).first()
                if not existing:
                    kp = KnowledgePoint(
                        name=name,
                        category=category,
                        grade_level=grade,
                        description=f"{category}相关的{name}知识点"
                    )
                    session.add(kp)

            session.commit()
            print("默认数据初始化完成")

        except Exception as e:
            session.rollback()
            print(f"初始化默认数据失败: {e}")
        finally:
            session.close()

# 全局数据库管理器实例
db_manager = DatabaseManager()

# ===============================
# 数据库操作辅助函数
# ===============================

def create_student(name: str, student_id: str, grade: GradeLevel,
                   class_name: str = None, school: str = None):
    """创建学生记录"""
    session = db_manager.get_session()
    try:
        # 检查是否已存在
        existing = session.query(Student).filter_by(student_id=student_id).first()
        if existing:
            return existing

        student = Student(
            name=name,
            student_id=student_id,
            grade=grade,
            class_name=class_name,
            school=school
        )
        session.add(student)
        session.commit()
        return student

    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def create_homework_with_questions(student_id: int, title: str,
                                   image_path: str, questions_data: list):
    """创建作业及其题目"""
    session = db_manager.get_session()
    try:
        # 创建作业
        homework = Homework(
            student_id=student_id,
            title=title,
            image_path=image_path,
            status=HomeworkStatus.PROCESSING
        )
        session.add(homework)
        session.flush()  # 获取homework.id

        # 创建题目
        for i, q_data in enumerate(questions_data):
            question = Question(
                homework_id=homework.id,
                question_number=i + 1,
                question_text=q_data.get('question_text'),
                question_type=q_data.get('question_type'),
                student_answer=q_data.get('student_answer'),
                correct_answer=q_data.get('correct_answer'),
                is_correct=q_data.get('is_correct', False),
                score=q_data.get('score', 0),
                max_score=q_data.get('max_score', 10),
                topic=q_data.get('topic'),
                difficulty=q_data.get('difficulty'),
                initial_feedback=q_data.get('initial_feedback'),
                enhanced_feedback=q_data.get('enhanced_feedback')
            )
            session.add(question)

        # 更新作业统计
        homework.total_questions = len(questions_data)
        homework.correct_questions = sum(1 for q in questions_data if q.get('is_correct', False))
        homework.total_score = sum(q.get('score', 0) for q in questions_data)
        homework.max_possible_score = sum(q.get('max_score', 10) for q in questions_data)
        homework.accuracy_rate = homework.correct_questions / homework.total_questions * 100 if homework.total_questions > 0 else 0
        homework.score_percentage = homework.total_score / homework.max_possible_score * 100 if homework.max_possible_score > 0 else 0
        homework.status = HomeworkStatus.COMPLETED
        homework.processed_at = datetime.now()

        session.commit()
        return homework

    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    # 创建表和初始化数据
    db_manager.create_tables()
    db_manager.init_default_data()
    print("数据库初始化完成！")