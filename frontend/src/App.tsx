import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { Agent, Board, Task } from "./types";
import { AGENTS } from "./types";

function agentLabel(agent: Agent): string {
  return AGENTS.find((item) => item.id === agent)?.short ?? agent;
}

function normalizeProjectPath(path: string): string {
  const trimmed = path.trim();
  if (!trimmed) return "";
  if (trimmed.startsWith("~/")) {
    return trimmed;
  }
  return trimmed.replace(/\/+$/, "") || trimmed;
}

function projectLabel(path: string): string {
  const normalized = normalizeProjectPath(path);
  if (!normalized) return "No project";
  const parts = normalized.split("/").filter(Boolean);
  return parts[parts.length - 1] || normalized;
}

const COLLAPSED_LIMIT = 10;
const COLLAPSED_STORAGE_KEY = "att.collapsedColumns";

function taskRecency(task: Task): number {
  const stamp = task.last_seen_at || task.updated_at || task.created_at;
  const ms = stamp ? Date.parse(stamp) : 0;
  return Number.isFinite(ms) ? ms : 0;
}

function latestTasks(tasks: Task[], limit: number): Task[] {
  return [...tasks]
    .sort((a, b) => {
      if (a.live !== b.live) return a.live ? -1 : 1;
      return taskRecency(b) - taskRecency(a);
    })
    .slice(0, limit);
}

function loadCollapsedColumns(): Set<number> {
  try {
    const raw = localStorage.getItem(COLLAPSED_STORAGE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((id): id is number => typeof id === "number"));
  } catch {
    return new Set();
  }
}

function TaskCardView({ task }: { task: Task }) {
  return (
    <article
      className={`task-card${task.live ? " live" : ""}`}
      data-agent={task.agent}
    >
      <h3 className="task-title">{task.title}</h3>
      <div className="task-meta">
        <span className={`badge agent ${task.agent}`}>{agentLabel(task.agent)}</span>
        {task.project_path ? (
          <span className="badge project" title={normalizeProjectPath(task.project_path)}>
            {projectLabel(task.project_path)}
          </span>
        ) : null}
        <span className={`badge priority ${task.priority}`}>{task.priority}</span>
        {task.live ? <span className="badge live">live</span> : null}
        {task.source === "synced" ? <span className="badge synced">synced</span> : null}
      </div>
      {task.description ? <p className="task-desc">{task.description}</p> : null}
    </article>
  );
}

function BoardColumn({
  columnId,
  columnName,
  color,
  tasks,
  collapsed,
  onToggleCollapsed,
}: {
  columnId: number;
  columnName: string;
  color: string;
  tasks: Task[];
  collapsed: boolean;
  onToggleCollapsed: (columnId: number) => void;
}) {
  const canCollapse = tasks.length > COLLAPSED_LIMIT;
  const visibleTasks = collapsed && canCollapse ? latestTasks(tasks, COLLAPSED_LIMIT) : tasks;
  const hiddenCount = Math.max(0, tasks.length - visibleTasks.length);

  return (
    <section className={`column${collapsed && canCollapse ? " collapsed" : ""}`}>
      <header className="column-header">
        <h2 className="column-title">
          <span className="column-dot" style={{ background: color }} />
          {columnName}
        </h2>
        <div className="column-header-meta">
          <span className="column-count">
            {collapsed && canCollapse
              ? `${visibleTasks.length} of ${tasks.length}`
              : tasks.length}
          </span>
          {canCollapse ? (
            <button
              type="button"
              className="column-collapse-btn"
              aria-pressed={collapsed}
              title={
                collapsed
                  ? "Show all tasks in this column"
                  : `Show only the latest ${COLLAPSED_LIMIT}`
              }
              onClick={() => onToggleCollapsed(columnId)}
            >
              {collapsed ? "Expand" : "Collapse"}
            </button>
          ) : null}
        </div>
      </header>
      <div className="column-body">
        {visibleTasks.map((task) => (
          <TaskCardView key={task.id} task={task} />
        ))}
        {tasks.length === 0 ? <div className="empty-column">No tasks</div> : null}
        {hiddenCount > 0 ? (
          <button
            type="button"
            className="column-more"
            onClick={() => onToggleCollapsed(columnId)}
          >
            Show {hiddenCount} more
          </button>
        ) : null}
      </div>
    </section>
  );
}

export default function App() {
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [agentFilter, setAgentFilter] = useState<Agent | "all">("all");
  const [projectFilter, setProjectFilter] = useState<string>("all");
  const [syncMeta, setSyncMeta] = useState<{
    synced_at: string | null;
    counts: Record<string, number>;
    watching: boolean;
  } | null>(null);
  const [liveConnected, setLiveConnected] = useState(false);
  const [busyProject, setBusyProject] = useState<string | null>(null);
  const [collapsedColumns, setCollapsedColumns] = useState<Set<number>>(() =>
    loadCollapsedColumns()
  );

  function toggleCollapsed(columnId: number) {
    setCollapsedColumns((prev) => {
      const next = new Set(prev);
      if (next.has(columnId)) next.delete(columnId);
      else next.add(columnId);
      localStorage.setItem(COLLAPSED_STORAGE_KEY, JSON.stringify([...next]));
      return next;
    });
  }

  async function refresh() {
    const next = await api.getBoard();
    setBoard(next);
    setError(null);
  }

  async function refreshSyncStatus() {
    try {
      const status = await api.syncStatus();
      setSyncMeta(status);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
    refreshSyncStatus();

    const source = new EventSource("/api/events");
    source.onopen = () => setLiveConnected(true);
    source.onerror = () => setLiveConnected(false);
    source.addEventListener("board", () => {
      refresh().catch(() => undefined);
      refreshSyncStatus();
    });
    source.addEventListener("connected", () => setLiveConnected(true));

    return () => {
      source.close();
    };
  }, []);

  const hiddenProjects = board?.hidden_projects ?? [];

  const projectOptions = useMemo(() => {
    if (!board) return [];
    const counts = new Map<string, number>();
    for (const column of board.columns) {
      for (const task of column.tasks) {
        if (agentFilter !== "all" && task.agent !== agentFilter) continue;
        const key = normalizeProjectPath(task.project_path);
        counts.set(key, (counts.get(key) ?? 0) + 1);
      }
    }
    return [...counts.entries()]
      .map(([path, count]) => ({ path, count, label: projectLabel(path) }))
      .sort((a, b) => {
        if (!a.path && b.path) return 1;
        if (a.path && !b.path) return -1;
        return a.label.localeCompare(b.label);
      });
  }, [board, agentFilter]);

  useEffect(() => {
    if (projectFilter === "all") return;
    if (!projectOptions.some((option) => option.path === projectFilter)) {
      setProjectFilter("all");
    }
  }, [projectOptions, projectFilter]);

  const filteredColumns = useMemo(() => {
    if (!board) return [];
    return board.columns.map((column) => ({
      ...column,
      tasks: column.tasks.filter((task) => {
        if (agentFilter !== "all" && task.agent !== agentFilter) return false;
        if (projectFilter !== "all") {
          return normalizeProjectPath(task.project_path) === projectFilter;
        }
        return true;
      }),
    }));
  }, [board, agentFilter, projectFilter]);

  const liveCount = useMemo(() => {
    if (!board) return 0;
    return board.columns.reduce(
      (sum, column) => sum + column.tasks.filter((task) => task.live).length,
      0
    );
  }, [board]);

  async function hideProject(path: string) {
    const key = normalizeProjectPath(path);
    setBusyProject(key);
    try {
      await api.hideProject(key);
      if (projectFilter === key) setProjectFilter("all");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to hide project");
    } finally {
      setBusyProject(null);
    }
  }

  async function unhideProject(path: string) {
    const key = normalizeProjectPath(path);
    setBusyProject(key);
    try {
      await api.unhideProject(key);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restore project");
    } finally {
      setBusyProject(null);
    }
  }

  if (!board) {
    return <div className="loading">{error ? error : "Loading board…"}</div>;
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand-block">
          <h1 className="brand">Agent Task Tracker</h1>
          <p className="tagline">
            Read-only live tracking for Claude Code, Codex, Cursor, Grok, and Grok Bot.
          </p>
          <p className="sync-line">
            <span className={`pulse-dot${liveConnected ? " on" : ""}`} />
            {liveConnected ? "Live" : "Reconnecting"}
            {liveCount ? ` · ${liveCount} active` : ""}
            {syncMeta?.synced_at
              ? ` · synced ${new Date(syncMeta.synced_at).toLocaleTimeString()}`
              : ""}
          </p>
        </div>
        <div className="topbar-actions">
          <div className="filter-stack">
            <div className="agent-filters" role="group" aria-label="Filter by agent">
              <button
                type="button"
                className={`filter-chip${agentFilter === "all" ? " active" : ""}`}
                onClick={() => setAgentFilter("all")}
              >
                All agents
              </button>
              {AGENTS.map((agent) => (
                <button
                  key={agent.id}
                  type="button"
                  data-agent={agent.id}
                  className={`filter-chip${agentFilter === agent.id ? " active" : ""}`}
                  onClick={() => setAgentFilter(agent.id)}
                >
                  {agent.short}
                  {syncMeta?.counts?.[agent.id] != null
                    ? ` (${syncMeta.counts[agent.id]})`
                    : ""}
                </button>
              ))}
            </div>
            <div
              className="agent-filters project-filters"
              role="group"
              aria-label="Filter by project"
            >
              <button
                type="button"
                className={`filter-chip${projectFilter === "all" ? " active" : ""}`}
                onClick={() => setProjectFilter("all")}
              >
                All projects
              </button>
              {projectOptions.map((project) => (
                <span
                  key={project.path || "__none__"}
                  className={`filter-chip project-chip${
                    projectFilter === project.path ? " active" : ""
                  }`}
                  title={project.path || "Tasks with no project path"}
                >
                  <button
                    type="button"
                    className="project-chip-label"
                    onClick={() => setProjectFilter(project.path)}
                  >
                    {project.label}
                    {` (${project.count})`}
                  </button>
                  <button
                    type="button"
                    className="project-chip-remove"
                    aria-label={`Hide ${project.label}`}
                    title="Hide from board (local only)"
                    disabled={busyProject === project.path}
                    onClick={(event) => {
                      event.stopPropagation();
                      void hideProject(project.path);
                    }}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            {hiddenProjects.length > 0 ? (
              <div
                className="agent-filters project-filters hidden-projects"
                role="group"
                aria-label="Hidden projects"
              >
                <span className="filter-label">Hidden</span>
                {hiddenProjects.map((path) => (
                  <button
                    key={path || "__none_hidden__"}
                    type="button"
                    className="filter-chip restore-chip"
                    title={path || "No project"}
                    disabled={busyProject === normalizeProjectPath(path)}
                    onClick={() => void unhideProject(path)}
                  >
                    Restore {projectLabel(path)}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <button
            className="btn ghost"
            type="button"
            onClick={() => {
              api
                .syncNow()
                .then(() => refresh())
                .then(() => refreshSyncStatus())
                .catch((err: Error) => setError(err.message));
            }}
          >
            Sync now
          </button>
        </div>
      </header>

      {error ? <div className="status-banner">{error}</div> : null}

      <main className="board-shell">
        <div className="board">
          {filteredColumns.map((column) => (
            <BoardColumn
              key={column.id}
              columnId={column.id}
              columnName={column.name}
              color={column.color}
              tasks={column.tasks}
              collapsed={collapsedColumns.has(column.id)}
              onToggleCollapsed={toggleCollapsed}
            />
          ))}
        </div>
      </main>
    </div>
  );
}
