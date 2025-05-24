# ===============================
# frontend/web.py - Web界面
# ===============================
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit
import os
import asyncio
import logging
from pathlib import Path
from werkzeug.utils import secure_filename
import json
from datetime import datetime

from ..config.settings import settings
from ..api.handlers import HomeworkHandler, StudentHandler, GradingHandler, StatisticsHandler
from ..utils.logger import setup_logger

logger = setup_logger("web")

def create_web_app():
    """创建Web应用"""
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    app.config['SECRET_KEY'] = 'math-grading-web-secret'
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

    # 创建上传目录
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # 初始化SocketIO用于实时更新
    socketio = SocketIO(app, cors_allowed_origins="*")

    # 初始化处理器
    homework_handler = HomeworkHandler()
    student_handler = StudentHandler()
    grading_handler = GradingHandler()
    statistics_handler = StatisticsHandler()

    # 启动异步事件循环
    loop = asyncio.new_event_loop()

    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    import threading
    threading.Thread(target=run_loop, daemon=True).start()

    # ============ 路由定义 ============

    @app.route('/')
    def index():
        """首页"""
        try:
            # 获取统计概览
            stats = statistics_handler.get_overview_statistics()

            # 获取最近的作业
            recent_homeworks = homework_handler.list_homeworks(page=1, per_page=5)

            return render_template('index.html',
                                   stats=stats,
                                   recent_homeworks=recent_homeworks.get('homeworks', []))
        except Exception as e:
            logger.error(f"首页加载失败: {e}")
            flash(f"数据加载失败: {e}", 'error')
            return render_template('index.html', stats={}, recent_homeworks=[])

    @app.route('/upload')
    def upload_page():
        """上传页面"""
        return render_template('upload.html')

    @app.route('/upload', methods=['POST'])
    def upload_homework():
        """处理作业上传"""
        try:
            if 'homework_file' not in request.files:
                flash('请选择要上传的文件', 'error')
                return redirect(url_for('upload_page'))

            file = request.files['homework_file']
            student_name = request.form.get('student_name', '').strip()
            grade_level = request.form.get('grade_level', '高一')

            if file.filename == '':
                flash('请选择要上传的文件', 'error')
                return redirect(url_for('upload_page'))

            if not student_name:
                flash('请输入学生姓名', 'error')
                return redirect(url_for('upload_page'))

            # 检查文件类型
            allowed_extensions = {'png', 'jpg', 'jpeg', 'bmp'}
            file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

            if file_ext not in allowed_extensions:
                flash('不支持的文件格式，请上传PNG、JPG或BMP格式的图片', 'error')
                return redirect(url_for('upload_page'))

            # 保存文件
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # 异步处理上传
            future = asyncio.run_coroutine_threadsafe(
                _async_handle_upload(file_path, student_name, grade_level), loop
            )
            result = future.result(timeout=30)

            if result['success']:
                homework_id = result['homework_id']
                flash('文件上传成功！', 'success')
                return redirect(url_for('homework_detail', homework_id=homework_id))
            else:
                flash(f'上传失败: {result["error"]}', 'error')
                return redirect(url_for('upload_page'))

        except Exception as e:
            logger.error(f"文件上传失败: {e}")
            flash(f'上传失败: {e}', 'error')
            return redirect(url_for('upload_page'))

    @app.route('/homework')
    def homework_list():
        """作业列表页面"""
        try:
            page = request.args.get('page', 1, type=int)
            status = request.args.get('status', 'all')

            homeworks_data = homework_handler.list_homeworks(
                page=page,
                per_page=10,
                status=status if status != 'all' else None
            )

            return render_template('homework_list.html',
                                   homeworks=homeworks_data.get('homeworks', []),
                                   pagination=homeworks_data.get('pagination', {}),
                                   current_status=status)
        except Exception as e:
            logger.error(f"作业列表加载失败: {e}")
            flash(f"数据加载失败: {e}", 'error')
            return render_template('homework_list.html', homeworks=[], pagination={})

    @app.route('/homework/<homework_id>')
    def homework_detail(homework_id):
        """作业详情页面"""
        try:
            homework_data = homework_handler.get_homework_results(homework_id)

            if not homework_data:
                flash('作业不存在', 'error')
                return redirect(url_for('homework_list'))

            return render_template('homework_detail.html',
                                   homework=homework_data.get('homework'),
                                   statistics=homework_data.get('statistics'))
        except Exception as e:
            logger.error(f"作业详情加载失败: {e}")
            flash(f"数据加载失败: {e}", 'error')
            return redirect(url_for('homework_list'))

    @app.route('/homework/<homework_id>/grade', methods=['POST'])
    def grade_homework_web(homework_id):
        """Web界面批改作业"""
        try:
            # 异步执行批改
            future = asyncio.run_coroutine_threadsafe(
                grading_handler.grade_homework(homework_id), loop
            )

            # 发送实时更新
            socketio.emit('grading_started', {'homework_id': homework_id})

            result = future.result(timeout=300)  # 5分钟超时

            if result.get('success'):
                flash('批改完成！', 'success')
                socketio.emit('grading_completed', {
                    'homework_id': homework_id,
                    'result': result
                })
            else:
                flash(f'批改失败: {result.get("error")}', 'error')
                socketio.emit('grading_failed', {
                    'homework_id': homework_id,
                    'error': result.get('error')
                })

            return redirect(url_for('homework_detail', homework_id=homework_id))

        except asyncio.TimeoutError:
            flash('批改超时，请稍后重试', 'error')
            socketio.emit('grading_timeout', {'homework_id': homework_id})
            return redirect(url_for('homework_detail', homework_id=homework_id))
        except Exception as e:
            logger.error(f"批改失败: {e}")
            flash(f'批改失败: {e}', 'error')
            return redirect(url_for('homework_detail', homework_id=homework_id))

    @app.route('/students')
    def student_list():
        """学生列表页面"""
        try:
            page = request.args.get('page', 1, type=int)
            students_data = student_handler.list_students(page=page, per_page=15)

            return render_template('student_list.html',
                                   students=students_data.get('students', []),
                                   pagination=students_data.get('pagination', {}))
        except Exception as e:
            logger.error(f"学生列表加载失败: {e}")
            flash(f"数据加载失败: {e}", 'error')
            return render_template('student_list.html', students=[], pagination={})

    @app.route('/student/<student_id>')
    def student_detail(student_id):
        """学生详情页面"""
        try:
            student = student_handler.get_student(student_id)
            if not student:
                flash('学生不存在', 'error')
                return redirect(url_for('student_list'))

            homeworks = student_handler.get_student_homeworks(student_id)
            stats = statistics_handler.get_student_statistics(student_id)

            return render_template('student_detail.html',
                                   student=student,
                                   homeworks=homeworks,
                                   statistics=stats)
        except Exception as e:
            logger.error(f"学生详情加载失败: {e}")
            flash(f"数据加载失败: {e}", 'error')
            return redirect(url_for('student_list'))

    @app.route('/statistics')
    def statistics_page():
        """统计页面"""
        try:
            overview = statistics_handler.get_overview_statistics()

            # 获取各年级统计
            grades = ['初一', '初二', '初三', '高一', '高二', '高三']
            grade_stats = {}
            for grade in grades:
                try:
                    grade_stats[grade] = statistics_handler.get_grade_statistics(grade)
                except:
                    grade_stats[grade] = {"statistics": {}}

            return render_template('statistics.html',
                                   overview=overview,
                                   grade_stats=grade_stats)
        except Exception as e:
            logger.error(f"统计页面加载失败: {e}")
            flash(f"数据加载失败: {e}", 'error')
            return render_template('statistics.html', overview={}, grade_stats={})

    @app.route('/api/similar-problems', methods=['POST'])
    def generate_similar_problems_web():
        """生成相似题目API"""
        try:
            data = request.get_json()
            original_question = data.get('original_question')
            count = data.get('count', 3)

            if not original_question:
                return jsonify({"error": "缺少原始题目"}), 400

            future = asyncio.run_coroutine_threadsafe(
                grading_handler.generate_similar_problems(original_question, count), loop
            )
            result = future.result(timeout=60)

            return jsonify(result)

        except Exception as e:
            logger.error(f"生成相似题目失败: {e}")
            return jsonify({"error": str(e)}), 500

    # ============ WebSocket事件处理 ============

    @socketio.on('connect')
    def handle_connect():
        """客户端连接"""
        emit('connected', {'message': '已连接到服务器'})
        logger.info(f"客户端连接: {request.sid}")

    @socketio.on('disconnect')
    def handle_disconnect():
        """客户端断开连接"""
        logger.info(f"客户端断开连接: {request.sid}")

    @socketio.on('join_homework')
    def handle_join_homework(data):
        """加入作业房间，接收实时更新"""
        homework_id = data.get('homework_id')
        if homework_id:
            session['homework_id'] = homework_id
            emit('joined_homework', {'homework_id': homework_id})

    # ============ 辅助函数 ============

    async def _async_handle_upload(file_path, student_name, grade_level):
        """异步处理文件上传"""
        from ..utils.image_processor import ImageProcessor
        from ..data.database import db_manager

        try:
            # 验证图像
            with open(file_path, 'rb') as f:
                image_data = f.read()

            validation_result = ImageProcessor.validate_image(image_data)
            if not validation_result["valid"]:
                return {"success": False, "error": f"图像验证失败: {validation_result['error']}"}

            # 创建学生和作业记录
            try:
                student = db_manager.create_student(
                    name=student_name,
                    student_id=f"STU_{hash(student_name) % 10000:04d}",
                    grade=grade_level
                )
            except:
                # 学生可能已存在
                with db_manager.get_session() as session:
                    from ..data.models import Student
                    student = session.query(Student).filter(Student.name == student_name).first()
                    if not student:
                        return {"success": False, "error": "创建学生记录失败"}

            homework = db_manager.create_homework(
                student_id=student.id,
                title=Path(file_path).name,
                grade_level=grade_level,
                image_path=file_path
            )

            return {
                "success": True,
                "homework_id": homework.id,
                "student_id": student.id
            }

        except Exception as e:
            logger.error(f"异步上传处理失败: {e}")
            return {"success": False, "error": str(e)}

    # ============ 错误处理器 ============

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f'服务器错误: {error}')
        return render_template('errors/500.html'), 500

    @app.errorhandler(413)
    def file_too_large(error):
        flash('文件过大，请选择小于16MB的文件', 'error')
        return redirect(url_for('upload_page'))

    # ============ 模板过滤器 ============

    @app.template_filter('datetime_format')
    def datetime_format(value, format='%Y-%m-%d %H:%M'):
        """格式化日期时间"""
        if isinstance(value, str):
            try:
                from datetime import datetime
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except:
                return value
        return value.strftime(format) if value else ''

    @app.template_filter('score_color')
    def score_color(score_percentage):
        """根据分数返回颜色类"""
        if score_percentage >= 90:
            return 'text-success'
        elif score_percentage >= 70:
            return 'text-warning'
        else:
            return 'text-danger'

    return app, socketio


# ============ HTML模板内容 ============

# 注意：以下是模板文件的内容，需要创建相应的templates目录和文件

TEMPLATES = {
    'base.html': '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}数学作业批改系统{% endblock %}</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <!-- Socket.io -->
    <script src="https://cdn.socket.io/4.5.0/socket.io.min.js"></script>
    
    <style>
        .sidebar {
            min-height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .sidebar .nav-link {
            color: rgba(255,255,255,0.8);
            margin: 0.25rem 0;
            border-radius: 0.5rem;
        }
        .sidebar .nav-link:hover, .sidebar .nav-link.active {
            color: white;
            background: rgba(255,255,255,0.1);
        }
        .main-content {
            background: #f8f9fa;
            min-height: 100vh;
        }
        .card {
            border: none;
            box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,0.075);
        }
        .stats-card {
            background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
            color: white;
        }
        .upload-area {
            border: 2px dashed #dee2e6;
            border-radius: 1rem;
            padding: 3rem;
            text-align: center;
            transition: all 0.3s ease;
        }
        .upload-area:hover {
            border-color: #6c757d;
            background: #f8f9fa;
        }
        .progress-container {
            display: none;
        }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <!-- 侧边栏 -->
            <nav class="col-md-3 col-lg-2 d-md-block sidebar collapse">
                <div class="position-sticky pt-3">
                    <div class="text-center mb-4">
                        <h4><i class="fas fa-calculator"></i> 数学批改系统</h4>
                    </div>
                    
                    <ul class="nav flex-column">
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('index') }}">
                                <i class="fas fa-home"></i> 首页
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('upload_page') }}">
                                <i class="fas fa-upload"></i> 上传作业
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('homework_list') }}">
                                <i class="fas fa-file-alt"></i> 作业管理
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('student_list') }}">
                                <i class="fas fa-users"></i> 学生管理
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('statistics_page') }}">
                                <i class="fas fa-chart-bar"></i> 统计报告
                            </a>
                        </li>
                    </ul>
                </div>
            </nav>
            
            <!-- 主内容区 -->
            <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4 main-content">
                <div class="pt-3 pb-2 mb-3">
                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                            {% for category, message in messages %}
                                <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show" role="alert">
                                    {{ message }}
                                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                </div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    
                    {% block content %}{% endblock %}
                </div>
            </main>
        </div>
    </div>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    
    <script>
        // Socket.io连接
        var socket = io();
        
        socket.on('connect', function() {
            console.log('已连接到服务器');
        });
        
        socket.on('grading_started', function(data) {
            showGradingProgress('批改已开始...');
        });
        
        socket.on('grading_completed', function(data) {
            hideGradingProgress();
            location.reload();
        });
        
        socket.on('grading_failed', function(data) {
            hideGradingProgress();
            alert('批改失败: ' + data.error);
        });
        
        function showGradingProgress(message) {
            $('.progress-container').show();
            $('.progress-message').text(message);
        }
        
        function hideGradingProgress() {
            $('.progress-container').hide();
        }
    </script>
    
    {% block scripts %}{% endblock %}
</body>
</html>
    ''',

    'index.html': '''
{% extends "base.html" %}

{% block title %}首页 - 数学作业批改系统{% endblock %}

{% block content %}
<div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pb-2 mb-3 border-bottom">
    <h1 class="h2">系统概览</h1>
</div>

<!-- 统计卡片 -->
<div class="row mb-4">
    <div class="col-md-3 mb-3">
        <div class="card stats-card">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <h4>{{ stats.get('total_students', 0) }}</h4>
                        <p class="mb-0">学生总数</p>
                    </div>
                    <div class="align-self-center">
                        <i class="fas fa-users fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-3 mb-3">
        <div class="card stats-card">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <h4>{{ stats.get('total_homeworks', 0) }}</h4>
                        <p class="mb-0">作业总数</p>
                    </div>
                    <div class="align-self-center">
                        <i class="fas fa-file-alt fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-3 mb-3">
        <div class="card stats-card">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <h4>{{ stats.get('graded_homeworks', 0) }}</h4>
                        <p class="mb-0">已批改</p>
                    </div>
                    <div class="align-self-center">
                        <i class="fas fa-check-circle fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-3 mb-3">
        <div class="card stats-card">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <h4>{{ "%.1f"|format(stats.get('average_score_percentage', 0)) }}%</h4>
                        <p class="mb-0">平均分</p>
                    </div>
                    <div class="align-self-center">
                        <i class="fas fa-percentage fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- 最近作业 -->
<div class="row">
    <div class="col-md-8">
        <div class="card">
            <div class="card-header">
                <h5><i class="fas fa-clock"></i> 最近作业</h5>
            </div>
            <div class="card-body">
                {% if recent_homeworks %}
                    <div class="table-responsive">
                        <table class="table table-hover">
                            <thead>
                                <tr>
                                    <th>学生</th>
                                    <th>作业</th>
                                    <th>年级</th>
                                    <th>状态</th>
                                    <th>提交时间</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for homework in recent_homeworks %}
                                <tr onclick="location.href='{{ url_for('homework_detail', homework_id=homework.id) }}'" style="cursor: pointer;">
                                    <td>{{ homework.student_name }}</td>
                                    <td>{{ homework.title }}</td>
                                    <td>{{ homework.grade_level }}</td>
                                    <td>
                                        <span class="badge bg-{{ 'success' if homework.status == '已批改' else 'warning' }}">
                                            {{ homework.status }}
                                        </span>
                                    </td>
                                    <td>{{ homework.submitted_at|datetime_format }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                {% else %}
                    <p class="text-center text-muted">暂无作业数据</p>
                {% endif %}
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card">
            <div class="card-header">
                <h5><i class="fas fa-chart-pie"></i> 年级分布</h5>
            </div>
            <div class="card-body">
                <canvas id="gradeChart" width="400" height="300"></canvas>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
    // 年级分布图表
    const gradeData = {{ stats.get('grade_distribution', {})|tojson }};
    
    if (Object.keys(gradeData).length > 0) {
        const ctx = document.getElementById('gradeChart').getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(gradeData),
                datasets: [{
                    data: Object.values(gradeData),
                    backgroundColor: [
                        '#FF6384', '#36A2EB', '#FFCE56', 
                        '#4BC0C0', '#9966FF', '#FF9F40'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }
</script>
{% endblock %}
    ''',

    'upload.html': '''
{% extends "base.html" %}

{% block title %}上传作业 - 数学作业批改系统{% endblock %}

{% block content %}
<div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pb-2 mb-3 border-bottom">
    <h1 class="h2">上传作业</h1>
</div>

<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card">
            <div class="card-body">
                <form method="POST" enctype="multipart/form-data" id="uploadForm">
                    <div class="mb-3">
                        <label for="student_name" class="form-label">学生姓名 <span class="text-danger">*</span></label>
                        <input type="text" class="form-control" id="student_name" name="student_name" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="grade_level" class="form-label">年级 <span class="text-danger">*</span></label>
                        <select class="form-select" id="grade_level" name="grade_level" required>
                            <option value="初一">初一</option>
                            <option value="初二">初二</option>
                            <option value="初三">初三</option>
                            <option value="高一" selected>高一</option>
                            <option value="高二">高二</option>
                            <option value="高三">高三</option>
                        </select>
                    </div>
                    
                    <div class="mb-3">
                        <label for="homework_file" class="form-label">作业图片 <span class="text-danger">*</span></label>
                        <div class="upload-area" id="uploadArea">
                            <i class="fas fa-cloud-upload-alt fa-3x mb-3 text-muted"></i>
                            <h5>点击或拖拽图片到此处</h5>
                            <p class="text-muted">支持 PNG、JPG、BMP 格式，文件大小不超过 16MB</p>
                            <input type="file" class="form-control" id="homework_file" name="homework_file" 
                                   accept=".png,.jpg,.jpeg,.bmp" required style="display: none;">
                        </div>
                        <div id="filePreview" class="mt-3" style="display: none;">
                            <img id="previewImage" class="img-fluid rounded" style="max-height: 300px;">
                            <div class="mt-2">
                                <span id="fileName"></span>
                                <button type="button" class="btn btn-sm btn-outline-danger ms-2" onclick="clearFile()">
                                    <i class="fas fa-times"></i> 移除
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <div class="d-grid gap-2">
                        <button type="submit" class="btn btn-primary btn-lg">
                            <i class="fas fa-upload"></i> 上传并开始批改
                        </button>
                    </div>
                </form>
                
                <div class="progress-container mt-3">
                    <div class="text-center">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">处理中...</span>
                        </div>
                        <p class="progress-message mt-2">正在上传文件...</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('homework_file');
    const filePreview = document.getElementById('filePreview');
    const previewImage = document.getElementById('previewImage');
    const fileName = document.getElementById('fileName');
    
    // 点击上传区域
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });
    
    // 拖拽上传
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = '#007bff';
        uploadArea.style.backgroundColor = '#f0f8ff';
    });
    
    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        resetUploadArea();
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        resetUploadArea();
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            handleFileSelect(files[0]);
        }
    });
    
    // 文件选择
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileSelect(file);
        }
    });
    
    function handleFileSelect(file) {
        // 验证文件类型
        const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/bmp'];
        if (!allowedTypes.includes(file.type)) {
            alert('请选择 PNG、JPG 或 BMP 格式的图片文件');
            return;
        }
        
        // 验证文件大小 (16MB)
        if (file.size > 16 * 1024 * 1024) {
            alert('文件大小不能超过 16MB');
            return;
        }
        
        // 显示预览
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImage.src = e.target.result;
            fileName.textContent = file.name;
            filePreview.style.display = 'block';
            uploadArea.style.display = 'none';
        };
        reader.readAsDataURL(file);
    }
    
    function clearFile() {
        fileInput.value = '';
        filePreview.style.display = 'none';
        uploadArea.style.display = 'block';
        resetUploadArea();
    }
    
    function resetUploadArea() {
        uploadArea.style.borderColor = '#dee2e6';
        uploadArea.style.backgroundColor = 'transparent';
    }
    
    // 表单提交
    document.getElementById('uploadForm').addEventListener('submit', function(e) {
        if (!fileInput.files.length) {
            e.preventDefault();
            alert('请选择要上传的文件');
            return;
        }
        
        document.querySelector('.progress-container').style.display = 'block';
        document.querySelector('button[type="submit"]').disabled = true;
    });
</script>
{% endblock %}
    '''
}

def create_template_files():
    """创建模板文件"""
    template_dir = Path("templates")
    template_dir.mkdir(exist_ok=True)

    for filename, content in TEMPLATES.items():
        template_path = template_dir / filename
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(content)

    print("Web模板文件创建完成！")

if __name__ == '__main__':
    # 创建模板文件
    create_template_files()

    # 启动Web应用
    app, socketio = create_web_app()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)