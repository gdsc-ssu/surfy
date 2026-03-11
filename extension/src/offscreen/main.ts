// Server message types (from surfy/domain/models/messages.py)
type ServerMessageType = 
  | "connected" | "node_start" | "node_end" | "state_update" 
  | "interrupt" | "cancelled" | "dom_highlight" | "error" | "heartbeat";

// Client message types
type ClientMessageType = "run" | "resume" | "chat" | "cancel" | "heartbeat";

// Internal extension message routing
interface OffscreenMessage {
  source: "offscreen";
  type: string;
  data?: unknown;
  connected?: boolean;
}

interface SidePanelMessage {
  source: "sidepanel";
  payload: any;
}

interface ToOffscreenMessage {
  target: "offscreen";
  payload: any;
}

const WS_URL = "ws://localhost:8765/ws";
const HEARTBEAT_INTERVAL = 30000;
const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;
const MAX_PENDING_MESSAGES = 50;

let socket: WebSocket | null = null;
let reconnectDelay = INITIAL_RECONNECT_DELAY;
let heartbeatTimer: number | null = null;
const pendingMessages: string[] = [];

function connect() {
  console.log(`Connecting to Surfy server at ${WS_URL}...`);
  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    console.log("WebSocket connected");
    reconnectDelay = INITIAL_RECONNECT_DELAY;
    sendUpdateToServiceWorker(true);
    startHeartbeat();

    while (pendingMessages.length > 0) {
      socket!.send(pendingMessages.shift()!);
    }
  };

  socket.onmessage = (event) => {
    try {
      const parsedMessage = JSON.parse(event.data);
      chrome.runtime.sendMessage({
        source: "offscreen",
        ...parsedMessage
      }).catch(() => { /* no receiver — side panel closed */ });
    } catch {
      console.warn("Failed to parse WebSocket message");
    }
  };

  socket.onclose = () => {
    console.log("WebSocket disconnected");
    sendUpdateToServiceWorker(false);
    stopHeartbeat();
    scheduleReconnect();
  };

  socket.onerror = () => {
    console.warn("WebSocket connection error — will reconnect");
    socket?.close();
  };
}

function scheduleReconnect() {
  console.log(`Reconnecting in ${reconnectDelay / 1000}s...`);
  setTimeout(connect, reconnectDelay);
  reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
}

function startHeartbeat() {
  stopHeartbeat();
  heartbeatTimer = window.setInterval(() => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "heartbeat", data: {} }));
    }
  }, HEARTBEAT_INTERVAL);
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}

function sendUpdateToServiceWorker(connected: boolean) {
  chrome.runtime.sendMessage({
    source: "offscreen",
    type: "ws_status",
    connected
  } as OffscreenMessage).catch(() => { /* side panel not open */ });
}

// Listen for messages from Service Worker
chrome.runtime.onMessage.addListener((msg: ToOffscreenMessage) => {
  if (msg.target !== "offscreen") return;
  
  if (msg.payload?.type === "reconnect") {
    console.log("Manual reconnect requested");
    if (socket) {
      socket.close();
    }
    reconnectDelay = INITIAL_RECONNECT_DELAY;
    connect();
    return;
  }
  
  const serialized = JSON.stringify(msg.payload);
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(serialized);
  } else {
    if (pendingMessages.length < MAX_PENDING_MESSAGES) {
      pendingMessages.push(serialized);
    } else {
      console.warn("Pending message queue full — dropping message");
    }
  }
});

// Clean shutdown
window.addEventListener("unload", () => {
  stopHeartbeat();
  if (socket) {
    socket.close();
  }
});

// Initial connection
connect();
