import { spawn } from "node:child_process";
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";

const port = 3137;
const origin = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, ["node_modules/next/dist/bin/next", "start", "-p", String(port)], {
  stdio: ["ignore", "pipe", "pipe"],
});
let serverLog = "";
server.stdout.on("data", (chunk) => { serverLog += chunk; });
server.stderr.on("data", (chunk) => { serverLog += chunk; });

async function ready() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(`${origin}/astralanx/live`);
      if (response.ok) return;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Next server did not become ready:\n${serverLog}`);
}

let browser;
let context;
try {
  await ready();
  browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
    args: ["--no-sandbox"],
  });
  context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  for (const route of ["/astralanx/live", "/astralanx/live/gen0194"] ) {
    await page.goto(`${origin}${route}`, { waitUntil: "networkidle" });
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    if (results.violations.length) {
      throw new Error(`${route} accessibility violations:\n${results.violations.map((item) => {
        const nodes = item.nodes.map((node) => `  ${node.target.join(" ")}: ${node.failureSummary}`).join("\n");
        return `${item.id}: ${item.help}\n${nodes}`;
      }).join("\n")}`);
    }
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (overflow > 1) throw new Error(`${route} has ${overflow}px horizontal overflow at 1280px`);
    if (!(await page.getByRole("heading", { level: 1 }).first().isVisible())) {
      throw new Error(`${route} lost its visible primary heading`);
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ["/astralanx/live", "/astralanx/live/gen0194"] ) {
    await page.goto(`${origin}${route}`, { waitUntil: "networkidle" });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (overflow > 1) throw new Error(`${route} has ${overflow}px horizontal overflow at 390px`);
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${origin}/astralanx/live/gen0194`, { waitUntil: "networkidle" });
  const checkbox = page.getByRole("checkbox").first();
  await checkbox.focus();
  const before = await checkbox.isChecked();
  await page.keyboard.press("Space");
  if ((await checkbox.isChecked()) === before) throw new Error("chart control did not respond to keyboard input");
  console.log("rendered-page accessibility and layout checks passed");
} finally {
  await context?.close();
  await browser?.close();
  server.kill("SIGTERM");
}
