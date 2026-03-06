# Henjiu Relay

> 多 OpenClaw 实例消息转发服务 - 通过 WebSocket 连接远程 OpenClaw，无需暴露公网端口

## 架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         上游应用                               │
│   (网站/APP/监控系统/自动化脚本)                             │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP POST /api/send
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Henjiu Relay Server                       │
│   ┌─────────────┐                ┌─────────────┐           │
│   │  HTTP API  │                │ WebSocket  │           │
│   │   :8080    │                │   :8081    │           │
│   └──────┬──────┘                └──────┬──────┘           │
│          │                               │                   │
│   ┌──────┴───────────────────────────┴──────┐            │
│   │         Router & Manager                 │            │
│   └──────────────────────────────────────────┘            │
└─────────────────────┬───────────────────────────────────────┘
                      │ WebSocket 长连接
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌───────────┐   ┌───────────┐ ┌───────────┐
│ OpenClaw  │   │ OpenClaw  │ │ OpenClaw  │
│    #1     │   │    #2    │ │    #N    │
│ Telegram  │   │  Feishu   │ │ WhatsApp │
└───────────┘   └───────────┘ └───────────┘
```

## 功能特性

- 🔌 **WebSocket 连接** - 远程 OpenClaw 主动连接，无需暴露公网端口
- 👥 **多用户管理** - 每个用户独立的 API Key
- 🔐 **多层认证** - 管理界面 Basic Auth + API Key + 实例 Token
- 📊 **监控面板** - 实时查看连接状态
- 🔄 **自动重连** - 连接断开自动重连

## 快速开始

### 1. 服务端部署

```bash
# 克隆或复制项目
cd henjiu-relay-server

# 安装依赖
pip install -e .

# 配置 .env 文件
cp .env.example .env
# 编辑 .env 填入配置

# 启动服务
python3 -m henjiu_relay_server.server
```

### 2. 远程插件部署

```bash
# 复制插件到远程 OpenClaw
cp -r henjiu-connector ~/.openclaw/extensions/henjiu-connector

# 安装依赖
cd ~/.openclaw/extensions/henjiu-connector
npm install ws

# 配置 OpenClaw
openclaw config.patch '{
  "channels": {
    "henjiu-connector": {
      "enabled": true,
      "relayUrl": "ws://你的服务端IP:8081",
      "instanceId": "实例ID",
      "instanceName": "显示名称",
      "authToken": "连接Token"
    }
  },
  "plugins": { "allow": ["henjiu-connector"] }
}'

# 重启
openclaw gateway restart
```

## 认证说明

| 接口 | 认证方式 | 示例 |
|------|----------|------|
| `/admin/*` | Basic Auth | `curl -u user:pass ...` |
| `/api/*` | API Key | `curl -H "X-API-Key: xxx" ...` |
| WebSocket | Instance Token | 注册时传递 auth_token |

## API 接口

### 认证方式

```bash
# 方式1: API Key (推荐)
curl -H "X-API-Key: your-api-key" http://IP:8080/api/send

# 方式2: Basic Auth (管理员)
curl -u admin:password http://IP:8080/api/instances
```

### 接口列表

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/health` | ❌ | 健康检查 |
| GET | `/api/debug/api-key` | 管理员 | 获取当前用户的 API Key |
| GET | `/api/instances` | ✅ | 列出实例 |
| GET | `/api/instances/{id}/status` | ✅ | 检查实例状态 |
| GET | `/api/sessions` | ✅ | 获取会话列表 |
| POST | `/api/send` | ✅ | 发送消息 |
| POST | `/api/reload` | 管理员 | 重载配置 |
| GET | `/api/users` | 管理员 | 列出用户 |
| POST | `/api/users` | 管理员 | 添加用户 |
| DELETE | `/api/users/{name}` | 管理员 | 删除用户 |
| POST | `/api/users/{name}/regenerate-key` | 管理员 | 重置用户 API Key |

### 发送消息

```bash
curl -X POST http://IP:8080/api/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "message": "Hello",
    "channel": "telegram",
    "instance_id": "tianyi"
  }'
```

### 响应示例

```json
// 成功
{
  "success": true,
  "message_id": "msg-abc123",
  "instance_id": "tianyi"
}

// 失败
{
  "success": false,
  "error": "Instance not connected"
}
```

## 配置说明

### 服务端 .env

```bash
# 服务器
HOST=0.0.0.0
PORT=8080

# 管理员账号
ADMIN_USERNAME=arno
ADMIN_PASSWORD=123456

# 实例配置 (JSON)
INSTANCES=[
  {
    "id": "tianyi",
    "name": "天翼云-冯麟",
    "url": "http://192.168.1.10:18789",
    "auth_token": "token-xxx",
    "enabled": true
  }
]
```

### 插件配置

```json
{
  "channels": {
    "henjiu-connector": {
      "enabled": true,
      "relayUrl": "ws://服务端IP:8081",
      "instanceId": "实例ID",
      "instanceName": "显示名称",
      "authToken": "连接Token"
    }
  }
}
```

## 管理界面

- **监控台**: `http://IP:8080/admin/dashboard`
- **用户管理**: `http://IP:8080/admin/users`
- **实例管理**: `http://IP:8080/admin`
- **API 文档**: `http://IP:8080/admin/api-docs`

## 项目结构

```
henjiu-relay-server/
├── henjiu_relay_server/   # Python 服务端
│   ├── server.py        # HTTP API
│   ├── websocket.py     # WebSocket 服务
│   ├── router.py        # 消息路由
│   ├── config.py        # 配置管理
│   └── admin.py        # 管理界面
├── henjiu-connector/   # 远程插件
│   ├── index.js        # 插件主文件
│   ├── package.json
│   └── DEPLOY.md       # 部署手册
├── tests/              # 测试
├── pyproject.toml
└── README.md
```

## 部署到服务器

```bash
# 1. 创建目录
ssh user@server "mkdir -p /opt/henjiu-relay"

# 2. 上传文件
scp -r . user@server:/opt/henjiu-relay/

# 3. 安装依赖
ssh user@server "cd /opt/henjiu-relay && pip install -e ."

# 4. 配置
ssh user@server "vim /opt/henjiu-relay/.env"

# 5. 启动
ssh user@server "cd /opt/henjiu-relay && python3 -m henjiu_relay_server.server"
```

## 优势对比

| 特性 | 传统方式 | Henjiu Relay |
|------|----------|---------------|
| 端口暴露 | 需要开放公网端口 | 无需暴露 |
| 认证 | 无/单一 | 多层认证 |
| 连接方式 | HTTP | WebSocket |
| 实例管理 | 手动配置 | 界面管理 |
| 用户管理 | 无 | 多用户+独立API Key |

## License

MIT
