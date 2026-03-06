"""Configuration with multi-user support"""

import secrets
from typing import Literal, Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache
import os
import json
import hashlib

# Load .env file at module import
from dotenv import load_dotenv
load_dotenv()


class AuthConfig(BaseModel):
    """认证配置"""
    type: Literal["none", "bearer", "basic", "apikey", "query"] = "none"
    token: str = ""
    username: str = ""
    password: str = ""
    api_key: str = ""
    api_key_header: str = "X-API-Key"
    
    @property
    def headers(self) -> dict[str, str]:
        headers = {}
        if self.type == "bearer" and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.type == "basic" and self.username:
            import base64
            credentials = f"{self.username}:{self.password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        elif self.type == "apikey" and self.api_key:
            headers[self.api_key_header] = self.api_key
        return headers
    
    @property
    def query_params(self) -> dict[str, str]:
        if self.type == "query" and self.api_key:
            return {"api_key": self.api_key}
        return {}


class InstanceConfig(BaseModel):
    """单个 OpenClaw 实例配置"""
    id: str = Field(..., description="实例标识")
    name: str = Field(default="", description="实例名称")
    url: str = Field(..., description="HTTP 地址")
    
    # 认证配置
    auth: AuthConfig = Field(default_factory=AuthConfig)
    api_token: str = Field(default="", description="API Token (兼容旧版)")
    
    # 连接认证 (每个实例独立的 Token)
    auth_token: str = Field(default="", description="WebSocket 连接认证 Token")
    
    enabled: bool = Field(default=True, description="是否启用")
    timeout: float = Field(default=30.0, description="请求超时(秒)")
    
    @field_validator("auth", mode="before")
    @classmethod
    def convert_old_auth(cls, v, info):
        if isinstance(v, dict):
            if not v.get("token") and info.data.get("api_token"):
                v["token"] = info.data["api_token"]
                v["type"] = "bearer"
            return AuthConfig(**v)
        elif v is None and info.data.get("api_token"):
            return AuthConfig(type="bearer", token=info.data["api_token"])
        return v or AuthConfig()


class UserConfig(BaseModel):
    """用户配置"""
    username: str = Field(..., description="用户名")
    password: str = Field(default="", description="密码")
    api_key: str = Field(default="", description="API Key")
    role: Literal["admin", "user"] = Field(default="user", description="角色")
    enabled: bool = Field(default=True, description="是否启用")


class RouteRule(BaseModel):
    """路由规则"""
    channel: str | None = Field(default=None, description="通道类型")
    sender_id: str | None = Field(default=None, description="发送者ID")
    pattern: str | None = Field(default=None, description="消息匹配模式(正则)")
    instance_id: str = Field(..., description="目标实例ID")


class Settings(BaseSettings):
    """Application settings"""
    host: str = "0.0.0.0"
    port: int = 8080
    channel_id: str = "relay"

    # 用户配置
    users: list[UserConfig] = Field(default_factory=list)
    
    # 默认管理员 (如果没有配置用户)
    admin_username: str = Field(default="arno", description="默认管理员用户名")
    admin_password: str = Field(default="", description="默认管理员密码")

    # 实例配置
    instances: list[InstanceConfig] = Field(default_factory=list)
    routes: list[RouteRule] = Field(default_factory=list)
    default_instance_id: str = Field(default="")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def _generate_api_key() -> str:
    """生成随机 API Key"""
    return secrets.token_urlsafe(32)


def _hash_password(password: str) -> str:
    """简单密码哈希 (生产环境建议用 bcrypt)"""
    return hashlib.sha256(password.encode()).hexdigest()[:16]


def _parse_instance_from_dict(data: dict) -> InstanceConfig:
    """从字典解析实例配置"""
    auth_data = data.get("auth", {})
    if isinstance(auth_data, dict):
        if not auth_data.get("token") and data.get("api_token"):
            auth_data["token"] = data["api_token"]
            auth_data["type"] = "bearer"
    elif isinstance(auth_data, str) and auth_data:
        auth_data = {"type": "bearer", "token": auth_data}
    else:
        auth_data = {}
    
    data["auth"] = auth_data
    return InstanceConfig(**data)


def _load_users_from_env() -> list[UserConfig]:
    """从环境变量加载用户配置"""
    import os
    import json
    
    users = []
    
    # 方法1: JSON 格式
    users_json = os.getenv("USERS", "").strip()
    if users_json:
        try:
            data = json.loads(users_json)
            for item in data:
                users.append(UserConfig(**item))
        except Exception:
            pass
    
    # 方法2: 单用户快捷方式
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    api_key = os.getenv("API_KEY", "").strip()
    
    if username and not users:
        users.append(UserConfig(
            username=username,
            password=password,
            api_key=api_key or _generate_api_key(),
            role="admin",
        ))
    
    return users


def _load_instances_from_env() -> list[InstanceConfig]:
    """从环境变量加载实例配置"""
    from dotenv import load_dotenv
    load_dotenv()
    
    instances = []
    import os
    import json
    
    urls_json = os.getenv("OPENCLAW_URLS", "").strip()
    if urls_json:
        try:
            data = json.loads(urls_json)
            for item in data:
                instances.append(_parse_instance_from_dict(item))
        except Exception:
            pass
    
    single_url = os.getenv("OPENCLAW_URL", "").strip()
    if single_url and not instances:
        auth = AuthConfig(
            type="bearer",
            token=os.getenv("OPENCLAW_API_TOKEN", ""),
        )
        instances.append(InstanceConfig(
            id="default",
            name="Default",
            url=single_url,
            auth=auth,
        ))
    
    return instances


def _load_routes_from_env() -> list[RouteRule]:
    """从环境变量加载路由规则"""
    import os
    import json
    routes = []
    
    routes_json = os.getenv("OPENCLAW_ROUTES", "").strip()
    if routes_json:
        try:
            data = json.loads(routes_json)
            for item in data:
                routes.append(RouteRule(**item))
        except Exception:
            pass
    
    return routes


class SettingsWithDefaults(Settings):
    """带默认值的设置"""
    
    def __init__(self, **data):
        super().__init__(**data)
        
        # Load users - must happen at init
        if not self.users:
            self.users = _load_users_from_env()
        
        # Ensure admin user has API key
        for user in self.users:
            if user.enabled and not user.api_key:
                user.api_key = _generate_api_key()
        
        # Ensure admin has a password hash
        for user in self.users:
            if user.enabled and not user.password and user.role == "admin":
                # Use a default password if not set
                pass
        
        if not self.instances:
            self.instances = _load_instances_from_env()
        
        # Build instances dict for lookup
        self._instances_dict = {inst.id: inst for inst in self.instances}
        
        if not self.routes:
            self.routes = _load_routes_from_env()
        
        if not self.default_instance_id and self.instances:
            self.default_instance_id = self.instances[0].id
    
    @property
    def instances_dict(self):
        return self._instances_dict
    
    def get_user_by_api_key(self, api_key: str) -> UserConfig | None:
        """通过 API Key 获取用户"""
        for user in self.users:
            if user.enabled and user.api_key == api_key:
                return user
        return None
    
    def get_user_by_credentials(self, username: str, password: str) -> UserConfig | None:
        """通过用户名密码获取用户"""
        for user in self.users:
            if user.enabled and user.username == username and user.password == password:
                return user
        return None


@lru_cache
def get_settings() -> SettingsWithDefaults:
    return SettingsWithDefaults()


settings = get_settings()
