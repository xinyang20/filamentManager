import { beforeEach, describe, expect, it } from "vitest";
import { useDashboardStore } from "./dashboard";
import { useNavigationStore } from "./navigation";
import { usePrintersStore } from "./printers";
import { mockApi, printerFixture, requestPaths, resetStoreTest } from "./testHelpers";

describe("useNavigationStore", () => {
  beforeEach(resetStoreTest);

  it("bootstraps printers and the active overview view", async () => {
    const fetchMock = mockApi((path) => {
      if (path === "/printers") return [printerFixture];
      if (path === "/dashboard/summary") return [{ printer: printerFixture, state: { subtask_name: "Benchy" }, device_snapshot: { derived_status: { printing: true } } }];
      throw new Error(`Unexpected request: ${path}`);
    });

    const store = useNavigationStore();
    await store.bootstrap();

    expect(store.activeView).toBe("overview");
    expect(usePrintersStore().printers).toHaveLength(1);
    expect(useDashboardStore().dashboardSummary).toHaveLength(1);
    expect(requestPaths(fetchMock)).toEqual(expect.arrayContaining(["/printers", "/dashboard/summary"]));
  });
});
