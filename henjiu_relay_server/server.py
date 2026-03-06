"""FastAPI server for OpenClaw Relay - WebSocket 版本"""

import logging
import asyncio
import secrets
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional

from .config import settings, UserConfig
from .router import router
from .websocket import ws_server, start_websocket_server
from .admin import admin_router
from . import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# API 认证依赖
async def verify_api_auth(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """验证 API 认证 - 支持 API Key 或 Basic Auth"""
    
    # 方法1: API Key (优先查数据库)
    if x_api_key:
        user = await database.get_user_by_api_key(x_api_key)
        if user and user.get("enabled"):
            return user
    
    # 方法2: Basic Auth
    if authorization and authorization.startswith("Basic "):
        import base64
        try:
            credentials = base64.b64decode(authorization[6:]).decode()
            username, password = credentials.split(":", 1)
            user = await database.get_user_by_credentials(username, password)
            if user and user.get("enabled"):
                return user
        except:
            pass
    
    raise HTTPException(status_code=401, detail="Authentication required")


async def verify_admin(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """验证管理员权限 - 需要 admin 角色"""
    user = await verify_api_auth(x_api_key, authorization)
    
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return user


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info(f"Starting OpenClaw Relay")
    logger.info(f"HTTP server: {settings.host}:{settings.port}")
    logger.info(f"WebSocket server: {settings.host}:8081")
    
    # 初始化数据库
    db_path = await database.init_db()
    logger.info(f"Database initialized: {db_path}")
    
    # 如果没有用户，从环境变量创建默认用户 (root 管理员)
    users = await database.list_users()
    if not users:
        admin_username = os.getenv("ADMIN_USERNAME", "arno")
        admin_password = os.getenv("ADMIN_PASSWORD", "123456")
        await database.add_user(
            username=admin_username,
            password=admin_password,
            role="admin",
            is_root=True,  # 超级管理员，不可删除
        )
        logger.info(f"Created root admin user: {admin_username}")
    
    # 启动 WebSocket 服务器
    ws_task = asyncio.create_task(start_websocket_server())
    
    yield
    
    # Cleanup
    ws_task.cancel()
    logger.info("Shutting down OpenClaw Relay")


app = FastAPI(
    title="OpenClaw Relay",
    description="多实例 OpenClaw 消息转发服务 (WebSocket)",
    version="0.3.0",
    lifespan=lifespan,
)

# Admin routes
app.include_router(admin_router)


# ============== Models ==============

class SendMessageRequest(BaseModel):
    """发送消息请求"""
    message: str
    target: str | None = None
    channel: str = "telegram"
    sender_id: str | None = None
    instance_id: str | None = None
    metadata: dict | None = None


class SendMessageResponse(BaseModel):
    """发送消息响应"""
    success: bool
    message_id: str | None = None
    instance_id: str | None = None
    error: str | None = None


# ============== Routes ==============

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "channel": settings.channel_id,
        "http_port": settings.port,
        "ws_port": 8081,
    }


@app.get("/api/debug/api-key", dependencies=[Depends(verify_admin)])
async def debug_api_key():
    """Debug: 获取当前 API Key (仅管理员)"""
    if settings.users:
        return {
            "username": settings.users[0].username,
            "api_key": settings.users[0].api_key,
        }
    return {"error": "No users configured"}


@app.get("/api/instances", dependencies=[Depends(verify_api_auth)])
async def list_instances():
    """列出所有实例（包括 WebSocket 连接状态）"""
    # 合并配置的实例和已连接的 WebSocket 客户端
    configured = router.list_instances(include_status=True)
    connected = ws_server.list_connections()
    
    # 标记在线状态
    connected_ids = {c["id"] for c in connected}
    for inst in configured:
        inst["online"] = inst["id"] in connected_ids
    
    return {
        "instances": configured,
        "connected": connected,  # 已连接的实例
        "default": settings.default_instance_id,
    }


@app.get("/api/instances/{instance_id}", dependencies=[Depends(verify_api_auth)])
async def get_instance(instance_id: str):
    """获取指定实例信息"""
    info = router.instances.get(instance_id)
    if not info:
        # 检查是否通过 WebSocket 连接
        if ws_server.is_connected(instance_id):
            return {
                "id": instance_id,
                "online": True,
                "connected_via": "websocket",
            }
        raise HTTPException(status_code=404, detail="Instance not found")
    
    return {
        "id": info.id,
        "name": info.name,
        "url": info.url,
        "enabled": info.enabled,
        "online": ws_server.is_connected(instance_id),
    }


@app.get("/api/instances/{instance_id}/status", dependencies=[Depends(verify_api_auth)])
async def get_instance_status(instance_id: str):
    """检查实例连通性"""
    # 优先检查 WebSocket 连接
    if ws_server.is_connected(instance_id):
        return {
            "id": instance_id,
            "online": True,
            "connected_via": "websocket",
        }
    
    # 检查配置的 HTTP 实例
    inst = router.instances.get(instance_id)
    if inst:
        return {
            "id": instance_id,
            "name": inst.name,
            "url": inst.url,
            "online": False,
            "note": "配置了但未通过 WebSocket 连接",
        }
    
    return {"id": instance_id, "online": False, "error": "Not found"}


@app.post("/api/reload", dependencies=[Depends(verify_api_auth)])
async def reload_config():
    """重新加载配置"""
    try:
        router.reload()
        return {"success": True, "message": "Config reloaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/send", dependencies=[Depends(verify_api_auth)], response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    """发送消息到远程 OpenClaw (通过 WebSocket)"""
    # 确定目标实例
    instance_id = request.instance_id
    if not instance_id:
        inst = router.get_instance(
            channel=request.channel,
            sender_id=request.sender_id or "",
            message=request.message,
        )
        if inst:
            instance_id = inst.id
    
    if not instance_id:
        return SendMessageResponse(
            success=False,
            error="No instance found",
        )
    
    # 通过 WebSocket 发送
    if ws_server.is_connected(instance_id):
        message = {
            "type": "message",
            "message": request.message,
            "channel": request.channel,
        }
        if request.target:
            message["target"] = request.target
        if request.metadata:
            message["metadata"] = request.metadata
        
        success = await ws_server.send_to_instance(instance_id, message)
        
        return SendMessageResponse(
            success=success,
            instance_id=instance_id,
            message_id=f"ws-{instance_id}" if success else None,
        )
    
    # 如果没连接，尝试 HTTP 回退
    if instance_id in router.instances:
        return SendMessageResponse(
            success=False,
            error=f"Instance {instance_id} not connected via WebSocket",
            instance_id=instance_id,
        )
    
    return SendMessageResponse(
        success=False,
        error=f"Unknown instance: {instance_id}",
    )


@app.post("/api/webhook", dependencies=[Depends(verify_api_auth)])
async def webhook(instance_id: str, payload: dict):
    """WebSocket 回调"""
    if not ws_server.is_connected(instance_id):
        return {"error": "Instance not connected"}
    
    await ws_server.send_to_instance(instance_id, {
        "type": "webhook",
        "data": payload,
    })
    return {"status": "sent"}


@app.get("/api/sessions", dependencies=[Depends(verify_api_auth)])
async def list_sessions():
    """获取所有已连接实例的会话"""
    # 通过 WebSocket 获取
    result = {}
    for inst_id in ws_server.connections.keys():
        result[inst_id] = [{"key": "main", "source": "websocket"}]
    return result


# ============== 用户管理 ==============

class AddUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    api_key: str | None = None


@app.post("/api/users", dependencies=[Depends(verify_admin)])
async def add_user(request: AddUserRequest):
    """添加用户"""
    # Check if user already exists
    users = await database.list_users()
    for user in users:
        if user["username"] == request.username:
            return {"error": "Username already exists"}
    
    # Generate API key if not provided
    if not request.api_key:
        request.api_key = secrets.token_urlsafe(32)
    
    new_user = await database.add_user(
        username=request.username,
        password=request.password,
        role=request.role,
        api_key=request.api_key,
    )
    
    return {
        "success": True,
        "user": new_user
    }


@app.get("/api/users", dependencies=[Depends(verify_admin)])
async def list_users():
    """列出用户 (不包含密码)"""
    users = await database.list_users()
    return {
        "users": [
            {
                "username": u["username"],
                "api_key": (u["api_key"][:8] + "...") if u.get("api_key") else "",
                "role": u["role"],
                "enabled": u.get("enabled", 1) == 1,
            }
            for u in users
        ]
    }


@app.delete("/api/users/{username}", dependencies=[Depends(verify_admin)])
async def delete_user(username: str):
    """删除用户 (不能删除 root 用户)"""
    success = await database.delete_user(username)
    if success:
        return {"success": True}
    return {"error": "Cannot delete root user or user not found"}


@app.post("/api/users/{username}/regenerate-key", dependencies=[Depends(verify_admin)])
async def regenerate_api_key(username: str):
    """重新生成用户的 API Key"""
    new_key = await database.regenerate_user_api_key(username)
    if new_key:
        return {
            "success": True,
            "api_key": new_key,
        }
    return {"error": "User not found"}


# ============== Main ==============

def main():
    """Main entry point"""
    import uvicorn
    # 启动 HTTP 服务器，WebSocket 在 lifespan 中单独启动
    uvicorn.run(
        "henjiu_relay_server.server:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()


@app.post("/api/users/{username}/password", dependencies=[Depends(verify_admin)])
async def change_password(username: str, data: dict):
    """修改用户密码"""
    new_password = data.get("password")
    if not new_password:
        return {"error": "Missing password"}
    
    await database.update_user_password(username, new_password)
    return {"success": True, "message": "Password updated"}
