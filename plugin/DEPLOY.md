# Henjiu Relay 插件部署手册

本文档介绍如何将 Henjiu Relay 插件部署到远程 OpenClaw 实例。

## 简介

Henjiu Relay 插件使远程 OpenClaw 通过 WebSocket 主动连接到 Henjiu Relay 服务器，实现消息转发，无需暴露公网端口。

```
远程 OpenClaw                    Henjiu Relay Server
┌─────────────────┐              ┌─────────────────────┐
│                 │   WebSocket  │                     │
│  OpenClaw       │─────────────▶│   本地服务器        │
│  + Relay Plugin │   ws://IP:   │   (你的机器)        │
│                 │     8081     │                     │
└─────────────────┘              └─────────────────────┘
```

## 文件清单

```
~/.openclaw/extensions/relay/
├── index.js            # 插件主文件 (必需)
├── relay-plugin.json   # 插件配置 (必需)
└── package.json        # 依赖配置 (必需)
```

## 部署步骤

### 步骤 1: 创建目录

在远程服务器上执行：

```bash
mkdir -p ~/.openclaw/extensions/relay
```

### 步骤 2: 复制文件

将以下 3 个文件复制到上述目录：

1. `index.js` - 插件主文件
2. `relay-plugin.json` - 插件配置
3. `package.json` - Node.js 依赖

可以通过以下方式复制：
- SCP: `scp *.js *.json user@remote:~/.openclaw/extensions/relay/`
- 或者直接在远程服务器上创建文件并粘贴内容

### 步骤 3: 安装依赖

```bash
cd ~/.openclaw/extensions/relay
npm install ws
```

### 步骤 4: 配置 OpenClaw

使用 `openclaw config.patch` 命令配置：

```bash
openclaw config.patch '{
  "channels": {
    "relay": {
      "enabled": true,
      "relayUrl": "ws://你的服务端IP:8081",
      "instanceId": "tianyi",
      "instanceName": "天翼云-冯麟",
      "authToken": "tianyi-token-2024"
    }
  },
  "plugins": {
    "allow": ["relay"]
  }
}'
```

⚠️ **重要**: `authToken` 必须与服务端配置的实例 `auth_token` 一致，否则无法连接！

**配置项说明：**

| 配置项 | 必填 | 说明 | 示例 |
|--------|------|------|------|
| `relayUrl` | ✅ | Henjiu Relay 服务器的 WebSocket 地址 | ws://192.168.1.100:8081 |
| `instanceId` | ✅ | 唯一标识，必须与服务端配置一致 | tianyi |
| `instanceName` | - | 显示名称 | 天翼云-冯麟 |
| `authToken` | ✅ | **连接认证 Token**，必须与服务端实例的 auth_token 一致 | tianyi-token-2024 |
|--------|------|------|------|
| `relayUrl` | ✅ | Henjiu Relay 服务器的 WebSocket 地址 | ws://192.168.111.201:8081 |
| `instanceId` | ✅ | 唯一标识，不能与其他实例重复 | tianyi, claw-b |
| `instanceName` | - | 显示名称，方便识别 | 天翼云-冯麟 |

### 步骤 5: 重启 Gateway

```bash
openclaw gateway restart
```

### 步骤 6: 验证连接

#### 方法 1: 查看日志

```bash
openclaw logs | grep -i relay
```

应该看到类似输出：

```
Relay channel: connecting to ws://192.168.111.201:8081 as tianyi
Relay channel: connected to ws://192.168.111.201:8081
Relay channel: registered as tianyi
```

#### 方法 2: 访问监控台

在浏览器打开：http://你的服务端IP:8080/admin/dashboard

登录后查看"已连接的实例"部分，应该能看到你的实例显示"在线"。

## 配置修改

如果需要修改配置：

```bash
openclaw config.patch '{
  "channels": {
    "relay": {
      "relayUrl": "ws://新的IP:8081"
    }
  }
}'

# 重启生效
openclaw gateway restart
```

## 故障排查

### 问题 1: 连接被拒绝

```
Error: connect ECONNREFUSED
```

**原因:** 无法连接到 Relay 服务器

**解决:**
1. 检查 Relay 服务器 IP 是否正确
2. 检查端口 8081 是否开放
3. 检查防火墙设置

```bash
# 测试网络连通性
ping 你的服务端IP

# 测试端口
telnet 你的服务端IP 8081
```

### 问题 2: 插件未加载

```
Plugin not loaded
```

**原因:** 插件未在允许列表中

**解决:**
```bash
# 检查允许列表
openclaw config.get plugins.allow

# 确保包含 relay
openclaw config.patch '{"plugins": {"allow": ["relay"]}}'
```

### 问题 3: 连接成功但无法发送消息

**检查:**
1. 查看日志是否有错误：`openclaw logs | grep -i error`
2. 确认 Relay 服务端是否正常运行

### 问题 4: 重启后连接未自动恢复

确保 Gateway 设置为开机自启：

```bash
# 检查 Gateway 状态
openclaw gateway status

# 如果未运行
openclaw gateway start
```

## 完整配置示例

```bash
# 一行命令完成所有配置
openclaw config.patch '{
  "channels": {
    "relay": {
      "enabled": true,
      "relayUrl": "ws://192.168.111.201:8081",
      "instanceId": "tianyi",
      "instanceName": "天翼云Windows-冯麟"
    }
  },
  "plugins": {
    "allow": ["relay"]
  }
}'

# 重启
openclaw gateway restart
```

## 获取帮助

如有问题，请联系管理员。
