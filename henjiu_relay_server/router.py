"""Message router - 选择合适的实例"""

import logging
import re
from typing import Any

from .config import InstanceConfig, RouteRule, settings

logger = logging.getLogger(__name__)


class MessageRouter:
    """消息路由器"""
    
    def __init__(self):
        self.instances: dict[str, InstanceConfig] = {}
        self.routes: list[RouteRule] = []
        self.default_instance_id = ""
        
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        # 实例映射
        for inst in settings.instances:
            self.instances[inst.id] = inst
            logger.info(f"Loaded instance: {inst.id} -> {inst.url}")
        
        # 路由规则
        self.routes = settings.routes
        for route in self.routes:
            logger.info(f"Route: {route.channel or '*'}:{route.sender_id or '*'} -> {route.instance_id}")
        
        # 默认实例
        self.default_instance_id = settings.default_instance_id
        logger.info(f"Default instance: {self.default_instance_id}")
    
    def get_instance(self, channel: str = "", sender_id: str = "", message: str = "") -> InstanceConfig | None:
        """根据条件获取目标实例"""
        
        # 按顺序匹配路由规则
        for rule in self.routes:
            # 检查 channel
            if rule.channel and rule.channel != channel:
                continue
            
            # 检查 sender_id
            if rule.sender_id and rule.sender_id != sender_id:
                continue
            
            # 检查消息模式
            if rule.pattern:
                try:
                    if not re.search(rule.pattern, message):
                        continue
                except re.error as e:
                    logger.warning(f"Invalid regex pattern: {rule.pattern}: {e}")
                    continue
            
            # 匹配成功
            instance_id = rule.instance_id
            if instance_id in self.instances:
                inst = self.instances[instance_id]
                if inst.enabled:
                    logger.info(f"Routed to instance {instance_id} (rule match)")
                    return inst
                else:
                    logger.warning(f"Instance {instance_id} is disabled")
        
        # 使用默认实例
        if self.default_instance_id and self.default_instance_id in self.instances:
            inst = self.instances[self.default_instance_id]
            if inst.enabled:
                logger.info(f"Using default instance {self.default_instance_id}")
                return inst
        
        return None
    
    def list_instances(self, include_status: bool = False) -> list[dict[str, Any]]:
        """列出所有实例"""
        result = []
        for inst in self.instances.values():
            item = {
                "id": inst.id,
                "name": inst.name,
                "url": inst.url,
                "enabled": inst.enabled,
                "auth_type": inst.auth.type if inst.auth else "none",
            }
            if include_status:
                # Will be filled by server
                item["status"] = "unknown"
            result.append(item)
        return result
    
    async def check_instance_status(self, instance_id: str) -> dict[str, Any]:
        """检查实例连通性"""
        if instance_id not in self.instances:
            return {"error": "Instance not found", "online": False}
        
        inst = self.instances[instance_id]
        
        try:
            from .client import OpenClawClient
            client = OpenClawClient(base_url=inst.url, auth=inst.auth, timeout=5.0)
            
            # Try to call sessions_list as health check
            response = await client.client.post(
                "/tools/invoke",
                json={"tool": "sessions_list", "args": {}, "sessionKey": "main"},
                headers=client._get_headers(),
                params=client._get_query(),
            )
            await client.close()
            
            if response.status_code == 200:
                return {
                    "id": instance_id,
                    "name": inst.name,
                    "url": inst.url,
                    "online": True,
                }
            else:
                return {
                    "id": instance_id,
                    "online": False,
                    "error": f"HTTP {response.status_code}",
                }
        except Exception as e:
            return {
                "id": instance_id,
                "online": False,
                "error": str(e),
            }
    
    def get_instance_status(self, instance_id: str) -> dict[str, Any]:
        """获取实例状态"""
        if instance_id not in self.instances:
            return {"error": "Instance not found"}
        
        inst = self.instances[instance_id]
        return {
            "id": inst.id,
            "name": inst.name,
            "url": inst.url,
            "enabled": inst.enabled,
        }
    
    def reload(self):
        """重新加载配置"""
        # 清除缓存重新加载
        settings.instances = []
        settings.default_instance_id = ""
        settings.routes = []
        # 重新初始化
        from .config import _load_instances_from_env, _load_routes_from_env
        settings.instances = _load_instances_from_env()
        settings.routes = _load_routes_from_env()
        
        if settings.instances:
            settings.default_instance_id = settings.instances[0].id
        
        self._load_config()


# 全局路由器
router = MessageRouter()
