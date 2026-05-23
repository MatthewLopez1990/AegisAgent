import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const files = [
  "index.html",
  "src/main.jsx",
  "src/styles.css"
];

for (const file of files) {
  const body = readFileSync(resolve(root, file), "utf8");
  if (!body.trim()) {
    throw new Error(`${file} is empty`);
  }
}

const app = readFileSync(resolve(root, "src/main.jsx"), "utf8");
const requiredLabels = [
  "chat",
  "setup",
  "tools",
  "connectors",
  "approvals",
  "audit",
  "memory",
  "skills",
  "subagents",
  "settings",
  "approval boundary",
  "no web mutation controls",
  "security posture",
  "external delivery:",
  "not performed",
  "gateway live",
  "offline fallback",
  "GET /connectors",
  "GET /dashboard",
  "GET /capabilities",
  "GET /tasks",
  "GET /agents/status",
  "GET /browser/sessions",
  "GET /connectors/doctor",
  "GET /setup/connectors",
  "GET /setup/run-checks",
  "GET /capabilities/gaps",
  "GET /model/providers",
  "GET /model/doctor",
  "GET /model/usage",
  "GET /sessions",
  "GET /automations",
  "GET /improvements",
  "GET /agents/contracts",
  "GET /subagents/jobs"
];

for (const label of requiredLabels) {
  if (!app.includes(label)) {
    throw new Error(`missing required GUI label: ${label}`);
  }
}

console.log("smoke ok: AegisAgent web GUI files and required panels are present");
