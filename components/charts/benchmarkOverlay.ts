import type { Benchmark, EquityPoint } from "@/lib/data";

export interface BenchmarkOverlayPoint {
  d: string;
  vBenchmark: number | null;
}

export function scaledBenchmarkOverlay(
  points: EquityPoint[],
  benchmark?: Benchmark,
): { overlay: BenchmarkOverlayPoint[]; values: number[] } {
  if (!benchmark || points.length === 0 || benchmark.equity_curve.length === 0) {
    return { overlay: points.map((p) => ({ d: p.d, vBenchmark: null })), values: [] };
  }

  const byDate = new Map(benchmark.equity_curve.map((p) => [p.d, p.v]));
  const firstAligned = points.find((p) => byDate.get(p.d) != null);
  if (!firstAligned) {
    return { overlay: points.map((p) => ({ d: p.d, vBenchmark: null })), values: [] };
  }

  const baseBenchmark = byDate.get(firstAligned.d);
  if (!baseBenchmark || baseBenchmark <= 0) {
    return { overlay: points.map((p) => ({ d: p.d, vBenchmark: null })), values: [] };
  }

  const values: number[] = [];
  const overlay = points.map((p) => {
    const benchmarkValue = byDate.get(p.d);
    const vBenchmark =
      benchmarkValue != null ? (benchmarkValue / baseBenchmark) * firstAligned.v : null;
    if (vBenchmark != null) values.push(vBenchmark);
    return { d: p.d, vBenchmark };
  });

  return { overlay, values };
}
