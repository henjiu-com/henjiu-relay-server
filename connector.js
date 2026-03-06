import { WebSocket } from "ws";

const args = process.argv.slice(2);
const config = {
  url: args[0] || "ws://localhost:8081",
  instanceId: args[1] || "cc2-openclaw",
  authToken: args[2] || "cc2-connector-token-2024",
  instanceName: args[3] || "CC2 OpenClaw",
  openclawUrl: "http://localhost:3000",
  openclawToken: args[4] || "12009cdbdb68a564c87ab5fa60364399c09ffb255eea01cd",
};

console.log(`Connecting to relay: ${config.url} as ${config.instanceId}...`);

let ws = null;
let reconnectTimer = null;
let heartbeatTimer = null;

// 通过 OpenClaw Tools Invoke API 发送消息
async function sendViaOpenClaw(message, target, msgId) {
  try {
    const response = await fetch(`${config.openclawUrl}/tools/invoke`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${config.openclawToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        tool: 'message',
        args: {
          action: 'send',
          channel: 'telegram',
          target: target || '5960098927',
          message: message,
        }
      }),
    });
    
    const result = await response.json();
    
    if (result.ok) {
      // 解析结果获取 messageId
      let reply = 'Message sent';
      try {
        const content = JSON.parse(result.result?.content?.[0]?.text || '{}');
        if (content.messageId) {
          reply = `Message sent (ID: ${content.messageId})`;
        }
      } catch (e) {}
      return { reply };
    } else {
      return { error: result.error?.message || 'Unknown error' };
    }
  } catch (error) {
    return { error: `Request failed: ${error.message}` };
  }
}

function connect() {
  ws = new WebSocket(config.url);
  
  ws.on('open', () => {
    console.log('Connected to relay, registering...');
    ws.send(JSON.stringify({
      type: "register",
      id: config.instanceId,
      auth_token: config.authToken,
      name: config.instanceName,
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
      console.log('Relay:', msg.type);
      
      if (msg.type === "registered") {
        console.log('Successfully registered as', msg.instance_id);
        console.log('Ready to relay messages via Tools Invoke API');
      } else if (msg.type === "message") {
        console.log('Received:', msg.message);
        
        const result = await sendViaOpenClaw(msg.message, msg.target, msg.msg_id);
        console.log('Result:', result.reply || result.error);
        
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: "reply",
            msg_id: msg.msg_id,
            message: result.reply || result.error || 'Done',
          }));
        }
      }
    } catch (e) {
      console.log('Error:', e.message);
    }
  });
  
  ws.on('close', () => {
    console.log('Disconnected from relay, reconnecting in 5s...');
    clearInterval(heartbeatTimer);
    reconnectTimer = setTimeout(connect, 5000);
  });
  
  ws.on('error', (err) => {
    console.log('Relay error:', err.message);
  });
}

connect();

process.on('SIGINT', () => {
  console.log('Shutting down...');
  clearTimeout(reconnectTimer);
  clearInterval(heartbeatTimer);
  if (ws) ws.close();
  process.exit(0);
});
