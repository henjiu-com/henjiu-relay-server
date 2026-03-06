"""OpenClaw HTTP Client with flexible auth"""

import logging
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from .config import AuthConfig

logger = logging.getLogger(__name__)


class OpenClawClient:
    """HTTP client for remote OpenClaw instance"""
    
    def __init__(
        self,
        base_url: str,
        auth: "AuthConfig | None" = None,
        timeout: float = 30.0,
    ):
        from .config import AuthConfig
        if auth is None:
            auth = AuthConfig()
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        )
    
    def _get_headers(self) -> dict[str, str]:
        """Get headers including auth"""
        headers = {
            "Content-Type": "application/json",
        }
        if self.auth:
            headers.update(self.auth.headers)
        return headers
    
    def _get_query(self) -> dict[str, str]:
        """Get query params including auth"""
        if self.auth:
            return self.auth.query_params
        return {}
    
    async def send_message(
        self,
        message: str,
        target: str | None = None,
        channel: str = "telegram",
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """发送消息到远程 OpenClaw via /tools/invoke"""
        # 使用 sessions_send tool
        payload: dict[str, Any] = {
            "tool": "sessions_send",
            "args": {
                "message": message,
                "channel": channel,
            },
            "sessionKey": "main",
        }
        
        if target:
            payload["args"]["target"] = target
        
        if metadata:
            payload["args"]["metadata"] = metadata
        
        try:
            response = await self.client.post(
                "/tools/invoke",
                json=payload,
                headers=self._get_headers(),
                params=self._get_query(),
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.warning(f"/tools/invoke failed: {e}")
            raise
    
    async def list_sessions(self) -> list[dict[str, Any]]:
        """列出活动会话 via /tools/invoke"""
        payload = {
            "tool": "sessions_list",
            "args": {},
            "sessionKey": "main",
        }
        response = await self.client.post(
            "/tools/invoke",
            json=payload,
            headers=self._get_headers(),
            params=self._get_query(),
        )
        response.raise_for_status()
        data = response.json()
        # sessions_list returns {sessions: [...]} or similar
        return data.get("sessions", []) if isinstance(data, dict) else data
    
    async def get_session_history(
        self,
        session_key: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """获取会话历史 via /tools/invoke"""
        payload = {
            "tool": "sessions_history",
            "args": {"limit": limit},
            "sessionKey": session_key,
        }
        response = await self.client.post(
            "/tools/invoke",
            json=payload,
            headers=self._get_headers(),
            params=self._get_query(),
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
