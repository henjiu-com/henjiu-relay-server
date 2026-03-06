# Henjiu Relay

> 多 OpenClaw 实例消息转发服务 - 通过 WebSocket 连接，无需公网暴露端口

## 架构

```
上游应用                    Henjiu Relay                  远程 OpenClaw
    │                              │                                  │
    │  1. HTTP POST               │                                  │
    │  /api/send                  │                                  │
    │────────────────────────────>│                                  │
    │                              │  2. WebSocket 转发              │
    │                              │─────────────────────────────────>│
    │                              │                                  │
    │                              │          3. 本地执行             │
    │                              │     (openclaw agent 处理)        │
    │                              │                                  │
    │                              │  4. WebSocket 响应              │
    │                              │<─────────────────────────────────│
    │                              │                                  │
    │  5. HTTP 响应               │                                  │
    │<────────────────────────────│                                  │
```

## 认证说明

### 两层认证

| 接口 | 认证方式 | 说明 |
|------|----------|------|
| 管理界面 | Basic Auth | 用户名 + 密码 |
| API | API Key | 每个用户独立的 Key |
| WebSocket | Instance Token | 每个实例独立的 Token |

### 配置示例

```json
{
  "users": [
    {
      "username": "arno",
      "password": "123456",
      "api_key": "随机生成的Key",
      "role": "admin"
    }
  ],
  "instances": [
    {
      "id": "tianyi",
      "name": "天翼云-冯麟",
      "url": "http://192.168.1.10:18789",
      "auth_token": "tianyi-token-2024"
    }
  ]
}
```

## 快速开始

### 1. 启动服务端

```bash
cd henjiu-relay-server
pip install -e .
python3 -m henjiu_relay_server.server
```

### 2. 部署插件到远程 OpenClaw

```bash
# 1. 复制插件到远程
mkdir -p ~/.openclaw/extensions/relay

# 2. 配置 (替换为你的 Token)
openclaw config.patch '{
  "channels": {
    "relay": {
      "enabled": true,
      "relayUrl": "ws://服务端IP:8081",
      "instanceId": "tianyi",
      "instanceName": "天翼云-冯麟",
      "authToken": "tianyi-token-2024"
    }
  },
  "plugins": { "allow": ["relay"] }
}'

# 3. 重启
openclaw gateway restart
```

### 3. 获取 API Key

首次启动后，访问:
```
GET /api/debug/api-key
```
返回用户的 API Key

### 4. 调用 API

```bash
curl -H "X-API-Key: your-api-key" \
  -X POST http://localhost:8080/api/send \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "channel": "telegram"}'
```

## 配置说明

### 服务端 (.env)

| 变量 | 说明 | 示例 |
|------|------|------|
| `HOST` | 监听地址 | 0.0.0.0 |
| `PORT` | HTTP 端口 | 8080 |
| `USERS` | 用户列表 (JSON) | 见上文 |
| `OPENCLAW_URLS` | 实例列表 (JSON) | 见上文 |

### 插件配置

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `enabled` | 是否启用 | true |
| `relayUrl` | 服务端 WebSocket | ws://IP:8081 |
| `instanceId` | 实例ID | tianyi |
| `instanceName` | 显示名称 | 天翼云-冯麟 |
| `authToken` | **连接认证 Token** | 必须与服务端配置的 auth_token 一致 |

## 界面

- **监控台**: http://IP:8080/admin/dashboard
- **管理页**: http://IP:8080/admin
- **API 手册**: http://IP:8080/admin/api-docs

## 优势

| 传统方式 | Henjiu Relay |
|----------|--------------|
| 需要对方暴露公网端口 | 无需公网暴露 |
| 无认证 | 多层认证 |
| 单一Token | 每实例独立Token |
| 单用户 | 多用户+独立API Key |

## 许可证

MIT
