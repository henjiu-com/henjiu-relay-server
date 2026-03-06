"""
OpenClaw Relay - 多实例消息转发服务

支持配置多个远程 OpenClaw 实例，通过统一的 API 接口转发消息。
"""

from .config import Settings, InstanceConfig, settings
from .router import MessageRouter
from .server import app

__version__ = "0.2.0"
