import { useEffect, useReducer, useRef, useState } from "react";
import { AppState, Action, ServerMessage } from "./types";
import { ConnectionStatus } from "./components/ConnectionStatus";
import { ProgressBar } from "./components/ProgressBar";
import { CancelButton } from "./components/CancelButton";
import { UnifiedInput } from "./components/UnifiedInput";
import { MessageList } from "./components/MessageList";

const NODE_INFO: Record<string, { label: string; icon: string }> = {
  cache_lookup: { label: "Cache lookup", icon: "💾" },
  research: { label: "Researching topic", icon: "🔎" },
  scout: { label: "Scouting website", icon: "🗺️" },
  planner: { label: "Creating plan", icon: "📋" },
  plan_approval: { label: "Waiting for approval", icon: "✋" },
  actor: { label: "Executing task", icon: "🎬" },
  evaluator: { label: "Evaluating result", icon: "✅" },
  completion_check: { label: "Checking completion", icon: "🏁" },
  human_gateway: { label: "Waiting for input", icon: "💬" },
  cache_store: { label: "Saving to cache", icon: "💾" },
  report: { label: "Generating report", icon: "📝" },
};

function getNodeInfo(node: string) {
  return NODE_INFO[node] || { label: node, icon: "⚙️" };
}

function parseServerTimestamp(ts?: string): number {
  if (!ts) return Date.now();
  const parsed = new Date(ts).getTime();
  return isNaN(parsed) ? Date.now() : parsed;
}

function formatDuration(startMs: number, endMs: number) {
  const diffSec = Math.max(0, Math.round((endMs - startMs) / 1000));
  if (diffSec < 60) {
    return `${diffSec}s`;
  }
  const min = Math.floor(diffSec / 60);
  const sec = diffSec % 60;
  return `${min}m ${sec}s`;
}

function buildNodeEndDetail(node: string, updates?: any): string | undefined {
  if (node === "cache_lookup") {
    return updates?.cache_hit ? "Cache hit ⚡" : "Cache miss";
  }
  if (node === "research" && updates?.research_result) {
    const r = updates.research_result;
    const sourceCount = r.sources?.length || 0;
    const header = sourceCount > 0 ? `${sourceCount}개 소스 발견` : "검색 완료";
    const summary = r.summary ? `${header}\n\n${r.summary}` : header;
    return summary;
  }
  if (node === "planner" && updates?.plan?.anchor) {
    return `Plan: ${updates.plan.anchor}`;
  }
  if (node === "evaluator" && updates?.eval_result) {
    const r = updates.eval_result;
    return r.success ? "✓ Pass" : `✗ ${r.reason || "Failed"}`;
  }
  if (node === "scout" && updates?.route_map) {
    const rm = updates.route_map;
    const stepCount = rm.steps?.length || 0;
    return stepCount > 0 ? `${stepCount}단계 탐색 → ${rm.final_url || "완료"}` : rm.scout_summary || "탐색 완료";
  }
  if (node === "actor" && updates?.last_page_state?.url) {
    return `→ ${updates.last_page_state.url}`;
  }
  return undefined;
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
      const timestamp = Date.now();
      let newMessages = [...state.messages];

      const prevPlan = state.plan ? JSON.stringify(state.plan) : null;
      const nextPlan = action.data.plan ? JSON.stringify(action.data.plan) : null;
      if (action.data.plan && prevPlan !== nextPlan) {
        newMessages.push({
          type: "plan",
          sender: "agent",
          text: "",
          timestamp,
          planData: {
            anchor: action.data.plan.anchor,
            tasks: action.data.plan.tasks,
            anchor_rationale: action.data.plan.anchor_rationale,
          },
        });
      }

      if (action.data.done && !action.data.error) {
        const last = newLog[newLog.length - 1];
        if (!last || last.node !== "__done") {
          if (last && last.status === "running") {
            newLog[newLog.length - 1] = { ...last, endedAt: timestamp, status: "done" as const };
          }
          newLog.push({
            node: "__done",
            label: "Completed",
            icon: "✅",
            startedAt: timestamp,
            endedAt: timestamp,
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
        messages: newMessages,
      };
    }
    case "NODE_START": {
      const info = getNodeInfo(action.node);
      const timestamp = parseServerTimestamp(action.serverTimestamp);
      const newLog = [...state.activityLog];
      const lastIdx = newLog.length - 1;
      if (lastIdx >= 0 && newLog[lastIdx].node === "__loading") {
        newLog[lastIdx] = { ...newLog[lastIdx], endedAt: timestamp, status: "done" as const };
      }
      let startDetail: string | undefined;
      if (action.node === "planner" && state.routeMap) {
        const parts: string[] = [];
        if (state.routeMap.final_url) {
          parts.push(`Scout: ${state.routeMap.final_url}`);
        }
        if (state.routeMap.scout_summary) {
          parts.push(state.routeMap.scout_summary);
        }
        startDetail = parts.join(" · ") || undefined;
      }
      newLog.push({
        node: action.node,
        label: info.label,
        icon: info.icon,
        startedAt: timestamp,
        endedAt: null,
        status: "running" as const,
        detail: startDetail,
      });
      return {
        ...state,
        currentNode: action.node,
        activityLog: newLog,
        messages: [
          ...state.messages,
          {
            type: "activity",
            sender: "agent",
            text: "",
            timestamp,
            activityData: {
              node: action.node,
              label: info.label,
              icon: info.icon,
              status: "running",
              detail: startDetail,
            },
          },
        ],
      };
    }
    case "NODE_END": {
      const timestamp = parseServerTimestamp(action.serverTimestamp);
      const detail = buildNodeEndDetail(action.node, action.updates);
      const updatedLog = state.activityLog.map((entry, idx) => {
        if (idx === state.activityLog.length - 1 && entry.status === "running") {
          return { ...entry, endedAt: timestamp, status: "done" as const, detail };
        }
        return entry;
      });

      const updatedMessages = [...state.messages];
      for (let i = updatedMessages.length - 1; i >= 0; i--) {
        const msg = updatedMessages[i];
        if (msg.type === "activity" && msg.activityData?.status === "running") {
          const duration = formatDuration(msg.timestamp, timestamp);

          updatedMessages[i] = {
            ...msg,
            activityData: {
              ...msg.activityData,
              status: "done",
              detail,
              duration,
            },
          };
          break;
        }
      }

      let newRouteMap = state.routeMap;
      if (action.node === "scout" && action.updates?.route_map) {
        newRouteMap = action.updates.route_map;
      }
      return {
        ...state,
        currentNode: null,
        activityLog: updatedLog,
        routeMap: newRouteMap,
        messages: updatedMessages,
      };
    }
    case "INTERRUPT":
      return {
        ...state,
        interrupt: action.data,
        messages: [
          ...state.messages,
          {
            type: "interrupt",
            sender: "agent",
            text: "",
            timestamp: Date.now(),
            interruptData: action.data,
          },
        ],
      };
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
      {
      const timestamp = Date.now();
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
            startedAt: timestamp,
            endedAt: null,
            status: "running" as const,
          },
        ],
        messages: [
          ...state.messages,
          {
            sender: "user",
            text: action.command,
            timestamp,
          },
          {
            type: "activity",
            sender: "agent",
            text: "",
            timestamp: timestamp + 1,
            activityData: {
              node: "__loading",
              label: "Starting...",
              icon: "⏳",
              status: "running",
            },
          },
        ]
      };
      }
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
    case "CHAT_REPORT":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            type: "report",
            sender: "agent",
            text: "",
            timestamp: Date.now(),
            reportData: { summary: action.text },
          },
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
      const newMessages = [...state.messages];
      for (let i = newMessages.length - 1; i >= 0; i--) {
        const msg = newMessages[i];
        if (msg.type === "activity" && msg.activityData?.status === "running") {
          const subSteps = msg.activityData.subSteps ? [...msg.activityData.subSteps] : [];
          subSteps.push({
            step_number: action.data.step_number,
            description: action.data.description,
            action_type: action.data.action_type,
          });
          newMessages[i] = {
            ...msg,
            activityData: {
              ...msg.activityData,
              subSteps,
            },
          };
          break;
        }
      }
      return { ...state, activityLog: newLog, messages: newMessages };
    }
    case "CLEAR":
      return { ...initialState, connected: state.connected };
    default:
      return state;
  }
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [autoApprove, setAutoApprove] = useState(() => localStorage.getItem("surfy_auto_approve") === "true");
  const [useCache, setUseCache] = useState(() => localStorage.getItem("surfy_use_cache") !== "false");

  const autoApproveRef = useRef(autoApprove);
  useEffect(() => { autoApproveRef.current = autoApprove; }, [autoApprove]);

  const useCacheRef = useRef(useCache);
  useEffect(() => { useCacheRef.current = useCache; }, [useCache]);

  const toggleAutoApprove = () => {
    setAutoApprove((prev) => {
      const next = !prev;
      localStorage.setItem("surfy_auto_approve", String(next));
      return next;
    });
  };

  const toggleCache = () => {
    setUseCache((prev) => {
      const next = !prev;
      localStorage.setItem("surfy_use_cache", String(next));
      return next;
    });
  };

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
          dispatch({ type: "NODE_START", node: message.data?.node || "unknown", serverTimestamp: message.timestamp });
          break;
        case "node_end":
          dispatch({ type: "NODE_END", node: message.data?.node || "unknown", updates: message.data?.updates, serverTimestamp: message.timestamp });
          break;
        case "interrupt":
          dispatch({ type: "INTERRUPT", data: message.data });
          if (autoApproveRef.current && message.data?.interrupt_type !== "human_gateway" && message.data?.interrupt_type !== "auth_verify_failed") {
            setTimeout(() => {
              // completion_check: approved=false means "Complete", approved=true means "Request More"
              const isCompletionCheck = message.data?.interrupt_type === "completion_check";
              const approvedValue = isCompletionCheck ? false : true;

              chrome.runtime.sendMessage({
                source: "sidepanel",
                payload: {
                  type: "resume",
                  data: {
                    interrupt_type: message.data?.interrupt_type,
                    value: { approved: approvedValue, modification: null },
                  },
                },
              });
              dispatch({ type: "INTERRUPT_RESOLVED" });
              dispatch({ type: "CHAT_MESSAGE", sender: "system", text: "Auto-approved" });
            }, 300);
          }
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
            dispatch({ type: "CHAT_REPORT", text: message.data.message });
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
    chrome.runtime.sendMessage({
      source: "sidepanel",
      payload: { type: "run", data: { command, use_cache: useCacheRef.current } },
    });
  };

  const totalTasks = state.plan?.tasks.length || 0;

  const handleChatSend = (text: string, interruptValue?: { approved?: boolean; modification?: string | null }) => {
    dispatch({ type: "CHAT_MESSAGE", sender: "user", text });
    
    if (state.interrupt) {
      const value = interruptValue || { approved: true, modification: text };
      chrome.runtime.sendMessage({
        source: "sidepanel",
        payload: {
          type: "resume",
          data: {
            interrupt_type: state.interrupt.interrupt_type,
            value,
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

  const handleClear = () => {
    dispatch({ type: "CLEAR" });
    chrome.runtime.sendMessage({
      source: "sidepanel",
      payload: { type: "clear", data: {} },
    });
  };

  const handleRetry = () => {
    chrome.runtime.sendMessage({
      source: "sidepanel",
      payload: { type: "reconnect" },
    });
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50 font-sans">
      <header className="flex-shrink-0 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <h1 className="text-xl font-bold text-blue-600">Surfy</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleCache}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              useCache
                ? "bg-amber-100 text-amber-700 hover:bg-amber-200"
                : "text-gray-400 hover:text-gray-600 hover:bg-gray-100"
            }`}
            title={useCache ? "Cache ON — 캐시 사용" : "Cache OFF — 항상 새로 검색"}
          >
            {useCache ? "💾 Cache" : "🔄 Fresh"}
          </button>
          <button
            onClick={toggleAutoApprove}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              autoApprove
                ? "bg-blue-100 text-blue-700 hover:bg-blue-200"
                : "text-gray-400 hover:text-gray-600 hover:bg-gray-100"
            }`}
            title={autoApprove ? "Auto-approve ON — 플랜 자동 승인" : "Auto-approve OFF — 수동 승인"}
          >
            {autoApprove ? "⚡ Auto" : "✋ Manual"}
          </button>
          {(state.done || state.error || state.activityLog.length > 0) && !state.running && (
            <button
              onClick={handleClear}
              className="px-2 py-1 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
              title="세션 초기화"
            >
              Clear
            </button>
          )}
          <ConnectionStatus connected={state.connected} onRetry={handleRetry} />
        </div>
      </header>

      <div className="flex-1 min-h-0 overflow-y-auto p-3">
        <MessageList
          messages={state.messages}
          onInterruptAction={(value) => {
            const fallbackText =
              typeof value?.modification === "string" && value.modification.length > 0
                ? value.modification
                : value?.approved === true
                  ? "Approved"
                  : "Stop";
            handleChatSend(fallbackText, value);
          }}
        />
      </div>

      <div className="flex-shrink-0 bg-white border-t border-gray-200 p-3 flex flex-col gap-2">
        <UnifiedInput state={state} onRun={handleRunStarted} onChat={handleChatSend} />
        <div className="flex items-center justify-between mt-1">
          <ProgressBar completed={state.completedCount} total={totalTasks} />
          {state.running && <CancelButton compact disabled={!state.running} onCancel={handleCancel} />}
        </div>
      </div>
    </div>
  );
}
