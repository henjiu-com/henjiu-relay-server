# Henjiu Relay Server

中继服务器，用于连接多个 OpenClaw 实例，支持消息转发和统一管理。

## 功能特性

- 🌐 WebSocket 连接多个 OpenClaw 实例
- 📱 统一的消息发送接口
- 🔐 API 密钥认证
- 📊 管理后台（实例管理、状态监控）
- 🔄 消息转发与回复接收

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件：

```env
# 管理账号
ADMIN_USERNAME=admin
ADMIN_PASSWORD=123456

# API 认证密钥
API_KEY=your-secret-api-key

# OpenClaw 实例配置
OPENCLAW_URLS=[
  {
    "id": "cc2-openclaw",
    "name": "CC2 OpenClaw",
    "url": "http://localhost:18789",
    "auth_token": "your-auth-token"
  }
]
```

### 3. 启动服务

```bash
python -m henjiu_relay_server.server
```

服务将在 http://localhost:8080 启动。

## 消息流程

```
上游 → POST /api/send → Relay WebSocket → Connector → OpenClaw API
                                      ↓
                            OpenClaw 回复 ← Connector 发回
                                      ↓
                            上游收到 reply 字段
```

详细流程：

1. **上游调用** `POST /api/send`，指定 `instance_id` 和 `message`
2. **Relay 服务器** 通过 WebSocket 转发给对应的 Connector（带 `msg_id`）
3. **Connector** 收到消息后，调用 OpenClaw 的 `/api/message` 接口
4. **OpenClaw** 处理消息，返回回复
5. **Connector** 将回复通过 WebSocket 发送回 Relay（包含 `msg_id`）
6. **Relay** 将 `reply` 放入响应返回给上游

## API 接口

### 发送消息

```bash
curl -X POST http://localhost:8080/api/send \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: your-api-key" \\
  -d '{"message": "Hello", "instance_id": "cc2-openclaw"}'
```

响应：
```json
{
  "success": true,
  "message_id": "ws-cc2-openclaw-xxx",
  "instance_id": "cc2-openclaw",
  "reply": "OpenClaw 的回复内容"
}
```

### 获取实例列表

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8080/api/instances
```

### 获取会话列表

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8080/api/sessions
```

## Connector 插件

每个 OpenClaw 实例需要运行 connector 插件来连接 relay 服务器：

```bash
cd henjiu-connector
npm install
node connector.js ws://relay-server:8081 instance-id auth-token "Instance Name" http://openclaw-url:18789
```

参数说明：
1. WebSocket 地址（relay 服务器）
2. 实例 ID
3. 认证 Token
4. 实例名称
5. OpenClaw URL（可选，默认 http://localhost:18789）

## 管理后台

访问 http://localhost:8080/admin/ 查看管理界面：
- 📊 监控台 - 实例状态、会话数量
- 🖥️ 实例管理 - 添加、编辑、删除实例
- 👥 用户管理 - API 密钥管理

## 部署

### 使用 systemd

创建 `/etc/systemd/system/henjiu-relay.service`：

```ini
[Unit]
Description=Henjiu Relay Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/henjiu_relay_server
ExecStart=/opt/henjiu_relay_server/venv/bin/python -m henjiu_relay_server.server
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable henjiu-relay
sudo systemctl start henjiu-relay
```

## 许可证

MIT
