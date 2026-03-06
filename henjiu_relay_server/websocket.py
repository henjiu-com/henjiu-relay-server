"""WebSocket Server for OpenClaw Relay"""

import asyncio
import logging
import json
from typing import Any

import websockets
from websockets.server import WebSocketServerProtocol

from .config import settings

logger = logging.getLogger(__name__)


class RelayWebSocket:
    """WebSocket 服务器 - 接收远程 OpenClaw 连接"""
    
    def __init__(self):
        self.connections: dict[str, WebSocketServerProtocol] = {}
        self.instance_info: dict[str, dict] = {}
    
    async def register(self, instance_id: str, websocket: WebSocketServerProtocol, info: dict = None):
        """注册连接"""
        # 关闭旧连接如果存在
        if instance_id in self.connections:
            try:
                await self.connections[instance_id].close()
            except:
                pass
        
        self.connections[instance_id] = websocket
        self.instance_info[instance_id] = info or {}
        logger.info(f"Instance {instance_id} connected. Total: {len(self.connections)}")
    
    async def unregister(self, instance_id: str):
        """注销连接"""
        if instance_id in self.connections:
            del self.connections[instance_id]
        if instance_id in self.instance_info:
            del self.instance_info[instance_id]
        logger.info(f"Instance {instance_id} disconnected. Total: {len(self.connections)}")
    
    async def send_to_instance(self, instance_id: str, message: dict) -> bool:
        """发送消息到指定实例"""
        if instance_id not in self.connections:
            logger.warning(f"Instance {instance_id} not connected")
            return False
        
        try:
            ws = self.connections[instance_id]
            await ws.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Failed to send to {instance_id}: {e}")
            await self.unregister(instance_id)
            return False
    
    def is_connected(self, instance_id: str) -> bool:
        """检查实例是否在线"""
        return instance_id in self.connections
    
    def list_connections(self) -> list[dict[str, Any]]:
        """列出所有连接"""
        return [
            {
                "id": inst_id,
                **self.instance_info.get(inst_id, {}),
                "online": True,
            }
            for inst_id in self.connections.keys()
        ]
    
    async def handle_connection(self, websocket: WebSocketServerProtocol):
        """处理新的 WebSocket 连接"""
        instance_id = None
        
        try:
            # 接收注册消息
            register_msg = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(register_msg)
            
            # 支持多种注册格式
            if data.get("type") == "register":
                instance_id = data.get("instance_id") or data.get("id")
            else:
                instance_id = data.get("instance_id") or data.get("id")
            
            if not instance_id:
                await websocket.send(json.dumps({"error": "Missing instance_id"}))
                return
            
            # 验证该实例配置的 auth_token
            instance = settings.instances_dict.get(instance_id)
            if instance and instance.auth_token:
                provided_token = data.get("auth_token") or data.get("token")
                if provided_token != instance.auth_token:
                    logger.warning(f"Authentication failed for instance {instance_id}")
                    await websocket.send(json.dumps({
                        "error": "Authentication failed",
                        "code": "AUTH_FAILED"
                    }))
                    await websocket.close()
                    return
            
            # 注册连接
            await self.register(instance_id, websocket, data.get("info", {}))
            
            # 发送确认
            await websocket.send(json.dumps({
                "type": "registered",
                "instance_id": instance_id,
                "status": "ok"
            }))
            
            # 保持连接，等待消息
            async for msg in websocket:
                try:
                    data = json.loads(msg)
                    msg_type = data.get("type")
                    
                    if msg_type == "ping":
                        await websocket.send(json.dumps({"type": "pong"}))
                    elif msg_type == "message":
                        # 收到客户端发来的消息（本地 OpenClaw 的回复）
                        logger.info(f"Received message from {instance_id}: {data.get('message', '')[:50]}")
                        # TODO: 可以转发给上游或存储
                    else:
                        logger.debug(f"Received from {instance_id}: {data}")
                        
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {instance_id}")
                    
        except asyncio.TimeoutError:
            logger.warning(f"Connection timeout from {path}")
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            if instance_id:
                await self.unregister(instance_id)


# 全局 WebSocket 服务器
ws_server = RelayWebSocket()


async def start_websocket_server():
    """启动 WebSocket 服务器"""
    host = "0.0.0.0"
    port = 8081  # 与 HTTP 服务器不同端口
    
    logger.info(f"Starting WebSocket server on {host}:{port}")
    
    async with websockets.serve(ws_server.handle_connection, host, port):
        await asyncio.Future()  # 永久运行


def get_ws_server() -> RelayWebSocket:
    return ws_server
