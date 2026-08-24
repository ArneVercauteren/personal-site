import "server-only";
import fs from "node:fs";
import path from "node:path";

export const deploymentVersions = {
  schema: 1,
  evaluator: "darwin-dsl-v1",
  costModel: "darwin-sliced-execution-v1",
  calendar: "observed-us-sessions-v1",
  eligibility: "causal-us-equities-v1",
} as const;

export interface DeploymentMetadata {
  schema_version: 1;
  strategy_id: string;
  display_name: string;
  formula_hash: string;
  cost_model_hash: string;
  engine_build_id: string;
  evaluator_version: typeof deploymentVersions.evaluator;
  cost_model_version: typeof deploymentVersions.costModel;
  calendar_version: typeof deploymentVersions.calendar;
  eligibility_version: typeof deploymentVersions.eligibility;
  training_cutoff: string;
  oos_window: { start: string; end: string };
  deployment_session: string;
  generated_at: string;
  data_sources: { research: string; forward_paper: string };
  cadence: {
    unit: "trading_sessions";
    interval: number;
    anchor_review_session: string;
    execution: "next_session_open";
  };
  bundle_hash: string;
}

type Bundle = {
  schema_version?: unknown;
  id?: unknown;
  name?: unknown;
  deployed_on?: unknown;
  rebalance_cadence_days?: unknown;
  rebalance_cadence_unit?: unknown;
  rebalance_transition_anchor?: unknown;
  cost_model?: unknown;
  formula?: unknown;
  deployment?: unknown;
};

const sha256 = /^[a-f0-9]{64}$/;
const isoDate = /^\d{4}-\d{2}-\d{2}$/;

function record(value: unknown, label: string): Record<string, unknown> {
  if (value == null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

export function validateDeploymentBundle(raw: unknown): asserts raw is Bundle & {
  deployment: DeploymentMetadata;
} {
  const bundle = record(raw, "deployment bundle") as Bundle;
  if (bundle.schema_version !== deploymentVersions.schema) {
    throw new Error("unsupported or missing deployment schema version");
  }
  const deployment = record(bundle.deployment, "deployment metadata");
  if (deployment.schema_version !== deploymentVersions.schema) {
    throw new Error("unsupported nested deployment schema version");
  }
  if (deployment.strategy_id !== bundle.id || deployment.display_name !== bundle.name) {
    throw new Error("deployment identity does not match strategy identity");
  }
  if (deployment.deployment_session !== bundle.deployed_on) {
    throw new Error("deployment session does not match deployed_on");
  }
  if (
    deployment.evaluator_version !== deploymentVersions.evaluator
    || deployment.cost_model_version !== deploymentVersions.costModel
    || deployment.calendar_version !== deploymentVersions.calendar
    || deployment.eligibility_version !== deploymentVersions.eligibility
  ) {
    throw new Error("deployment uses unsupported semantic versions");
  }
  if (
    !sha256.test(String(deployment.formula_hash))
    || !sha256.test(String(deployment.cost_model_hash))
    || !sha256.test(String(deployment.bundle_hash))
  ) {
    throw new Error("deployment hashes must be SHA-256");
  }
  if (typeof deployment.engine_build_id !== "string" || !deployment.engine_build_id) {
    throw new Error("deployment engine build id is required");
  }
  const cadence = record(deployment.cadence, "deployment cadence");
  if (
    cadence.unit !== "trading_sessions"
    || cadence.execution !== "next_session_open"
    || cadence.interval !== bundle.rebalance_cadence_days
    || cadence.anchor_review_session !== bundle.rebalance_transition_anchor
    || bundle.rebalance_cadence_unit !== "trading_days"
  ) {
    throw new Error("deployment cadence semantics do not match strategy");
  }
  if (!isoDate.test(String(cadence.anchor_review_session))) {
    throw new Error("deployment cadence anchor must be an ISO date");
  }
  const oos = record(deployment.oos_window, "deployment OOS window");
  if (
    !isoDate.test(String(deployment.training_cutoff))
    || !isoDate.test(String(oos.start))
    || !isoDate.test(String(oos.end))
    || String(deployment.training_cutoff) >= String(oos.start)
    || String(oos.start) > String(oos.end)
  ) {
    throw new Error("deployment training/OOS chronology is invalid");
  }
  const sources = record(deployment.data_sources, "deployment data sources");
  if (typeof sources.research !== "string" || typeof sources.forward_paper !== "string") {
    throw new Error("deployment data-source provenance is incomplete");
  }
  record(bundle.formula, "deployment formula");
  record(bundle.cost_model, "deployment cost model");
}

/** Validate every committed open bundle during static builds. */
export function validateCommittedDeploymentBundles(): void {
  const directory = path.join(process.cwd(), "paper_trading", "strategies");
  const files = fs.readdirSync(directory).filter((name) => name.endsWith(".json"));
  if (!files.length) throw new Error("no committed deployment bundles found");
  for (const file of files) {
    const bundle = JSON.parse(fs.readFileSync(path.join(directory, file), "utf8")) as unknown;
    validateDeploymentBundle(bundle);
  }
}
