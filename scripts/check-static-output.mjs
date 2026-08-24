import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const read = (relative) => readFileSync(join(root, ".next", "server", "app", relative), "utf8");
const dashboard = read("astralanx/live.html");
const detail = read("astralanx/live/gen0194.html");
const strategySpec = JSON.parse(
  readFileSync(join(root, "paper_trading", "strategies", "gen0194.json"), "utf8"),
);

const requiredDashboard = [
  "Paper-trading dashboard",
  "Snapshot as of",
  "Live return",
  "Current DD",
  strategySpec.name,
  strategySpec.blurb,
];
const requiredDetail = [
  strategySpec.name,
  strategySpec.blurb,
  strategySpec.thesis,
  strategySpec.expected_behavior,
  ...strategySpec.risks,
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
for (const value of ["What failure looks like", ...strategySpec.failure_modes]) {
  if (detail.includes(value)) throw new Error(`strategy smoke check found removed content: ${value}`);
}
console.log("static accessibility/content smoke checks passed");
