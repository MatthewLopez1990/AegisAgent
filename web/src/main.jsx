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

const tools = [
  ["filesystem", "on", "read/write cwd", "ask write", "med", "4e98"],
  ["shell", "gated", "docker preferred", "ask risky", "med", "af21"],
  ["git", "on", "repo only", "ask push", "low", "90cc"],
  ["browser", "local", "localhost", "manual open", "low", "72bd"],
  ["network", "gated", "allowlist", "ask", "high", "13a0"],
  ["secrets", "locked", "read handle", "never echo", "high", "51dd"],
  ["memory", "on", "user files", "ask write", "med", "29bf"],
  ["skills", "on", "signed set", "auto", "low", "ba74"],
  ["subagents", "on", "isolated", "ask spawn", "med", "a12f"],
  ["mcp", "gated", "registered", "ask connect", "high", "f812"]
];

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

function App() {
  const [active, setActive] = useState("chat");
  const [composer, setComposer] = useState("/approve edit once --scope tui");
  const [events, setEvents] = useState([
    { type: "system", text: "gateway standby; local console state loaded" },
    { type: "policy", text: "shell read-only command allowed / audit=8f31c2" }
  ]);
  const [connected, setConnected] = useState(false);
  const [approval, setApproval] = useState("ask");
  const [connectorSummary, setConnectorSummary] = useState(fallbackConnectorSummary);

  useEffect(() => {
    const ws = new WebSocket("ws://127.0.0.1:8787/ws");
    ws.onopen = () => setConnected(true);
    ws.onmessage = (message) => {
      const payload = JSON.parse(message.data);
      setEvents((items) => [...items.slice(-7), { type: payload.type || "event", text: payload.message || JSON.stringify(payload.decision || payload) }]);
    };
    ws.onerror = () => setConnected(false);
    ws.onclose = () => setConnected(false);
    return () => ws.close();
  }, []);

  useEffect(() => {
    fetch("http://127.0.0.1:8787/connectors")
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("connector endpoint unavailable")))
      .then((payload) => setConnectorSummary(payload))
      .catch(() => setConnectorSummary(fallbackConnectorSummary));
  }, []);

  const counts = useMemo(() => ({
    enabled: tools.filter((tool) => tool[1] === "on" || tool[1] === "local").length,
    ask: tools.filter((tool) => tool[3].includes("ask") || tool[1] === "gated").length,
    blocked: tools.filter((tool) => tool[1] === "locked").length
  }), []);

  const send = () => {
    setEvents((items) => [...items.slice(-7), { type: "draft", text: composer || "empty command ignored" }]);
    setComposer("");
  };

  return (
    <main className="shell">
      <section className="window" aria-label="AegisAgent secure console">
        <div className="chrome">
          <span className="dot red" />
          <span className="dot amber" />
          <span className="dot green" />
          <span className="title">aegisagent web --workspace ~/Code/AegisAgent</span>
          <span className="mode">{connected ? "gateway live" : "local mode"}</span>
        </div>

        <header className="mast">
          <div><strong>AEGIS SHIELD</strong> prompt-first governed agent</div>
          <div className="badges">
            <span>policy:enforced</span>
            <span>sandbox:gated</span>
            <span>net:ask</span>
            <span>audit:live</span>
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
            <View active={active} events={events} counts={counts} approval={approval} setApproval={setApproval} connectorSummary={connectorSummary} />
            <div className="footer">
              <span>Tab pane</span><span>Enter select</span><span>/ command</span><span>? help</span><span>q quit</span>
            </div>
            <form className="composer" onSubmit={(event) => { event.preventDefault(); send(); }}>
              <label htmlFor="composer">aegis&gt;</label>
              <input id="composer" value={composer} onChange={(event) => setComposer(event.target.value)} placeholder="/policy shell require-approval risky" />
              <button type="submit"><Play size={16} /> send</button>
            </form>
          </section>

          <aside className="posture" aria-label="Security posture">
            <PanelHeader title="security posture" value="low risk" />
            <Metric icon={Gauge} label="model" value="local/terminal-v0" state="primary" />
            <Metric icon={TerminalSquare} label="tools" value="shell, git, files" state="gated" />
            <Metric icon={GitBranch} label="workspace" value="AegisAgent" state="scoped" />
            <Metric icon={Network} label="network" value="disabled" state="until approved" />
            <Metric icon={Radio} label="connectors" value={`${connectorSummary.enabled_count} enabled`} state="metadata only" />
            <Metric icon={LockKeyhole} label="secrets" value="vault locked" state="no echo" />
            <Metric icon={ScrollText} label="audit" value="append-only" state="chain ok" />
            <div className="approval">
              <strong>pending approval</strong>
              <span>write src/aegisagent/tui/renderer.py</span>
              <div>
                {["allow", "scope", "deny"].map((item) => (
                  <button key={item} onClick={() => setApproval(item)} className={approval === item ? "active" : ""}>{item}</button>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}

function View({ active, events, counts, approval, setApproval, connectorSummary }) {
  if (active === "tools") return <Tools counts={counts} />;
  if (active === "connectors") return <Connectors summary={connectorSummary} />;
  if (active === "setup") return <Setup />;
  if (active === "audit") return <Audit events={events} />;
  if (active === "approvals") return <Approvals approval={approval} setApproval={setApproval} />;
  if (active === "memory") return <ListView title="memory search" icon={Database} rows={["MEMORY.md curated context indexed", "USER.md operator preferences ready", "session FTS store online", "write actions require approval"]} />;
  if (active === "skills") return <ListView title="skill registry" icon={Boxes} rows={["workspace SKILL.md scan enabled", "global bundles allowed after signature check", "risky markers quarantine skill folders", "skill writes audited"]} />;
  if (active === "subagents") return <ListView title="subagent queue" icon={Workflow} rows={["max concurrency 8", "max depth 2", "max children per agent 5", "cascade stop enabled"]} />;
  if (active === "settings") return <ListView title="settings" icon={Settings2} rows={["network default ask", "host execution ask", "secret echo deny", "external delivery ask"]} />;
  return <Chat events={events} />;
}

function Chat({ events }) {
  return (
    <div className="chat pane">
      <PanelHeader title="session: main / branch: main" value="streaming" />
      <p><span className="you">you</span> tighten the setup flow and verify the local command.</p>
      <p><span className="aegis">aegis</span> I will inspect first, then ask before writes or networked tools.</p>
      <div className="tool-card">
        <strong>tool: rg --files</strong>
        <span>allowed / read-only</span>
        <code>scope=workspace risk=low policy=auto audit=8f31c2</code>
      </div>
      <div className="approval-card">
        <strong>approval required: edit file</strong>
        <span>ask</span>
        <code>target=src/aegisagent/tui/renderer.py</code>
      </div>
      <div className="event-stream">
        {events.map((event, index) => <p key={`${event.type}-${index}`}><span>{event.type}</span>{event.text}</p>)}
      </div>
    </div>
  );
}

function Tools({ counts }) {
  return (
    <div className="pane">
      <PanelHeader title="tools, skills, scopes" value={`${counts.enabled} enabled ${counts.ask} ask ${counts.blocked} blocked`} />
      <div className="tabs"><span className="hot">tools</span><span>skills</span><span>providers</span><span>policies</span><span>audit</span></div>
      <div className="matrix">
        <div className="head">name</div><div className="head">status</div><div className="head">scope</div><div className="head">approval</div><div className="head">risk</div><div className="head">receipt</div>
        {tools.flatMap((tool) => tool.map((cell, index) => <div key={`${tool[0]}-${index}`} className={index === 1 || index === 4 ? `state ${cell}` : ""}>{cell}</div>))}
      </div>
    </div>
  );
}

function Connectors({ summary }) {
  return (
    <div className="pane connectors">
      <PanelHeader title="connector readiness" value={`${summary.enabled_count} enabled`} />
      <div className="connector-flags">
        <span>external delivery: {summary.external_delivery_performed ? "performed" : "not performed"}</span>
        <span>browser auto-launch: {summary.browser_auto_launch ? "enabled" : "off"}</span>
      </div>
      <div className="connector-grid">
        {summary.connectors.map((connector) => (
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
      <div className="preview">
        <strong>gateway routes</strong>
        <p>GET /connectors</p>
        <p>GET /connectors/doctor</p>
        <p>GET /setup/connectors</p>
        <p>GET /setup/run-checks</p>
      </div>
    </div>
  );
}

function Setup() {
  return (
    <div className="pane setup">
      <PanelHeader title="secure defaults, provider first" value="least privilege" />
      <div className="setup-grid">
        {setupSteps.map(([label, body, state], index) => (
          <button key={label} className={`step ${state}`}>
            <span>{index + 1}</span>
            <strong>{label}</strong>
            <small>{body}</small>
          </button>
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

function Audit({ events }) {
  return (
    <div className="pane audit">
      <PanelHeader title="audit receipts" value="chain ok" />
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

function Approvals({ approval, setApproval }) {
  return (
    <div className="pane approvals">
      <PanelHeader title="approval queue" value="1 pending" />
      <div className="approval-card large">
        <strong>write request</strong>
        <p>target=src/aegisagent/tui/renderer.py</p>
        <p>reason=add secure setup picker and permission receipt row</p>
        <div>
          {["allow", "scope", "deny"].map((item) => (
            <button key={item} onClick={() => setApproval(item)} className={approval === item ? "active" : ""}>{item}</button>
          ))}
        </div>
      </div>
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

createRoot(document.getElementById("root")).render(<App />);
