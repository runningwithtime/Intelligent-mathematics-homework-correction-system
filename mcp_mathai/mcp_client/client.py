# ===============================
# mcp_client/client.py
# ===============================
import asyncio
import websockets
import json
import logging
from typing import Dict, Any, Optional
import time

logger = logging.getLogger(__name__)

class MCPClient:
    """MCP客户端 - 修复版"""

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.websocket = None
        self.connected = False
        self.request_id = 0

    async def connect(self) -> bool:
        """连接到MCP服务器"""
        try:
            uri = f"ws://{self.host}:{self.port}"
            logger.info(f"尝试连接到MCP服务器: {uri}")

            # 设置连接超时
            self.websocket = await asyncio.wait_for(
                websockets.connect(uri),
                timeout=10.0
            )

            # 接收欢迎消息
            welcome_msg = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=5.0
            )

            welcome_data = json.loads(welcome_msg)
            if welcome_data.get("type") == "welcome":
                self.connected = True
                logger.info("✅ MCP客户端连接成功")
                logger.info(f"服务器信息: {welcome_data.get('server_info', {})}")
                return True
            else:
                raise Exception(f"未收到欢迎消息: {welcome_data}")

        except asyncio.TimeoutError:
            logger.error("连接MCP服务器超时")
            raise Exception("连接MCP服务器超时")
        except ConnectionRefusedError:
            logger.error(f"无法连接到MCP服务器 {self.host}:{self.port} - 连接被拒绝")
            raise Exception(f"MCP服务器不可用 ({self.host}:{self.port})")
        except Exception as e:
            logger.error(f"连接MCP服务器失败: {e}")
            raise Exception(f"MCP连接失败: {e}")

    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("MCP客户端已断开连接")
            except Exception as e:
                logger.error(f"断开连接时出错: {e}")
            finally:
                self.connected = False
                self.websocket = None

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用MCP工具"""
        if not self.connected or not self.websocket:
            raise Exception("MCP客户端未连接")

        try:
            # 生成请求ID
            self.request_id += 1
            request_id = self.request_id

            # 构造JSON-RPC请求
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }

            logger.info(f"发送MCP工具调用: {tool_name}")
            logger.debug(f"请求数据: {json.dumps(request, indent=2)}")

            # 发送请求
            await self.websocket.send(json.dumps(request))

            # 接收响应（设置较长的超时时间）
            response_str = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=60.0  # 给AI处理更多时间
            )

            response = json.loads(response_str)
            logger.debug(f"收到MCP响应: {json.dumps(response, indent=2)}")

            # 检查响应
            if response.get("id") != request_id:
                raise Exception(f"响应ID不匹配: 期望{request_id}, 收到{response.get('id')}")

            if "error" in response:
                error = response["error"]
                raise Exception(f"MCP工具调用失败: {error.get('message', '未知错误')}")

            result = response.get("result")
            if not result:
                raise Exception("MCP工具调用返回空结果")

            logger.info(f"✅ MCP工具调用成功: {tool_name}")
            return result

        except asyncio.TimeoutError:
            logger.error(f"MCP工具调用超时: {tool_name}")
            raise Exception(f"工具调用超时: {tool_name}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
            raise Exception(f"响应格式错误: {e}")
        except Exception as e:
            logger.error(f"MCP工具调用失败: {e}")
            raise

    async def send_custom_message(self, message_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """发送自定义消息"""
        if not self.connected or not self.websocket:
            raise Exception("MCP客户端未连接")

        try:
            message = {
                "type": message_type,
                "timestamp": time.time(),
                **data
            }

            logger.info(f"发送自定义消息: {message_type}")
            await self.websocket.send(json.dumps(message))

            # 接收响应
            response_str = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=30.0
            )

            response = json.loads(response_str)
            logger.info(f"收到自定义消息响应: {response.get('type', 'unknown')}")

            return response

        except asyncio.TimeoutError:
            logger.error(f"自定义消息超时: {message_type}")
            raise Exception(f"消息超时: {message_type}")
        except Exception as e:
            logger.error(f"发送自定义消息失败: {e}")
            raise

    async def ping(self) -> bool:
        """测试连接"""
        try:
            if not self.connected:
                return False

            response = await self.send_custom_message("ping", {"test": True})
            return response.get("type") == "pong"

        except Exception as e:
            logger.error(f"Ping测试失败: {e}")
            return False

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.connected and self.websocket is not None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()