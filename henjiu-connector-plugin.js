import { WebSocket } from "ws";

// Runtime state
let _runtime = null;
let _config = null;
let _api = null;
let ws = null;
let reconnectTimer = null;
let heartbeatTimer = null;

const DEFAULT_CONFIG = {
  relayUrl: "ws://localhost:8081",
  instanceId: "cc2-openclaw",
  authToken: "cc2-connector-token-2024",
  instanceName: "CC2 OpenClaw",
};

function getRuntime() {
  if (!_runtime) {
    throw new Error("[henjiu-connector] Runtime not initialized");
  }
  return _runtime;
}

function getConfig() {
  return {
    ...DEFAULT_CONFIG,
    ...(_config?.channels?.["henjiu-connector"] || {}),
  };
}

// 插件 setup 函数 - OpenClaw 会调用这个
export function setup(api) {
  console.log('[henjiu-connector] Setting up plugin...');
  
  _api = api;
  _config = api.config;
  
  // 保存 runtime - 这是关键！
  _runtime = api.runtime;
  console.log('[henjiu-connector] Runtime available:', !!_runtime);
  
  const cfg = getConfig();
  console.log('[henjiu-connector] Config:', JSON.stringify(cfg));
  
  // 连接到 relay server
  connectRelay();
  
  console.log('[henjiu-connector] Plugin setup complete');
}

// 注册函数
export function register(api) {
  setup(api);
}

// 连接到 relay server
function connectRelay() {
  const cfg = getConfig();
  
  console.log(`[henjiu-connector] Connecting to relay: ${cfg.relayUrl} as ${cfg.instanceId}...`);
  
  ws = new WebSocket(cfg.relayUrl);
  
  ws.on('open', () => {
    console.log('[henjiu-connector] Connected to relay, registering...');
    ws.send(JSON.stringify({
      type: "register",
      id: cfg.instanceId,
      auth_token: cfg.authToken,
      name: cfg.instanceName,
    }));
    
    heartbeatTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);
  });
  
  ws.on('message', async (data) => {
    try {
      const msg = JSON.parse(data.toString());
      console.log('[henjiu-connector] Relay:', msg.type);
      
      if (msg.type === "registered") {
        console.log('[henjiu-connector] Successfully registered as', msg.instance_id);
      } else if (msg.type === "message") {
        console.log('[henjiu-connector] Received from relay:', msg.message);
        
        try {
          // 使用 OpenClaw internal API 发送消息给 agent
          const reply = await sendToOpenClawAgent(msg.message, msg.msg_id);
          console.log('[henjiu-connector] Agent reply:', reply);
          
          // 发送回复给 relay
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
              type: "reply",
              msg_id: msg.msg_id,
              message: reply || 'Message processed',
            }));
          }
        } catch (e) {
          console.log('[henjiu-connector] Error:', e.message);
          
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
              type: "reply",
              msg_id: msg.msg_id,
              message: 'Error: ' + e.message,
            }));
          }
        }
      }
    } catch (e) {
      console.log('[henjiu-connector] Parse error:', e.message);
    }
  });
  
  ws.on('close', () => {
    console.log('[henjiu-connector] Disconnected, reconnecting in 5s...');
    clearInterval(heartbeatTimer);
    reconnectTimer = setTimeout(connectRelay, 5000);
  });
  
  ws.on('error', (err) => {
    console.log('[henjiu-connector] Error:', err.message);
  });
}

// 使用 OpenClaw internal API 发送消息给 agent
async function sendToOpenClawAgent(message, msgId) {
  console.log('[henjiu-connector] Sending to agent:', message.substring(0, 50));
  
  const runtime = getRuntime();
  const core = runtime.channel;
  const config = _config;
  
  // 参考 wecom 插件的实现
  // 使用默认的 main session
  const sessionKey = "main";
  
  // 构建消息格式
  const envelopeOptions = core.reply.resolveEnvelopeFormatOptions(config);
  const previousTimestamp = core.session.readSessionUpdatedAt({
    storePath: core.session.resolveStorePath(config.session?.store, { agentId: "main" }),
    sessionKey: sessionKey,
  });
  
  const body = core.reply.formatAgentEnvelope({
    channel: "Henjiu Relay",
    from: "relay",
    timestamp: Date.now(),
    previousTimestamp,
    envelope: envelopeOptions,
    body: message,
  });
  
  const ctxPayload = core.reply.finalizeInboundContext({
    Body: body,
    RawBody: message,
    CommandBody: message,
    From: "henjiu-relay:relay",
    To: "henjiu-relay",
    SessionKey: sessionKey,
    AccountId: "default",
    ChatType: "direct",
    ConversationLabel: "Henjiu Relay",
    SenderName: "Relay",
    SenderId: "relay",
    Provider: "henjiu-relay",
    Surface: "henjiu-relay",
    OriginatingChannel: "henjiu-relay",
  });
  
  // 发送消息并等待回复
  return new Promise((resolve, reject) => {
    let replyText = '';
    let resolved = false;
    
    const finish = (text) => {
      if (resolved) return;
      resolved = true;
      resolve(text || 'Done');
    };
    
    // 超时
    const timeout = setTimeout(() => {
      console.log('[henjiu-connector] Timeout waiting for reply');
      finish(replyText || 'Message sent (timeout)');
    }, 25000);
    
    core.reply.dispatchReplyWithBufferedBlockDispatcher({
      ctx: ctxPayload,
      cfg: config,
      dispatcherOptions: {
        deliver: async (payload, info) => {
          console.log('[henjiu-connector] Deliver called, kind:', info.kind);
          if (payload.text) {
            replyText += payload.text;
          }
          if (info.kind === "final") {
            clearTimeout(timeout);
            finish(replyText || 'Done');
          }
        },
        onError: async (err, info) => {
          console.log('[henjiu-connector] Error:', err.message);
          clearTimeout(timeout);
          reject(err);
        },
      },
    });
  });
}

export default { setup, register };
