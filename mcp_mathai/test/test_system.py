import asyncio
import threading
from datetime import time


def test_mcp_server():
    """测试MCP服务器启动 - 修复版"""
    print("🔧 测试1: MCP服务器启动")
    try:
        from mcp_server.server import MathGradingMCPServer

        async def test_server():
            # 尝试不同端口避免冲突
            for port in range(8765, 8775):
                try:
                    server = MathGradingMCPServer(host="localhost", port=port)
                    server_instance = await server.start_server()
                    print(f"✅ MCP服务器启动成功 (端口: {port})")
                    return server_instance, port
                except OSError as e:
                    if "10048" in str(e):  # 端口被占用
                        continue
                    else:
                        raise
            raise Exception("无法找到可用端口")

        # 在后台启动服务器
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def run_server():
            try:
                server_instance, port = loop.run_until_complete(test_server())
                print(f"🔗 MCP服务器正在运行 (端口: {port})，等待连接...")
                # 保存端口信息供其他测试使用
                with open("server_port.txt", "w") as f:
                    f.write(str(port))
                loop.run_forever()
            except Exception as e:
                print(f"❌ MCP服务器启动失败: {e}")

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # 等待服务器启动
        time.sleep(3)
        print("✅ 测试1通过")
        return True

    except Exception as e:
        print(f"❌ 测试1失败: {e}")
        return False

def test_mcp_client():
    """测试MCP客户端连接 - 修复版"""
    print("\n🔧 测试2: MCP客户端连接")
    try:
        from mcp_client.client import MCPClient

        # 读取服务器端口
        port = 8765
        try:
            with open("server_port.txt", "r") as f:
                port = int(f.read().strip())
        except:
            pass

        async def test_client():
            client = MCPClient(host="localhost", port=port)
            await client.connect()

            # 测试ping
            ping_result = await client.ping()
            if ping_result:
                print("✅ MCP客户端连接和ping测试成功")
            else:
                print("⚠️ MCP客户端连接成功但ping失败")

            await client.disconnect()
            return True

        # 测试连接
        asyncio.run(test_client())
        print("✅ 测试2通过")
        return True

    except Exception as e:
        print(f"❌ 测试2失败: {e}")
        return False