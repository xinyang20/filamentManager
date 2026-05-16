import { beforeEach, describe, expect, it } from "vitest";
import { nextTick } from "vue";
import { usePrintLogStore } from "./printLog";
import { mockApi, requestPaths, resetStoreTest } from "./testHelpers";

async function flushAsync() {
  await nextTick();
  await Promise.resolve();
  await Promise.resolve();
}

describe("usePrintLogStore", () => {
  beforeEach(resetStoreTest);

  it("loads paged logs, summary and analytics", async () => {
    const fetchMock = mockApi((path) => {
      if (path === "/print-log?limit=25&offset=0") return { total: 1, limit: 25, offset: 0, items: [{ id: 1, printer_id: 1, status: "succeeded" }] };
      if (path === "/print-log/summary") return { total: 1, running: 0, succeeded: 1, failed: 0, cancelled: 0, total_duration_seconds: 120, by_printer: [] };
      if (path === "/print-log/analytics?") return { total: 1, running: 0, succeeded: 1, failed: 0, cancelled: 0, total_duration_seconds: 120, by_printer: [], bucket: "day" };
      throw new Error(`Unexpected request: ${path}`);
    });

    const store = usePrintLogStore();
    await store.loadPrintLog();

    expect(store.printLogs[0].status).toBe("succeeded");
    expect(store.printLogSummary?.succeeded).toBe(1);
    expect(store.printLogAnalytics?.bucket).toBe("day");
    expect(requestPaths(fetchMock)).toContain("/print-log?limit=25&offset=0");
  });

  it("automatically reloads when filter criteria change", async () => {
    const fetchMock = mockApi((path) => {
      if (path.startsWith("/print-log?")) return { total: 0, limit: 25, offset: 0, items: [] };
      if (path === "/print-log/summary") return { total: 0, running: 0, succeeded: 0, failed: 0, cancelled: 0, total_duration_seconds: 0, by_printer: [] };
      if (path.startsWith("/print-log/analytics?")) return { total: 0, running: 0, succeeded: 0, failed: 0, cancelled: 0, total_duration_seconds: 0, by_printer: [], bucket: "day" };
      throw new Error(`Unexpected request: ${path}`);
    });

    const store = usePrintLogStore();
    store.printLogFilters.offset = 25;
    store.printLogFilters.printer_id = "2";
    await flushAsync();

    expect(store.printLogFilters.offset).toBe(0);
    expect(requestPaths(fetchMock)).toContain("/print-log?limit=25&offset=0&printer_id=2");
  });
});
