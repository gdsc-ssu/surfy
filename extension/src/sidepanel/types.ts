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
  sender: "user" | "system";
  text: string;
  timestamp: number;
}

export interface ServerMessage {
  source: "background";
  type: string;
  data?: any;
  connected?: boolean;
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
}

export type Action =
  | { type: "WS_STATUS"; connected: boolean }
  | { type: "CONNECTED"; state: any }
  | { type: "STATE_UPDATE"; data: StateUpdateData }
  | { type: "NODE_START"; node: string }
  | { type: "NODE_END"; node: string }
  | { type: "INTERRUPT"; data: InterruptData }
  | { type: "CANCELLED" }
  | { type: "ERROR"; message: string }
  | { type: "RUN_STARTED" }
  | { type: "INTERRUPT_RESOLVED" }
  | { type: "CHAT_MESSAGE"; sender: "user" | "system"; text: string };
