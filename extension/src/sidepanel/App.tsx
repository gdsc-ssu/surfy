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
import { ActivityLog } from "./components/ActivityLog";

const NODE_INFO: Record<string, { label: string; icon: string }> = {
  research: { label: "Researching topic", icon: "🔎" },
  scout: { label: "Scouting website", icon: "🗺️" },
  planner: { label: "Creating plan", icon: "📋" },
  plan_approval: { label: "Waiting for approval", icon: "✋" },
  actor: { label: "Executing task", icon: "🎬" },
  evaluator: { label: "Evaluating result", icon: "✅" },
  completion_check: { label: "Checking completion", icon: "🏁" },
  human_gateway: { label: "Waiting for input", icon: "💬" },
};

function getNodeInfo(node: string) {
  return NODE_INFO[node] || { label: node, icon: "⚙️" };
}

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
  activityLog: [],
  lastCommand: null,
};

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "WS_STATUS":
      if (!action.connected) {
        // Disconnected — reset running state so inputs aren't stuck disabled
        return { ...state, connected: false, running: false, currentNode: null };
      }
      return { ...state, connected: true };
    case "CONNECTED":
      return {
        ...state,
        connected: true,
        running: action.running,
        plan: action.state?.plan || null,
        routeMap: action.state?.route_map || null,
        currentTaskIdx: action.state?.current_task_idx || 0,
        completedCount: action.state?.completed_count || 0,
        done: action.state?.done || false,
        error: action.state?.error || null,
      };
    case "STATE_UPDATE": {
      const newLog = [...state.activityLog];
      if (action.data.done && !action.data.error) {
        const last = newLog[newLog.length - 1];
        if (!last || last.node !== "__done") {
          if (last && last.status === "running") {
            newLog[newLog.length - 1] = { ...last, endedAt: Date.now(), status: "done" as const };
          }
          newLog.push({
            node: "__done",
            label: "Completed",
            icon: "✅",
            startedAt: Date.now(),
            endedAt: Date.now(),
            status: "done" as const,
          });
        }
      }
      return {
        ...state,
        plan: action.data.plan,
        currentTaskIdx: action.data.current_task_idx,
        completedCount: action.data.completed_count,
        done: action.data.done,
        error: action.data.error,
        running: !action.data.done && !action.data.error,
        activityLog: newLog,
      };
    }
    case "NODE_START": {
      const info = getNodeInfo(action.node);
      const newLog = [...state.activityLog];
      const lastIdx = newLog.length - 1;
      if (lastIdx >= 0 && newLog[lastIdx].node === "__loading") {
        newLog[lastIdx] = { ...newLog[lastIdx], endedAt: Date.now(), status: "done" as const };
      }
      newLog.push({
        node: action.node,
        label: info.label,
        icon: info.icon,
        startedAt: Date.now(),
        endedAt: null,
        status: "running" as const,
      });
      return {
        ...state,
        currentNode: action.node,
        activityLog: newLog,
      };
    }
    case "NODE_END": {
      const updatedLog = state.activityLog.map((entry, idx) => {
        if (idx === state.activityLog.length - 1 && entry.status === "running") {
          let detail: string | undefined;
          const updates = action.updates;
          if (action.node === "planner" && updates?.plan?.anchor) {
            detail = `Plan: ${updates.plan.anchor}`;
          } else if (action.node === "evaluator" && updates?.eval_result) {
            const r = updates.eval_result;
            detail = r.success ? "✓ Pass" : `✗ ${r.reason || "Failed"}`;
          } else if (action.node === "scout" && updates?.route_map?.scout_summary) {
            detail = updates.route_map.scout_summary;
          } else if (action.node === "actor" && updates?.last_page_state?.url) {
            detail = `→ ${updates.last_page_state.url}`;
          }
          return { ...entry, endedAt: Date.now(), status: "done" as const, detail };
        }
        return entry;
      });
      return { ...state, currentNode: null, activityLog: updatedLog };
    }
    case "INTERRUPT":
      return { ...state, interrupt: action.data };
    case "CANCELLED":
      return { 
        ...state, 
        running: false, 
        currentNode: null,
        activityLog: [
          ...state.activityLog,
          {
            node: "__cancelled",
            label: "Execution cancelled",
            icon: "🚫",
            startedAt: Date.now(),
            endedAt: Date.now(),
            status: "done" as const,
          },
        ],
        messages: [
          ...state.messages,
          { sender: "system", text: "Execution cancelled.", timestamp: Date.now() }
        ]
      };
    case "ERROR": {
      const errLog = [...state.activityLog];
      const lastIdx = errLog.length - 1;
      if (lastIdx >= 0 && errLog[lastIdx].node === "__loading") {
        errLog[lastIdx] = { ...errLog[lastIdx], endedAt: Date.now(), status: "done" as const };
      }
      return { 
        ...state, 
        error: action.message, 
        running: false, 
        currentNode: null,
        activityLog: errLog,
        messages: [
          ...state.messages,
          { sender: "system", text: `Error: ${action.message}`, timestamp: Date.now() }
        ]
      };
    }
    case "RUN_STARTED":
      return { 
        ...state, 
        running: true, 
        error: null, 
        done: false, 
        interrupt: null,
        lastCommand: action.command,
        activityLog: [
          {
            node: "__loading",
            label: "Starting agent...",
            icon: "⏳",
            startedAt: Date.now(),
            endedAt: null,
            status: "running" as const,
          },
        ],
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
    case "STEP_PROGRESS": {
      const newLog = [...state.activityLog];
      // Find the last running entry that matches the node
      for (let i = newLog.length - 1; i >= 0; i--) {
        if (newLog[i].node === action.data.node && newLog[i].status === "running") {
          const entry = newLog[i];
          const subSteps = entry.subSteps ? [...entry.subSteps] : [];
          subSteps.push({
            step_number: action.data.step_number,
            description: action.data.description,
            action_type: action.data.action_type,
          });
          newLog[i] = { ...entry, subSteps };
          break;
        }
      }
      return { ...state, activityLog: newLog };
    }
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
          dispatch({ type: "CONNECTED", state: message.data?.state, running: message.data?.running || false });
          break;
        case "state_update":
          dispatch({ type: "STATE_UPDATE", data: message.data });
          break;
        case "node_start":
          dispatch({ type: "NODE_START", node: message.data?.node || "unknown" });
          break;
        case "node_end":
          dispatch({ type: "NODE_END", node: message.data?.node || "unknown", updates: message.data?.updates });
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
        case "step_progress":
          dispatch({
            type: "STEP_PROGRESS",
            data: {
              node: message.data?.node || "unknown",
              step_number: message.data?.step_number || 0,
              description: message.data?.description || "",
              action_type: message.data?.action_type,
            },
          });
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

  const handleRunStarted = (command: string) => {
    dispatch({ type: "RUN_STARTED", command });
  };

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

  const handleRetry = () => {
    chrome.runtime.sendMessage({
      source: "sidepanel",
      payload: { type: "reconnect" },
    });
  };

  const handleCommandRetry = () => {
    if (!state.lastCommand) return;
    dispatch({ type: "RUN_STARTED", command: state.lastCommand });
    chrome.runtime.sendMessage({
      source: "sidepanel",
      payload: { type: "run", data: { command: state.lastCommand } },
    });
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50 font-sans">
      {/* Header */}
      <header className="flex-shrink-0 bg-white border-b border-gray-200 p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-blue-600">Surfy</h1>
          <ConnectionStatus connected={state.connected} onRetry={handleRetry} />
        </div>
        <CommandInput disabled={!state.connected || state.running} onRun={handleRunStarted} />
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden flex flex-col p-4 relative">
        {state.done && !state.error && (
          <div className="bg-green-50 border border-green-200 text-green-700 p-3 rounded-md mb-4 text-sm flex items-center gap-2">
            <span className="text-lg">✓</span>
            <span className="font-medium">완료</span>
          </div>
        )}

        {state.error && (
          <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-md mb-4 text-sm flex items-center justify-between">
            <div>
              <span className="font-bold">Error:</span> {state.error}
            </div>
            {state.lastCommand && (
              <button
                onClick={handleCommandRetry}
                className="ml-3 px-3 py-1 bg-red-600 text-white text-xs rounded-md hover:bg-red-700 transition-colors flex-shrink-0"
              >
                Retry
              </button>
            )}
          </div>
        )}

        <ActivityLog entries={state.activityLog} />

        <PlanView
          plan={state.plan}
          routeMap={state.routeMap}
          currentTaskIdx={state.currentTaskIdx}
        />

        {state.interrupt && (
          <InterruptPanel 
            interrupt={state.interrupt} 
            onResolved={() => dispatch({ type: "INTERRUPT_RESOLVED" })}
          />
        )}

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
