import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const read = (relative) => readFileSync(join(root, ".next", "server", "app", relative), "utf8");
const dashboard = read("astralanx/live.html");
const detail = read("astralanx/live/gen0194.html");

const requiredDashboard = [
  "Paper-trading dashboard",
  "Snapshot as of",
  "Live return",
  "Current DD",
  "Adaptive Cross-Sectional Selection",
];
const requiredDetail = [
  "Forward paper-trading",
  "Thesis, behaviour &amp; risks",
  "Rebalance timeline",
  "Download live data",
  "role=\"img\"",
];

for (const value of requiredDashboard) {
  if (!dashboard.includes(value)) throw new Error(`dashboard smoke check missing: ${value}`);
}
for (const value of requiredDetail) {
  if (!detail.includes(value)) throw new Error(`strategy smoke check missing: ${value}`);
}
if (detail.includes("<h1") && detail.includes(">gen0194</h1>")) {
  throw new Error("machine strategy id leaked into the primary page title");
}
console.log("static accessibility/content smoke checks passed");
