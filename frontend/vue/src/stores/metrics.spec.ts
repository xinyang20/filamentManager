import { beforeEach, describe, expect, it } from "vitest";
import { useMetricsStore } from "./metrics";
import { usePrintersStore } from "./printers";
import { mockApi, requestPaths, resetStoreTest } from "./testHelpers";

describe("useMetricsStore", () => {
  beforeEach(resetStoreTest);

  it("loads metric samples for the selected range", async () => {
    const fetchMock = mockApi((path) => {
      if (path.startsWith("/printers/1/metrics?")) return [{ id: 1, metric: "temperature.nozzle", value_float: 215, unit: "celsius", sampled_at: "2026-05-06T00:00:00Z" }];
      throw new Error(`Unexpected request: ${path}`);
    });
    usePrintersStore().selectedPrinterId = 1;

    const store = useMetricsStore();
    store.metricRange = "1h";
    await store.loadMetrics();

    expect(store.metrics).toHaveLength(1);
    expect(store.metricGroups.temperatures[0].value_float).toBe(215);
    expect(requestPaths(fetchMock)[0]).toContain("bucket=minute");
  });
});
