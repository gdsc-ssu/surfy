import React, { useEffect, useReducer } from "react";
import { AppState, Action, ServerMessage } from "./types";
import { ConnectionStatus } from "./components/ConnectionStatus";
import { CommandInput } from "./components/CommandInput";
import { PlanView } from "./components/PlanView";
import { InterruptPanel } from "./components/InterruptPanel";
import { ProgressBar } from "./components/ProgressBar";
import { NodeStatusBar } from "./components/NodeStatusBar";
import { ChatPanel } from "./components/ChatPanel";
import { CancelButton } from "./components/CancelButton";

const initialState: AppState = {
  connected: false,
  running: false,
  plan: null,
  routeMap: null,
  currentTaskIdx: 0,
  completedCount: 0,
  done: false,
  error: null,
  currentNode: null,
  interrupt: null,
  messages: [],
};

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "WS_STATUS":
      return { ...state, connected: action.connected };
    case "CONNECTED":
      return {
        ...state,
        connected: true,
        running: action.state?.running || false,
        plan: action.state?.plan || null,
        routeMap: action.state?.route_map || null,
        currentTaskIdx: action.state?.current_task_idx || 0,
        completedCount: action.state?.completed_count || 0,
        done: action.state?.done || false,
        error: action.state?.error || null,
      };
    case "STATE_UPDATE":
      return {
        ...state,
        plan: action.data.plan,
        currentTaskIdx: action.data.current_task_idx,
        completedCount: action.data.completed_count,
        done: action.data.done,
        error: action.data.error,
        running: !action.data.done && !action.data.error,
      };
    case "NODE_START":
      return { ...state, currentNode: action.node };
    case "NODE_END":
      return { ...state, currentNode: null };
    case "INTERRUPT":
      return { ...state, interrupt: action.data };
    case "CANCELLED":
      return { 
        ...state, 
        running: false, 
        currentNode: null,
        messages: [
          ...state.messages,
          { sender: "system", text: "Execution cancelled.", timestamp: Date.now() }
        ]
      };
    case "ERROR":
      return { 
        ...state, 
        error: action.message, 
        running: false, 
        currentNode: null,
        messages: [
          ...state.messages,
          { sender: "system", text: `Error: ${action.message}`, timestamp: Date.now() }
        ]
      };
    case "RUN_STARTED":
      return { 
        ...state, 
        running: true, 
        error: null, 
        done: false, 
        interrupt: null,
        messages: [
          ...state.messages,
          { sender: "system", text: "Execution started.", timestamp: Date.now() }
        ]
      };
    case "INTERRUPT_RESOLVED":
      return { ...state, interrupt: null };
    case "CHAT_MESSAGE":
      return {
        ...state,
        messages: [
          ...state.messages,
          { sender: action.sender, text: action.text, timestamp: Date.now() },
        ],
      };
    default:
      return state;
  }
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);

  useEffect(() => {
    const handleMessage = (message: ServerMessage) => {
      if (message.source !== "background") return;

      switch (message.type) {
        case "ws_status":
          dispatch({ type: "WS_STATUS", connected: message.connected || false });
          break;
        case "connected":
          dispatch({ type: "CONNECTED", state: message.data?.state });
          break;
        case "state_update":
          dispatch({ type: "STATE_UPDATE", data: message.data });
          break;
        case "node_start":
          dispatch({ type: "NODE_START", node: message.data?.node || "unknown" });
          break;
        case "node_end":
          dispatch({ type: "NODE_END", node: message.data?.node || "unknown" });
          break;
        case "interrupt":
          dispatch({ type: "INTERRUPT", data: message.data });
          break;
        case "cancelled":
          dispatch({ type: "CANCELLED" });
          break;
        case "error":
          dispatch({ type: "ERROR", message: message.data?.message || "Unknown error" });
          break;
        case "chat":
          if (message.data?.message) {
            dispatch({ type: "CHAT_MESSAGE", sender: "system", text: message.data.message });
          }
          break;
      }
    };

    chrome.runtime.onMessage.addListener(handleMessage);

    // Request initial status
    chrome.runtime.sendMessage({
      source: "sidepanel",
      payload: { type: "get_status" },
    });

    return () => {
      chrome.runtime.onMessage.removeListener(handleMessage);
    };
  }, []);

  // Intercept run messages to update local state optimistically
  useEffect(() => {
    const handleOutgoingMessage = (message: any) => {
      if (message.source === "sidepanel" && message.payload?.type === "run") {
        dispatch({ type: "RUN_STARTED" });
      } else if (message.source === "sidepanel" && message.payload?.type === "resume") {
        dispatch({ type: "INTERRUPT_RESOLVED" });
      }
    };
    
    // We can't easily intercept chrome.runtime.sendMessage globally, 
    // but we can rely on the server's state_update or node_start to update UI.
    // The CommandInput and InterruptPanel components will send the messages.
    // We'll just let the server responses drive the state.
  }, []);

  const totalTasks = state.plan?.tasks.length || 0;

  const handleChatSend = (text: string) => {
    dispatch({ type: "CHAT_MESSAGE", sender: "user", text });
    
    if (state.interrupt) {
      chrome.runtime.sendMessage({
        source: "sidepanel",
        payload: {
          type: "resume",
          data: {
            interrupt_type: state.interrupt.interrupt_type,
            value: { approved: true, modification: text },
          },
        },
      });
      dispatch({ type: "INTERRUPT_RESOLVED" });
    } else {
      chrome.runtime.sendMessage({
        source: "sidepanel",
        payload: {
          type: "chat",
          data: { message: text },
        },
      });
    }
  };

  const handleCancel = () => {
    chrome.runtime.sendMessage({
      source: "sidepanel",
      payload: { type: "cancel", data: {} },
    });
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50 font-sans">
      {/* Header */}
      <header className="flex-shrink-0 bg-white border-b border-gray-200 p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-blue-600">Surfy</h1>
          <ConnectionStatus connected={state.connected} />
        </div>
        <CommandInput disabled={!state.connected || state.running} />
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden flex flex-col p-4 relative">
        {state.error && (
          <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-md mb-4 text-sm">
            <span className="font-bold">Error:</span> {state.error}
          </div>
        )}

        <PlanView
          plan={state.plan}
          routeMap={state.routeMap}
          currentTaskIdx={state.currentTaskIdx}
        />

        {state.interrupt && <InterruptPanel interrupt={state.interrupt} />}

        <ChatPanel 
          messages={state.messages} 
          onSend={handleChatSend} 
          isInterruptActive={!!state.interrupt}
          isRunning={state.running}
        />
      </main>

      {/* Footer */}
      <footer className="flex-shrink-0 bg-white border-t border-gray-200 p-4 flex flex-col gap-2">
        <ProgressBar completed={state.completedCount} total={totalTasks} />
        <NodeStatusBar currentNode={state.currentNode} />
        <CancelButton disabled={!state.running} onCancel={handleCancel} />
      </footer>
    </div>
  );
}
