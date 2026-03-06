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
```

### 3. 配置 OpenClaw 实例

在管理后台添加实例，或通过环境变量配置：

```env
# OpenClaw 实例配置（可选，也可通过管理后台添加）
OPENCLAW_URLS=[
  {
    "id": "cc2-openclaw",
    "name": "CC2 OpenClaw",
    "url": "http://localhost:18789",
    "auth_token": "your-auth-token",
    "enabled": true
  }
]
```

### 4. 启动服务

```bash
python -m henjiu_relay_server.server
```

服务将在 http://localhost:8080 启动。

### 5. 配置 OpenClaw

在 OpenClaw 配置文件中添加工具权限：

```json
{
  "tools": {
    "profile": "messaging"
  }
}
```

重启 OpenClaw Gateway 使配置生效。

## 消息流程

```
上游 → POST /api/send → Relay WebSocket → Connector → OpenClaw Tools Invoke API
                                                        ↓
                                              Telegram/其他渠道
                                                        ↓
OpenClaw 回复 → Connector → Relay → 上游收到 reply 字段
```

详细流程：

1. **上游调用** `POST /api/send`，指定 `instance_id` 和 `message`
2. **Relay 服务器** 通过 WebSocket 转发给对应的 Connector（带 `msg_id`）
3. **Connector** 收到消息后，调用 OpenClaw 的 `/tools/invoke` 接口（`message` 工具）
4. **OpenClaw** 处理消息，通过配置的渠道（如 Telegram）发送，返回回复
5. **Connector** 将回复通过 WebSocket 发送回 Relay（包含 `msg_id`）
6. **Relay** 将 `reply` 放入响应返回给上游

## API 接口

### 发送消息

```bash
curl -X POST http://localhost:8080/api/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"message": "Hello", "instance_id": "cc2-openclaw"}'
```

响应：
```json
{
  "success": true,
  "message_id": "ws-cc2-openclaw-xxx",
  "instance_id": "cc2-openclaw",
  "reply": "Message sent (ID: 123)"
}
```

**参数说明：**
- `message` (必填): 要发送的消息内容
- `instance_id` (必填): 目标 OpenClaw 实例 ID

### 获取实例列表

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8080/api/instances
```

### 获取会话列表

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8080/api/sessions
```

## OpenAI 兼容接口

推荐使用 OpenAI 兼容接口，标准化且支持流式响应。

### Chat Completions

**端点:** `POST /v1/chat/completions`

**认证:** `Authorization: Bearer <API_KEY>`

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | 实例ID (如 `cc2-openclaw`) |
| messages | array | 是 | 消息列表，格式同 OpenAI |
| stream | boolean | 否 | 是否流式响应 (true/false) |
| temperature | number | 否 | 温度参数 (默认 0.7) |
| max_tokens | number | 否 | 最大 token 数 |

**请求示例 (非流式):**
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "cc2-openclaw",
    "messages": [
      {"role": "user", "content": "你好"}
    ]
  }'
```

**响应示例 (非流式):**
```json
{
  "id": "chatcmpl-1234567890",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "cc2-openclaw",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "你好！有什么可以帮你的？"},
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

**请求示例 (流式):**
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "cc2-openclaw",
    "messages": [
      {"role": "user", "content": "你好"}
    ],
    "stream": true
  }'
```

**响应示例 (流式):**
```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"cc2-openclaw","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"cc2-openclaw","choices":[{"index":0,"delta":{"content":"你"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"cc2-openclaw","choices":[{"index":0,"delta":{"content":"好"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"cc2-openclaw","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

## Connector 配置

每个 OpenClaw 实例需要运行 connector 来连接 relay 服务器：

### 1. 安装依赖

```bash
cd henjiu-connector
npm install
```

### 2. 启动 Connector

```bash
node connector.js ws://relay-server:8081 instance-id auth-token "Instance Name" openclaw-token
```

**参数说明：**
1. `ws://relay-server:8081` - Relay 服务器 WebSocket 地址
2. `instance-id` - 实例 ID（与数据库中配置一致）
3. `auth-token` - 认证 Token（与实例配置中的 token 一致）
4. `"Instance Name"` - 实例显示名称
5. `openclaw-token` - OpenClaw Gateway 认证 Token（可选，默认从配置文件读取）

### 3. OpenClaw 工具配置

在 OpenClaw 配置中添加：

```json
{
  "tools": {
    "profile": "messaging"
  }
}
```

这将启用 `message` 工具，允许通过 API 发送消息。

## 管理后台

访问 http://localhost:8080/admin/ 查看管理界面：
- 📊 监控台 - 实例状态、会话数量
- 🖥️ 实例管理 - 添加、编辑、删除实例
- 👥 用户管理 - API 密钥管理

## 部署

### 服务器端部署

1. 克隆代码：
```bash
git clone https://github.com/henjiu-com/henjiu-relay-server.git /opt/henjiu_relay_server
cd /opt/henjiu_relay_server
```

2. 创建虚拟环境并安装依赖：
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. 配置环境变量：
```bash
cp .env.example .env
nano .env  # 编辑配置
```

4. 启动服务：
```bash
nohup /opt/henjiu_relay_server/venv/bin/python -m henjiu_relay_server.server > /opt/henjiu_relay_server/app.log 2>&1 &
```

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
