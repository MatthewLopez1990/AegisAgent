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
  "audit",
  "memory",
  "skills",
  "subagents",
  "settings",
  "approval required",
  "security posture",
  "external delivery:",
  "not performed",
  "GET /connectors"
];

for (const label of requiredLabels) {
  if (!app.includes(label)) {
    throw new Error(`missing required GUI label: ${label}`);
  }
}

console.log("smoke ok: AegisAgent web GUI files and required panels are present");
