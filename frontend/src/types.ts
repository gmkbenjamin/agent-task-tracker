export type Agent = "claude_code" | "codex" | "cursor" | "grok" | "grok_bot";
export type Priority = "low" | "medium" | "high" | "urgent";

export interface Task {
  id: number;
  title: string;
  description: string;
  agent: Agent;
  priority: Priority;
  project_path: string;
  column_id: number;
  position: number;
  source?: string;
  external_key?: string | null;
  live?: boolean;
  last_seen_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Column {
  id: number;
  name: string;
  position: number;
  color: string;
  created_at: string;
  tasks: Task[];
}

export interface Board {
  columns: Column[];
  hidden_projects?: string[];
}

export const AGENTS: { id: Agent; label: string; short: string }[] = [
  { id: "claude_code", label: "Claude Code", short: "Claude" },
  { id: "codex", label: "ChatGPT Codex", short: "Codex" },
  { id: "cursor", label: "Cursor", short: "Cursor" },
  { id: "grok", label: "Grok", short: "Grok" },
  { id: "grok_bot", label: "Grok Bot", short: "GrokBot" },
];
