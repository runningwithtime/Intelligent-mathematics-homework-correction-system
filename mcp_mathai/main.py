# ===============================
# main.py
# ===============================
import asyncio
import argparse
import sys
import threading
import time
import logging
import socket
import psutil
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 修复Windows编码问题
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

logger = logging.getLogger("main")

class PortManager:
    """端口管理器"""

    @staticmethod
    def is_port_available(host: str, port: int) -> bool:
        """检查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind((host, port))
                return True
        except OSError:
            return False

    @staticmethod
    def find_available_port(start_port: int = 8765, max_attempts: int = 20) -> int:
        """寻找可用端口"""
        for port in range(start_port, start_port + max_attempts):
            if PortManager.is_port_available("localhost", port):
                return port
        raise Exception(f"无法在 {start_port}-{start_port + max_attempts} 范围内找到可用端口")

    @staticmethod
    def get_port_processes(port: int) -> list:
        """获取占用端口的进程信息"""
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'connections']):
                try:
                    for conn in proc.info.get('connections', []):
                        if hasattr(conn, 'laddr') and conn.laddr.port == port:
                            processes.append({
                                "pid": proc.info['pid'],
                                "name": proc.info['name'],
                                "status": getattr(conn, 'status', 'unknown')
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                    continue
        except Exception as e:
            logger.warning(f"无法获取端口进程信息: {e}")
        return processes

    @staticmethod
    def cleanup_port(port: int, force: bool = False) -> bool:
        """清理端口（可选择是否强制）"""
        if PortManager.is_port_available("localhost", port):
            logger.info(f"✅ 端口 {port} 已经可用")
            return True

        processes = PortManager.get_port_processes(port)
        if not processes:
            logger.warning(f"⚠️ 端口 {port} 被占用但未找到占用进程")
            return False

        logger.info(f"🔍 发现 {len(processes)} 个进程占用端口 {port}:")
        for proc in processes:
            logger.info(f"  - PID: {proc['pid']}, 名称: {proc['name']}")

        if force:
            return PortManager._force_cleanup_processes(processes, port)
        else:
            return False

    @staticmethod
    def _force_cleanup_processes(processes: list, port: int) -> bool:
        """强制清理进程"""
        killed_count = 0
        for proc_info in processes:
            try:
                proc = psutil.Process(proc_info['pid'])
                logger.info(f"⚡ 终止进程: PID={proc_info['pid']}, 名称={proc_info['name']}")
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                    killed_count += 1
                except psutil.TimeoutExpired:
                    logger.warning(f"🔥 强制杀死进程: PID={proc_info['pid']}")
                    proc.kill()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.warning(f"⚠️ 无法终止进程 PID={proc_info['pid']}: {e}")

        if killed_count > 0:
            logger.info(f"✅ 已终止 {killed_count} 个进程")
            time.sleep(2)  # 等待端口释放
            return PortManager.is_port_available("localhost", port)

        return False

class SystemManager:
    """系统管理器 - 统一管理所有组件"""

    def __init__(self):
        self.mcp_server_running = False
        self.mcp_server_thread = None
        self.server_instance = None
        self.mcp_port = 8765
        self.port_manager = PortManager()

    def prepare_mcp_port(self) -> int:
        """准备MCP服务器端口"""
        logger.info("🔍 检查MCP服务器端口...")

        # 检查默认端口
        if self.port_manager.is_port_available("localhost", self.mcp_port):
            logger.info(f"✅ 端口 {self.mcp_port} 可用")
            return self.mcp_port

        # 端口被占用，显示占用信息
        processes = self.port_manager.get_port_processes(self.mcp_port)
        logger.warning(f"⚠️ 端口 {self.mcp_port} 被占用")

        if processes:
            logger.info("📋 占用进程:")
            for proc in processes:
                logger.info(f"  - PID: {proc['pid']}, 名称: {proc['name']}")

            # 尝试自动清理（谨慎模式，只清理明显的旧实例）
            should_cleanup = any(
                'python' in proc['name'].lower() or
                'mcp' in proc['name'].lower() for proc in processes
            )

            if should_cleanup:
                logger.info("🧹 尝试自动清理旧的Python/MCP进程...")
                if self.port_manager.cleanup_port(self.mcp_port, force=True):
                    logger.info(f"✅ 端口 {self.mcp_port} 清理成功")
                    return self.mcp_port

        # 如果清理失败，寻找替代端口
        logger.info("🔄 寻找替代端口...")
        try:
            new_port = self.port_manager.find_available_port(8766, 20)
            logger.info(f"✅ 找到可用端口: {new_port}")
            self.mcp_port = new_port
            return new_port
        except Exception as e:
            logger.error(f"❌ 无法找到可用端口: {e}")
            raise

    def start_mcp_server(self):
        """在后台线程启动MCP服务器"""
        def run_server():
            try:
                from mcp_server.server import MathGradingMCPServer

                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def server_main():
                    # 使用准备好的端口
                    server = MathGradingMCPServer(host="localhost", port=self.mcp_port)
                    self.server_instance = await server.start_server()
                    self.mcp_server_running = True
                    logger.info(f"✅ MCP服务器在端口 {self.mcp_port} 启动成功")

                    # 保持服务器运行
                    try:
                        await self.server_instance.wait_closed()
                    except Exception as e:
                        logger.error(f"服务器运行错误: {e}")

                # 运行服务器
                loop.run_until_complete(server_main())

            except Exception as e:
                logger.error(f"MCP服务器启动失败: {e}")
                self.mcp_server_running = False

        try:
            # 准备端口
            actual_port = self.prepare_mcp_port()
            logger.info(f"📡 将在端口 {actual_port} 启动MCP服务器")

            # 启动后台线程
            self.mcp_server_thread = threading.Thread(target=run_server, daemon=True)
            self.mcp_server_thread.start()

            # 等待服务器启动
            logger.info("⏳ 等待MCP服务器启动...")
            time.sleep(3)

            return self.mcp_server_running

        except Exception as e:
            logger.error(f"端口准备失败: {e}")
            return False

    def test_mcp_connection(self):
        """测试MCP连接"""
        try:
            from mcp_client.client import MCPClient

            async def test_connection():
                try:
                    client = MCPClient(host="localhost", port=self.mcp_port)
                    await client.connect()
                    ping_result = await client.ping()
                    await client.disconnect()
                    return ping_result
                except Exception as e:
                    logger.warning(f"MCP连接测试失败: {e}")
                    return False

            result = asyncio.run(test_connection())
            if result:
                logger.info(f"✅ MCP连接测试成功 (端口 {self.mcp_port})")
            else:
                logger.warning(f"⚠️ MCP连接测试失败 (端口 {self.mcp_port})")
            return result

        except Exception as e:
            logger.error(f"MCP连接测试异常: {e}")
            return False

    def check_database(self):
        """检查并修复数据库"""
        try:
            import sqlite3
            from pathlib import Path

            db_path = "math_grading.db"
            logger.info("🗄️ 检查数据库...")

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 检查并创建students表
            try:
                cursor.execute("SELECT * FROM students LIMIT 1")
                logger.info("✅ students表存在")
            except sqlite3.OperationalError:
                logger.info("📝 创建students表...")
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
                logger.info("✅ students表创建成功")

            # 检查并添加缺失的列
            cursor.execute("PRAGMA table_info(students)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'class_name' not in columns:
                logger.info("📝 添加class_name列...")
                cursor.execute("ALTER TABLE students ADD COLUMN class_name TEXT")
                logger.info("✅ class_name列添加成功")

            conn.commit()
            conn.close()
            logger.info("✅ 数据库检查完成")
            return True

        except Exception as e:
            logger.error(f"数据库检查失败: {e}")
            return False

    def start_gui(self):
        """启动GUI"""
        try:
            logger.info("🖥️ 启动GUI界面...")
            from frontend.gui import MathGradingGUI

            # 如果端口不是默认的，需要通知GUI
            if self.mcp_port != 8765:
                logger.info(f"💡 GUI将使用MCP端口: {self.mcp_port}")
                # 这里可以通过环境变量或配置文件传递端口信息
                import os
                os.environ['MCP_PORT'] = str(self.mcp_port)

            app = MathGradingGUI()
            logger.info("✅ GUI创建成功，开始运行...")
            app.run()
        except Exception as e:
            logger.error(f"GUI启动失败: {e}")
            raise

def start_server_only():
    """仅启动MCP服务器模式"""
    try:
        manager = SystemManager()
        port = manager.prepare_mcp_port()
        logger.info(f"🔧 启动服务器模式 (端口 {port})...")

        from mcp_server.server import main as server_main
        asyncio.run(server_main())
    except Exception as e:
        logger.error(f"服务器模式失败: {e}")

def start_gui_only():
    """仅启动GUI模式"""
    try:
        logger.info("🖥️ 启动GUI模式...")
        from frontend.gui import MathGradingGUI
        app = MathGradingGUI()
        app.run()
    except Exception as e:
        logger.error(f"GUI模式失败: {e}")

def start_web_only():
    """仅启动Web模式"""
    try:
        logger.info("🌐 启动Web模式...")
        from api.routes import create_app
        app = create_app()
        app.run(host="localhost", port=8766, debug=True)
    except Exception as e:
        logger.error(f"Web模式失败: {e}")

def start_all_services():
    """启动所有服务 - 修复版"""
    logger.info("🚀 启动完整系统...")

    # 创建系统管理器
    manager = SystemManager()

    # 1. 检查数据库
    logger.info("📋 步骤1: 检查数据库...")
    if not manager.check_database():
        logger.warning("⚠️ 数据库检查失败，但继续启动")

    # 2. 启动MCP服务器
    logger.info("📋 步骤2: 启动MCP服务器...")
    if manager.start_mcp_server():
        logger.info(f"✅ MCP服务器启动成功 (端口 {manager.mcp_port})")

        # 3. 测试连接
        logger.info("📋 步骤3: 测试MCP连接...")
        if manager.test_mcp_connection():
            logger.info("✅ MCP服务完全就绪")
        else:
            logger.warning("⚠️ MCP连接测试失败，但继续启动GUI")
    else:
        logger.error("❌ MCP服务器启动失败，但继续启动GUI")

    # 4. 启动GUI
    logger.info("📋 步骤4: 启动GUI...")
    try:
        manager.start_gui()
    except Exception as e:
        logger.error(f"GUI启动失败: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数学作业批改系统")
    parser.add_argument("--mode", choices=["server", "gui", "web", "all", "test", "port-check"],
                        default="all", help="启动模式")
    parser.add_argument("--port", type=int, default=8765, help="MCP服务器端口")

    args = parser.parse_args()

    logger.info(f"🎯 启动模式: {args.mode}")
    logger.info("=" * 50)

    try:
        if args.mode == "port-check":
            # 端口检查模式
            manager = SystemManager()
            logger.info("🔍 端口检查模式")
            try:
                port = manager.prepare_mcp_port()
                logger.info(f"✅ 端口检查完成，可用端口: {port}")
            except Exception as e:
                logger.error(f"❌ 端口检查失败: {e}")
        elif args.mode == "server":
            start_server_only()
        elif args.mode == "gui":
            start_gui_only()
        elif args.mode == "web":
            start_web_only()
        elif args.mode == "test":
            # 运行测试脚本
            logger.info("🧪 运行系统测试...")
            import subprocess
            subprocess.run([sys.executable, "test_system.py"])
        elif args.mode == "all":
            start_all_services()
        else:
            logger.error(f"未知模式: {args.mode}")

    except KeyboardInterrupt:
        logger.info("👋 用户中断程序")
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    print("🧮 数学作业批改系统 v1.0")
    print("=" * 30)
    main()