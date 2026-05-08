import { beforeEach, describe, expect, it } from "vitest";
import { useMetricsStore } from "./metrics";
import { usePrintersStore } from "./printers";
import { mockApi, requestPaths, resetStoreTest } from "./testHelpers";

describe("useMetricsStore", () => {
  beforeEach(resetStoreTest);

  it("loads metric samples for the selected range", async () => {
    const fetchMock = mockApi((path) => {
      if (path.includes("group=temperature")) return [{ id: 1, metric: "temperature.nozzle", value_float: 215, unit: "celsius", sampled_at: "2026-05-06T00:00:00Z" }];
      if (path.includes("group=fan")) return [{ id: 2, metric: "fan.cooling_fan_speed.percent", value_float: 53, unit: "percent", sampled_at: "2026-05-06T00:00:00Z" }];
      if (path.includes("group=ams")) return [{ id: 4, metric: "ams.128.humidity", value_float: 12, unit: "percent", sampled_at: "2026-05-06T00:00:00Z" }];
      throw new Error(`Unexpected request: ${path}`);
    });
    usePrintersStore().selectedPrinterId = 1;

    const store = useMetricsStore();
    store.metricRange = "1h";
    await store.loadMetrics();

    expect(store.metrics).toHaveLength(3);
    expect(store.metricGroups.temperatures[0].value_float).toBe(215);
    expect(store.metricGroups.ams[0].metric).toBe("ams.128.humidity");
    expect(requestPaths(fetchMock)).toHaveLength(3);
    expect(requestPaths(fetchMock)[0]).toContain("bucket=minute");
    expect(requestPaths(fetchMock)).toEqual(expect.arrayContaining([
      expect.stringContaining("group=temperature"),
      expect.stringContaining("group=fan"),
      expect.stringContaining("group=ams"),
    ]));
    expect(requestPaths(fetchMock)).not.toEqual(expect.arrayContaining([expect.stringContaining("group=wifi")]));
  });

  it("uses hourly aggregation for long ranges", async () => {
    const fetchMock = mockApi((path) => {
      if (path.startsWith("/printers/1/metrics?")) return [];
      throw new Error(`Unexpected request: ${path}`);
    });
    usePrintersStore().selectedPrinterId = 1;

    const store = useMetricsStore();
    store.metricRange = "24h";
    await store.loadMetrics();

    expect(store.metricBucket()).toBe("hour");
    expect(requestPaths(fetchMock)[0]).toContain("bucket=hour");
  });
});
