import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Bot,
  Boxes,
  CheckCircle2,
  Database,
  Gauge,
  GitBranch,
  KeyRound,
  LockKeyhole,
  MessageSquare,
  Network,
  Play,
  Radio,
  ScrollText,
  Settings2,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  Workflow
} from "lucide-react";
import "./styles.css";

const GATEWAY = "http://127.0.0.1:8787";

const fallbackTools = [
  { name: "filesystem", status: "on", scope: "read/write cwd", approval: "ask write", risk: "medium", description: "Read workspace files and stage approved writes." },
  { name: "shell", status: "gated", scope: "docker preferred", approval: "ask risky", risk: "medium", description: "Execute commands through policy and sandbox routing." },
  { name: "git", status: "on", scope: "repo only", approval: "ask push", risk: "low", description: "Inspect and mutate git state with approval for writes." },
  { name: "browser", status: "gated", scope: "session records", approval: "ask open", risk: "medium", description: "Record explicit browser sessions without surprise launch." },
  { name: "network", status: "gated", scope: "allowlist", approval: "ask", risk: "high", description: "Fetch remote data only after approval." },
  { name: "secrets", status: "locked", scope: "read handle", approval: "never echo", risk: "high", description: "Store secret handles without transcript echo." },
  { name: "memory", status: "on", scope: "user files", approval: "ask write", risk: "medium", description: "Search curated memory and sessions." },
  { name: "skills", status: "on", scope: "signed set", approval: "auto", risk: "low", description: "Load SKILL.md folders." },
  { name: "subagents", status: "on", scope: "isolated sessions", approval: "ask spawn", risk: "medium", description: "Spawn bounded helper sessions." },
  { name: "mcp", status: "gated", scope: "registered servers", approval: "ask connect", risk: "high", description: "Register MCP-compatible external tools." }
];

const fallbackConnectorSummary = {
  connectors: [
    { name: "slack", kind: "messaging", status: "not_configured", approval: "ask_send" },
    { name: "teams", kind: "messaging", status: "not_configured", approval: "ask_send" },
    { name: "webhook", kind: "webhook", status: "not_configured", approval: "ask_send" },
    { name: "mcp", kind: "external_tools", status: "not_configured", approval: "ask_connect" },
    { name: "browser", kind: "local_browser", status: "available_local_only", approval: "manual_open" },
    { name: "openwebui", kind: "messaging", status: "not_configured", approval: "ask_send" }
  ],
  enabled_count: 0,
  external_delivery_performed: false,
  browser_auto_launch: false
};

const fallbackGateway = {
  status: "offline",
  routeErrors: [],
  tools: fallbackTools,
  connectors: fallbackConnectorSummary,
  dashboard: {
    title: "AEGIS TERMINAL DASHBOARD",
    workspace: "gateway offline",
    terminal_first: true,
    browser_auto_launch: false,
    gateway_started: false,
    safety: { audit_chain_ok: true, audit_receipts: 0, tools: { enabled: 5, ask: 10, blocked: 1, total: 12 }, sandbox: { backend: "host-gated", host_execution_requires_approval: true } },
    runtime: { sessions: 0, tasks: 0, automations: 0, improvements: 0, subagents: 0, agent_jobs: 0, browser_sessions: 0, model_usage_records: 0 },
    model: { active_provider: "local/terminal-v0", mode: "local", browser_required: false },
    capabilities: { counts: { ready: 0, partial: 0, metadata_ready: 0, planned: 0, total: 0 }, top_gaps: [] },
    agents: { profiles: ["planner", "researcher", "implementer", "reviewer"], limits: { max_concurrency: 8, max_depth: 2, max_children: 5 } }
  },
  capabilities: { counts: { ready: 0, partial: 0, metadata_ready: 0, planned: 0, total: 0 }, gaps: [] },
  tasks: { task_count: 0, tasks: [] },
  automations: { automation_count: 0, automations: [] },
  improvements: { proposal_count: 0, proposals: [] },
  agents: { profiles: [], limits: { max_concurrency: 8, max_depth: 2, max_children: 5 } },
  contracts: { profiles: [] },
  browser: { session_count: 0, sessions: [], browser_auto_launch: false },
  model: { active_provider: "local/terminal-v0", mode: "local", routes: [] },
  usage: { count: 0, total_tokens: 0, recent: [] },
  audit: { ok: true, count: 0 },
  sessions: { sessions: [] }
};

const nav = [
  ["chat", MessageSquare],
  ["approvals", ShieldCheck],
  ["tools", TerminalSquare],
  ["connectors", Radio],
  ["audit", ScrollText],
  ["setup", KeyRound],
  ["memory", Database],
  ["skills", Sparkles],
  ["subagents", Bot],
  ["settings", Settings2]
];

const setupSteps = [
  ["choose model provider", "local/terminal-v0 active", "complete"],
  ["connect secrets handles", "environment names only, no raw values", "active"],
  ["choose execution sandbox", "Docker preferred, host fallback gated", "next"],
  ["enable tools", "network remains ask", "next"],
  ["register connectors", "messaging and browser are metadata-only", "next"],
  ["import skills", "workspace signed set only", "next"],
  ["run security check", "metadata-only readiness", "next"]
];

function App() {
  const [active, setActive] = useState("chat");
  const [composer, setComposer] = useState("/policy shell git pull origin main");
  const [events, setEvents] = useState([
    { type: "system", text: "web shell loaded; waiting for gateway hydration" },
    { type: "policy", text: "terminal-first safety: no browser auto-launch" }
  ]);
  const [gateway, setGateway] = useState(fallbackGateway);

  useEffect(() => {
    let cancelled = false;
    hydrateGateway()
      .then((payload) => {
        if (!cancelled) setGateway(payload);
      })
      .catch(() => {
        if (!cancelled) setGateway(fallbackGateway);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const counts = useMemo(() => summarizeTools(gateway.tools), [gateway.tools]);
  const dashboard = gateway.dashboard;
  const runtime = dashboard.runtime || fallbackGateway.dashboard.runtime;
  const safety = dashboard.safety || fallbackGateway.dashboard.safety;

  const send = () => {
    const action = composer.trim() || "empty command ignored";
    setEvents((items) => [
      ...items.slice(-6),
      { type: "draft", text: action },
      { type: "policy", text: "draft retained locally; approve and run from CLI/TUI" }
    ]);
    setComposer("");
  };

  return (
    <main className="shell">
      <section className="window" aria-label="AegisAgent secure console">
        <div className="chrome">
          <span className="dot red" />
          <span className="dot amber" />
          <span className="dot green" />
          <span className="title">aegisagent web --gateway 127.0.0.1:8787</span>
          <span className="mode">{gateway.status === "live" ? "gateway live" : gateway.status === "partial" ? "partial data" : "offline fallback"}</span>
        </div>

        <header className="mast">
          <div><strong>AEGIS SHIELD</strong> prompt-first governed agent</div>
          <div className="badges">
            <span>policy:enforced</span>
            <span>sandbox:{safety.sandbox?.backend || "gated"}</span>
            <span>net:ask</span>
            <span>audit:{safety.audit_chain_ok ? "ok" : "review"}</span>
          </div>
        </header>

        <div className="layout">
          <aside className="rail" aria-label="Primary views">
            {nav.map(([name, Icon]) => (
              <button key={name} className={active === name ? "selected" : ""} onClick={() => setActive(name)} title={name}>
                <Icon size={17} />
                <span>{name}</span>
              </button>
            ))}
          </aside>

          <section className="work">
            <View active={active} events={events} counts={counts} gateway={gateway} />
            <div className="footer">
              <span>GET /dashboard</span><span>GET /capabilities</span><span>GET /tasks</span><span>GET /agents/status</span>
            </div>
            <form className="composer" onSubmit={(event) => { event.preventDefault(); send(); }}>
              <label htmlFor="composer">aegis&gt;</label>
              <input id="composer" value={composer} onChange={(event) => setComposer(event.target.value)} placeholder="/policy shell require-approval risky" />
              <button type="submit"><Play size={16} /> send</button>
            </form>
          </section>

          <aside className="posture" aria-label="Security posture">
            <PanelHeader title="security posture" value={gateway.status === "live" ? "live data" : gateway.status === "partial" ? "partial data" : "fallback"} />
            <Metric icon={Gauge} label="model" value={dashboard.model?.active_provider || gateway.model.active_provider} state={dashboard.model?.mode || gateway.model.mode} />
            <Metric icon={TerminalSquare} label="tools" value={`${counts.enabled}/${counts.total} on`} state={`${counts.ask} ask`} />
            <Metric icon={GitBranch} label="workspace" value={shortPath(dashboard.workspace)} state="scoped" />
            <Metric icon={Network} label="network" value="approval gated" state="no auto-fetch" />
            <Metric icon={Radio} label="connectors" value={`${gateway.connectors.enabled_count || 0} enabled`} state="metadata only" />
            <Metric icon={LockKeyhole} label="secrets" value="redacted" state="no echo" />
            <Metric icon={ScrollText} label="audit" value={`${safety.audit_receipts || gateway.audit.count || 0} receipts`} state={safety.audit_chain_ok ? "chain ok" : "review"} />
            <div className="approval">
              <strong>approval boundary</strong>
              <span>Web is read-only for agent state. Mutations still route through explicit terminal approvals.</span>
              <span>no web mutation controls</span>
              <code>browser_auto_launch=false external_action_started=false</code>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}

function View({ active, events, counts, gateway }) {
  if (active === "tools") return <Tools tools={gateway.tools} counts={counts} />;
  if (active === "connectors") return <Connectors summary={gateway.connectors} />;
  if (active === "setup") return <Setup setup={gateway.setup} />;
  if (active === "audit") return <Audit events={events} audit={gateway.audit} />;
  if (active === "approvals") return <Approvals />;
  if (active === "memory") return <ListView title="memory search" icon={Database} rows={memoryRows(gateway)} />;
  if (active === "skills") return <ListView title="skill registry" icon={Boxes} rows={skillRows()} />;
  if (active === "subagents") return <Subagents gateway={gateway} />;
  if (active === "settings") return <Settings gateway={gateway} />;
  return <Chat events={events} gateway={gateway} />;
}

function Chat({ events, gateway }) {
  const dashboard = gateway.dashboard;
  const runtime = dashboard.runtime || fallbackGateway.dashboard.runtime;
  const gaps = Array.isArray(gateway.capabilities?.gaps) ? gateway.capabilities.gaps : [];
  return (
    <div className="chat pane">
      <PanelHeader title="session: main / branch: main" value={gateway.status === "live" ? "hydrated" : gateway.status === "partial" ? "partial" : "fallback"} />
      <div className="stat-grid">
        <Stat label="tasks" value={runtime.tasks} />
        <Stat label="agents" value={runtime.subagents} />
        <Stat label="jobs" value={runtime.agent_jobs} />
        <Stat label="browser sessions" value={runtime.browser_sessions} />
      </div>
      <p><span className="you">you</span> blend terminal Aegis and Hermes-style agent workflows.</p>
      <p><span className="aegis">aegis</span> Gateway state is now read through the same terminal stores; writes still require approval.</p>
      <div className="tool-card">
        <strong>live route: GET /dashboard</strong>
        <span>{dashboard.title}</span>
        <code>workspace={dashboard.workspace} terminal_first={String(dashboard.terminal_first)}</code>
      </div>
      <div className="approval-card">
        <strong>capability backlog</strong>
        <span>{gaps.length} open</span>
        <code>{gaps.slice(0, 3).map((gap) => `${gap.label}: ${gap.status}`).join("\n") || "no gaps loaded"}</code>
      </div>
      <div className="event-stream">
        {events.map((event, index) => <p key={`${event.type}-${index}`}><span>{event.type}</span>{event.text}</p>)}
      </div>
    </div>
  );
}

function Tools({ tools, counts }) {
  const rows = Array.isArray(tools) ? tools : fallbackTools;
  return (
    <div className="pane">
      <PanelHeader title="tools, skills, scopes" value={`${counts.enabled} enabled ${counts.ask} ask ${counts.blocked} blocked`} />
      <div className="tabs"><span className="hot">tools</span><span>skills</span><span>providers</span><span>policies</span><span>audit</span></div>
      <div className="matrix">
        <div className="head">name</div><div className="head">status</div><div className="head">scope</div><div className="head">approval</div><div className="head">risk</div><div className="head">description</div>
        {rows.flatMap((tool) => [
          <div key={`${tool.name}-name`}>{tool.name}</div>,
          <div key={`${tool.name}-status`} className={`state ${tool.status}`}>{tool.status}</div>,
          <div key={`${tool.name}-scope`}>{tool.scope}</div>,
          <div key={`${tool.name}-approval`}>{tool.approval}</div>,
          <div key={`${tool.name}-risk`} className={`state ${tool.risk}`}>{tool.risk}</div>,
          <div key={`${tool.name}-description`}>{tool.description}</div>
        ])}
      </div>
    </div>
  );
}

function Connectors({ summary }) {
  const safeSummary = summary && typeof summary === "object" ? summary : fallbackConnectorSummary;
  const connectors = Array.isArray(safeSummary.connectors) ? safeSummary.connectors : [];
  return (
    <div className="pane connectors">
      <PanelHeader title="connector readiness" value={`${safeSummary.enabled_count || 0} enabled`} />
      <div className="connector-flags">
        <span>external delivery: {safeSummary.external_delivery_performed ? "performed" : "not performed"}</span>
        <span>browser auto-launch: {safeSummary.browser_auto_launch ? "enabled" : "off"}</span>
      </div>
      <div className="connector-grid">
        {connectors.map((connector) => (
          <div className="connector-route" key={connector.name}>
            <div>
              <strong>{connector.name}</strong>
              <span>{connector.kind}</span>
            </div>
            <p>{connector.status}</p>
            <code>approval={connector.approval}</code>
          </div>
        ))}
      </div>
      <RouteList routes={["GET /connectors", "GET /connectors/doctor", "GET /setup/connectors", "GET /setup/run-checks"]} />
    </div>
  );
}

function Setup() {
  return (
    <div className="pane setup">
      <PanelHeader title="secure defaults, provider first" value="least privilege" />
      <div className="setup-grid">
        {setupSteps.map(([label, body, state], index) => (
          <div key={label} className={`step ${state}`}>
            <span>{index + 1}</span>
            <strong>{label}</strong>
            <small>{body}</small>
          </div>
        ))}
      </div>
      <div className="preview">
        <strong>security preview</strong>
        <p>provider key: redacted at source</p>
        <p>shell: ask before write</p>
        <p>network: blocked by default</p>
        <p>audit: append-only receipts</p>
      </div>
    </div>
  );
}

function Audit({ events, audit }) {
  return (
    <div className="pane audit">
      <PanelHeader title="audit receipts" value={audit.ok ? "chain ok" : "review"} />
      <div className="stat-grid">
        <Stat label="receipts" value={audit.count || 0} />
        <Stat label="metadata only" value="true" />
      </div>
      {events.map((event, index) => (
        <div className="receipt" key={index}>
          <span>#{String(index + 1).padStart(4, "0")}</span>
          <strong>{event.type}</strong>
          <p>{event.text}</p>
        </div>
      ))}
    </div>
  );
}

function Approvals() {
  return (
    <div className="pane approvals">
      <PanelHeader title="approval queue" value="terminal gated" />
      <div className="approval-card large">
        <strong>no web mutation controls</strong>
        <p>Current gateway parity routes are read-only. Approved writes, browser opens, remote pulls, and task execution stay in CLI/TUI approval flows.</p>
        <code>aegisagent tui{"\n"}/git remote pull origin main | approve{"\n"}/update origin main | approve</code>
      </div>
    </div>
  );
}

function Subagents({ gateway }) {
  const agents = gateway.agents || fallbackGateway.agents;
  const contracts = gateway.contracts || fallbackGateway.contracts;
  const rows = [
    `max concurrency ${agents.limits?.max_concurrency || 8}`,
    `max depth ${agents.limits?.max_depth || 2}`,
    `profiles ${(contracts.profiles || agents.profiles || []).length}`,
    `background jobs ${gateway.subagentJobs?.job_count || 0}`,
    `persisted subagents ${gateway.subagents?.subagent_count || 0}`
  ];
  return <ListView title="subagent queue" icon={Workflow} rows={rows} />;
}

function Settings({ gateway }) {
  const routeErrors = Array.isArray(gateway.routeErrors) ? gateway.routeErrors : [];
  return (
    <div className="pane list-view">
      <PanelHeader title="settings" value="read-only parity" />
      <RouteList routes={[
        "GET /dashboard",
        "GET /capabilities",
        "GET /capabilities/gaps",
        "GET /model/providers",
        "GET /model/doctor",
        "GET /model/usage",
        "GET /sessions",
        "GET /tasks",
        "GET /automations",
        "GET /improvements",
        "GET /agents/status",
        "GET /agents/contracts",
        "GET /subagents/jobs",
        "GET /browser/sessions"
      ]} />
      <div className="preview">
        <strong>runtime</strong>
        <p>model usage records: {gateway.usage.count || 0}</p>
        <p>browser sessions: {gateway.browser.session_count || 0}</p>
        <p>automation records: {gateway.automations.automation_count || 0}</p>
        <p>improvement proposals: {gateway.improvements.proposal_count || 0}</p>
      </div>
      {routeErrors.length > 0 && (
        <div className="preview route-list">
          <strong>hydration warnings</strong>
          {routeErrors.map((error) => <p key={error.route}>{error.route}: {error.message}</p>)}
        </div>
      )}
    </div>
  );
}

function ListView({ title, icon: Icon, rows }) {
  return (
    <div className="pane list-view">
      <PanelHeader title={title} value="ready" />
      {rows.map((row) => (
        <div className="list-row" key={row}><Icon size={16} /><span>{row}</span><CheckCircle2 size={15} /></div>
      ))}
    </div>
  );
}

function RouteList({ routes }) {
  return (
    <div className="preview route-list">
      <strong>gateway routes</strong>
      {routes.map((route) => <p key={route}>{route}</p>)}
    </div>
  );
}

function PanelHeader({ title, value }) {
  return <div className="panel-header"><strong>{title}</strong><span>{value}</span></div>;
}

function Metric({ icon: Icon, label, value, state }) {
  return (
    <div className="metric">
      <Icon size={16} />
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{state}</em>
    </div>
  );
}

function Stat({ label, value }) {
  return <div className="stat"><span>{label}</span><strong>{String(value)}</strong></div>;
}

async function hydrateGateway() {
  const routes = {
    tools: "/tools",
    connectors: "/connectors",
    dashboard: "/dashboard",
    capabilities: "/capabilities",
    tasks: "/tasks",
    automations: "/automations",
    improvements: "/improvements",
    agents: "/agents/status",
    contracts: "/agents/contracts",
    browser: "/browser/sessions",
    model: "/model/providers",
    usage: "/model/usage",
    audit: "/audit",
    sessions: "/sessions",
    subagents: "/subagents",
    subagentJobs: "/subagents/jobs"
  };
  const next = { ...fallbackGateway, status: "offline", routeErrors: [] };
  const entries = await Promise.allSettled(Object.entries(routes).map(async ([key, route]) => {
    try {
      return [key, route, await fetchJson(route)];
    } catch (error) {
      return [key, route, error];
    }
  }));
  let liveCount = 0;
  const routeErrors = [];
  for (const entry of entries) {
    if (entry.status !== "fulfilled") continue;
    const [key, route, value] = entry.value;
    if (value instanceof Error) {
      routeErrors.push({ route, message: value.message || "request failed" });
      continue;
    }
    next[key] = value;
    liveCount += 1;
  }
  next.routeErrors = routeErrors;
  next.status = liveCount === 0 ? "offline" : routeErrors.length === 0 ? "live" : "partial";
  return next;
}

async function fetchJson(route) {
  const response = await fetch(`${GATEWAY}${route}`);
  if (!response.ok) throw new Error(`${route} returned ${response.status}`);
  return response.json();
}

function summarizeTools(tools) {
  const rows = Array.isArray(tools) ? tools : fallbackTools;
  return {
    enabled: rows.filter((tool) => tool.status === "on" || tool.status === "local").length,
    ask: rows.filter((tool) => String(tool.approval).includes("ask") || tool.status === "gated").length,
    blocked: rows.filter((tool) => ["locked", "blocked"].includes(tool.status)).length,
    total: rows.length
  };
}

function shortPath(path) {
  if (!path) return "";
  const parts = String(path).split("/");
  return parts.slice(-2).join("/");
}

function memoryRows(gateway) {
  return [
    `${Array.isArray(gateway.sessions?.sessions) ? gateway.sessions.sessions.length : 0} session records visible`,
    `${gateway.tasks.task_count || 0} task records indexed`,
    "curated MEMORY.md / USER.md remain terminal-managed",
    "write actions require approval"
  ];
}

function skillRows() {
  return [
    "workspace SKILL.md scan enabled",
    "global bundles allowed after signature check",
    "risky markers quarantine skill folders",
    "skill writes audited"
  ];
}

createRoot(document.getElementById("root")).render(<App />);
