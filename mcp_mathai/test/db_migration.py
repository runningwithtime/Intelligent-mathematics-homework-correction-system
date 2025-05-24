# ===============================
# db_migration.py - 数据库Schema修复
# ===============================
import sqlite3
import sys
from pathlib import Path

def check_and_fix_database():
    """检查并修复数据库Schema"""
    db_path = "math_grading.db"  # 根据你的实际数据库路径调整

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查students表结构
        cursor.execute("PRAGMA table_info(students)")
        columns = [column[1] for column in cursor.fetchall()]

        print(f"当前students表的列: {columns}")

        # 检查是否缺少class_name列
        if 'class_name' not in columns:
            print("缺少class_name列，正在添加...")
            cursor.execute("ALTER TABLE students ADD COLUMN class_name TEXT")
            print("class_name列添加成功")

        # 检查是否缺少其他必要的列
        required_columns = {
            'student_id': 'TEXT',
            'name': 'TEXT',
            'grade': 'TEXT',
            'class_name': 'TEXT',
            'school': 'TEXT',
            'total_homeworks': 'INTEGER DEFAULT 0',
            'total_score': 'REAL DEFAULT 0.0',
            'average_score': 'REAL DEFAULT 0.0',
            'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }

        for col_name, col_type in required_columns.items():
            if col_name not in columns:
                print(f"添加缺失列: {col_name}")
                cursor.execute(f"ALTER TABLE students ADD COLUMN {col_name} {col_type}")

        # 提交更改
        conn.commit()
        print("数据库Schema修复完成")

        # 验证修复结果
        cursor.execute("PRAGMA table_info(students)")
        new_columns = [column[1] for column in cursor.fetchall()]
        print(f"修复后students表的列: {new_columns}")

        return True

    except Exception as e:
        print(f"数据库修复失败: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def create_missing_tables():
    """创建缺失的表"""
    db_path = "math_grading.db"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 创建students表（如果不存在）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT UNIQUE,
                name TEXT NOT NULL,
                grade TEXT,
                class_name TEXT,
                school TEXT,
                total_homeworks INTEGER DEFAULT 0,
                total_score REAL DEFAULT 0.0,
                average_score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建homeworks表（如果不存在）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS homeworks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                homework_id TEXT UNIQUE,
                student_id TEXT,
                image_path TEXT,
                grade_level TEXT,
                subject TEXT DEFAULT 'math',
                total_score REAL,
                feedback TEXT,
                suggestions TEXT,
                practice_problems TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
        """)

        # 创建grading_results表（如果不存在）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS grading_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                homework_id TEXT,
                question_number INTEGER,
                question_content TEXT,
                student_answer TEXT,
                correct_answer TEXT,
                is_correct BOOLEAN,
                score REAL,
                feedback TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (homework_id) REFERENCES homeworks (homework_id)
            )
        """)

        conn.commit()
        print("数据库表创建/验证完成")
        return True

    except Exception as e:
        print(f"创建数据库表失败: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("开始数据库Schema检查和修复...")

    # 创建缺失的表
    if create_missing_tables():
        print("✓ 数据库表检查完成")
    else:
        print("✗ 数据库表检查失败")
        sys.exit(1)

    # 修复Schema
    if check_and_fix_database():
        print("✓ 数据库Schema修复完成")
    else:
        print("✗ 数据库Schema修复失败")
        sys.exit(1)

    print("数据库准备就绪！")