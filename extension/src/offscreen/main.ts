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

let socket: WebSocket | null = null;
let reconnectDelay = INITIAL_RECONNECT_DELAY;
let heartbeatTimer: number | null = null;

function connect() {
  console.log(`Connecting to Surfy server at ${WS_URL}...`);
  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    console.log("WebSocket connected");
    reconnectDelay = INITIAL_RECONNECT_DELAY;
    sendUpdateToServiceWorker(true);
    startHeartbeat();
  };

  socket.onmessage = (event) => {
    try {
      const parsedMessage = JSON.parse(event.data);
      chrome.runtime.sendMessage({
        source: "offscreen",
        ...parsedMessage
      });
    } catch (error) {
      console.error("Failed to parse WebSocket message:", error);
    }
  };

  socket.onclose = () => {
    console.log("WebSocket disconnected");
    sendUpdateToServiceWorker(false);
    stopHeartbeat();
    scheduleReconnect();
  };

  socket.onerror = (error) => {
    console.error("WebSocket error:", error);
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
  } as OffscreenMessage);
}

// Listen for messages from Service Worker
chrome.runtime.onMessage.addListener((msg: ToOffscreenMessage) => {
  if (msg.target === "offscreen" && socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(msg.payload));
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
