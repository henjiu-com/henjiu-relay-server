/**
 * OpenClaw Relay Channel Plugin
 * 
 * 用法:
 * 1. 复制到扩展目录: ~/.openclaw/extensions/henjiu-connector/
 * 2. 在 config 中启用
 */

import { WebSocket } from "ws";

// 默认配置
const DEFAULT_CONNECTOR_URL = "ws://localhost:8081";

export const relayChannelPlugin = {
  id: "henjiu-connector",
  meta: {
    id: "henjiu-connector",
    label: "Henjiu Relay",
    selectionLabel: "Henjiu Relay",
    docsPath: "",
    blurb: "Connect to OpenClaw Relay server via WebSocket",
    aliases: ["henjiu-connector"],
  },
  capabilities: {
    chatTypes: ["direct", "group"],
    reactions: false,
    threads: false,
    media: false,
    nativeCommands: false,
    blockStreaming: false,
  },
  reload: { configPrefixes: ["channels.henjiu-connector"] },
  configSchema: {
    schema: {
      $schema: "http://json-schema.org/draft-07/schema#",
      type: "object",
      additionalProperties: false,
      properties: {
        enabled: {
          type: "boolean",
          description: "Enable Relay channel",
          default: false,
        },
        connectorUrl: {
          type: "string",
          description: "Relay WebSocket server URL",
          default: "ws://localhost:8081",
        },
        instanceId: {
          type: "string",
          description: "Unique instance ID for this client",
          default: "henjiu-connector-client",
        },
        instanceName: {
          type: "string",
          description: "Display name for this instance",
          default: "OpenClaw",
        },
        authToken: {
          type: "string",
          description: "Authentication token (must match server config)",
          default: "",
        },
      },
    },
  },

  async setup(api) {
    const config = api.config.channels?.henjiu-connector || {};
    
    if (!config.enabled) {
      api.logger.info("Relay channel: disabled");
      return;
    }

    const connectorUrl = config.connectorUrl || DEFAULT_CONNECTOR_URL;
    const instanceId = config.instanceId || "henjiu-connector-client";
    const instanceName = config.instanceName || "OpenClaw";
    const authToken = config.authToken || "";

    api.logger.info(`Relay channel: connecting to ${connectorUrl} as ${instanceId}`);

    let ws = null;
    let reconnectTimer = null;
    let heartbeatTimer = null;

    // 连接函数
    function connect() {
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        return;
      }

      try {
        ws = new WebSocket(connectorUrl);

        ws.on("open", () => {
          api.logger.info(`Relay channel: connected to ${connectorUrl}`);
          
          // 发送注册消息 (包含认证Token)
          ws.send(JSON.stringify({
            type: "register",
            instance_id: instanceId,
            auth_token: authToken,
            info: {
              name: instanceName,
            },
          }));

          // 启动心跳
          heartbeatTimer = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "ping" }));
            }
          }, 30000);
        });

        ws.on("message", (data) => {
          try {
            const msg = JSON.parse(data.toString());
            handleMessage(api, msg);
          } catch (e) {
            api.logger.warn(`Relay channel: invalid JSON: ${data}`);
          }
        });

        ws.on("close", () => {
          api.logger.warn("Relay channel: connection closed");
          scheduleReconnect();
        });

        ws.on("error", (err) => {
          api.logger.error(`Relay channel: error: ${err.message}`);
        });
      } catch (err) {
        api.logger.error(`Relay channel: failed to connect: ${err.message}`);
        scheduleReconnect();
      }
    }

    function scheduleReconnect() {
      if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
        heartbeatTimer = null;
      }
      if (!reconnectTimer) {
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          connect();
        }, 5000);
      }
    }

    // 处理收到的消息
    function handleMessage(api, msg) {
      const { type, message, channel, from, target } = msg;

      if (type === "registered") {
        api.logger.info(`Relay channel: registered as ${msg.instance_id || instanceId}`);
        return;
      }

      if (type === "ping" || type === "pong") {
        return;
      }

      if (type === "message" && message) {
        // 收到来自 Relay 的消息，转发给 OpenClaw
        api.logger.info(`Relay channel: received message from ${from}: ${message.substring(0, 50)}`);
        
        // 使用 injectInbound 注入消息
        if (api.injectInbound) {
          api.injectInbound({
            channel: "relay",
            senderId: from || "relay",
            chatId: from || "relay",
            message,
            channelType: "direct",
          });
        }
      }
    }

    // 注册 outbound - 发送消息到 Relay
    if (api.registerOutbound) {
      api.registerOutbound({
        name: "relay",
        async send(message, ctx) {
          if (ws && ws.readyState === WebSocket.OPEN) {
            const channel = ctx?.target?.channel || "telegram";
            const target = ctx?.target?.userId || ctx?.target?.chatId || null;
            
            ws.send(JSON.stringify({
              type: "message",
              message,
              channel,
              target,
              from: instanceId,
              timestamp: Date.now(),
            }));
            
            return { id: `relay-${Date.now()}`, status: "sent" };
          } else {
            api.logger.warn("Relay channel: not connected");
            throw new Error("Relay not connected");
          }
        },
      });
    }

    // 启动连接
    connect();

    // 返回 cleanup 函数
    return () => {
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) ws.close();
      api.logger.info("Relay channel: stopped");
    };
  },
};

export default relayChannelPlugin;
