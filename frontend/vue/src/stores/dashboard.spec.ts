import { beforeEach, describe, expect, it } from "vitest";
import { useDashboardStore } from "./dashboard";
import { usePrintersStore } from "./printers";
import { mockApi, printerFixture, requestPaths, resetStoreTest } from "./testHelpers";

describe("useDashboardStore", () => {
  beforeEach(resetStoreTest);

  it("loads dashboard details and camera capabilities", async () => {
    const fetchMock = mockApi((path) => {
      if (path === "/printers/1/dashboard") {
        return {
          state: { subtask_name: "Calibration cube", mc_percent: 42 },
          device_snapshot: { derived_status: { printing: true }, camera: {}, camera_options: {}, data_coverage: {}, print_status: {} },
          recent_events: [],
          recent_print_logs: [],
        };
      }
      if (path === "/printers/1/capabilities") return { model_family: "x1", known: true, recommended_maintenance: [], visible_fields: [], evidence: {} };
      if (path === "/printers/1/camera/capabilities") return { available: true, stream_path: "/camera/mjpeg" };
      if (path === "/filament/effective-color-mappings") return [];
      throw new Error(`Unexpected request: ${path}`);
    });
    const printers = usePrintersStore();
    printers.printers = [printerFixture];
    printers.selectedPrinterId = 1;

    const store = useDashboardStore();
    await store.loadDashboard();

    expect(store.dashboard?.state?.subtask_name).toBe("Calibration cube");
    expect(store.deviceCapabilities?.known).toBe(true);
    expect(store.cameraCapabilities?.available).toBe(true);
    expect(store.cameraStreamSrc).toContain("/api/printers/1/camera/mjpeg");
    expect(requestPaths(fetchMock)).toContain("/printers/1/dashboard");
  });
});
