export interface Plan {
  anchor: string;
  tasks: TaskItem[];
  anchor_rationale: string;
}

export interface TaskItem {
  description: string;
  success_criteria: {
    url_contains: string | null;
    text_visible: string | null;
    description: string;
  };
  target_url: string | null;
}

export interface RouteStep {
  url: string;
  title: string;
  action_taken: string;
  observed_elements: string[];
  notes: string;
}

export interface RouteMap {
  steps: RouteStep[];
  final_url: string;
  scout_summary: string;
}

export interface StateUpdateData {
  plan: Plan | null;
  current_task_idx: number;
  completed_count: number;
  done: boolean;
  error: string | null;
}

export interface InterruptData {
  interrupt_type: "plan_approval" | "human_gateway" | "completion_check";
  payload: Record<string, any>;
}

export interface ChatMessage {
  sender: "user" | "system" | "agent";
  text: string;
  timestamp: number;
  type?: "text" | "activity" | "plan" | "interrupt" | "report";
  activityData?: {
    node: string;
    label: string;
    icon: string;
    status: "running" | "done";
    detail?: string;
    duration?: string;
    subSteps?: { step_number: number; description: string; action_type?: string }[];
  };
  planData?: {
    anchor: string;
    tasks: TaskItem[];
    anchor_rationale?: string;
  };
  interruptData?: InterruptData;
  reportData?: {
    summary: string;
  };
}

export interface ServerMessage {
  source: "background";
  type: string;
  data?: any;
  connected?: boolean;
}

export interface ActivityLogEntry {
  node: string;
  label: string;
  icon: string;
  startedAt: number;
  endedAt: number | null;
  status: "running" | "done";
  detail?: string;
  subSteps?: { step_number: number; description: string; action_type?: string }[];
}

export interface AppState {
  connected: boolean;
  running: boolean;
  plan: Plan | null;
  routeMap: RouteMap | null;
  currentTaskIdx: number;
  completedCount: number;
  done: boolean;
  error: string | null;
  currentNode: string | null;
  interrupt: InterruptData | null;
  messages: ChatMessage[];
  activityLog: ActivityLogEntry[];
  lastCommand: string | null;
}

export type Action =
  | { type: "WS_STATUS"; connected: boolean }
  | { type: "CONNECTED"; state: any; running: boolean }
  | { type: "STATE_UPDATE"; data: StateUpdateData }
  | { type: "NODE_START"; node: string }
  | { type: "NODE_END"; node: string; updates?: any }
  | { type: "INTERRUPT"; data: InterruptData }
  | { type: "CANCELLED" }
  | { type: "ERROR"; message: string }
  | { type: "RUN_STARTED"; command: string }
  | { type: "INTERRUPT_RESOLVED" }
  | { type: "CHAT_MESSAGE"; sender: "user" | "system" | "agent"; text: string }
  | { type: "CHAT_REPORT"; text: string }
  | { type: "STEP_PROGRESS"; data: { node: string; step_number: number; description: string; action_type?: string } }
  | { type: "CLEAR" };
