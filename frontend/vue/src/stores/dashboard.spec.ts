import { beforeEach, describe, expect, it } from "vitest";
import { useDashboardStore } from "./dashboard";
import { usePrintersStore } from "./printers";
import { mockApi, printerFixture, requestPaths, resetStoreTest } from "./testHelpers";

function amsDashboard(unitCount: number) {
  return {
    state: {},
    device_snapshot: {
      ams_status: {},
      derived_status: {},
      temperatures: {},
      camera: {},
      camera_options: {},
      data_coverage: {},
      print_status: {},
    },
    ams_units: Array.from({ length: unitCount }, (_, index) => ({
      ams_id: String(index),
      ams_type_name: "AMS",
      temperature: 24,
      humidity: 2,
    })),
    ams_slots: Array.from({ length: unitCount }, (_, unitIndex) =>
      Array.from({ length: 4 }, (_, slotIndex) => ({
        ams_id: String(unitIndex),
        tray_id: String(slotIndex),
        user_tray_id: slotIndex + 1,
        material: slotIndex === 2 ? "" : "PLA",
        color: slotIndex === 0 ? "#ff0000" : "#00ff00",
        remain: slotIndex === 2 ? -1 : 32 + slotIndex,
        state_name: slotIndex === 2 ? "empty" : "loaded",
        is_active: unitIndex === 0 && slotIndex === 0,
      })),
    ).flat(),
    recent_events: [],
    recent_print_logs: [],
  };
}

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

  it("builds dual hotend temperature rows from dashboard temperatures", async () => {
    mockApi((path) => {
      if (path === "/printers/1/dashboard") {
        return {
          state: {},
          device_snapshot: {
            temperatures: {
              nozzles: [
                { key: "right_hotend", label_key: "right_hotend", current: 220, target: 220 },
                { key: "left_hotend", label_key: "left_hotend", current: 195, target: 200 },
              ],
            },
            derived_status: {},
            camera: {},
            camera_options: {},
            data_coverage: {},
            print_status: {},
          },
          recent_events: [],
          recent_print_logs: [],
        };
      }
      if (path === "/printers/1/capabilities") return { model_family: "h2d", known: true, recommended_maintenance: [], visible_fields: [], evidence: {} };
      if (path === "/printers/1/camera/capabilities") return { available: false };
      if (path === "/filament/effective-color-mappings") return [];
      throw new Error(`Unexpected request: ${path}`);
    });
    const printers = usePrintersStore();
    printers.printers = [printerFixture];
    printers.selectedPrinterId = 1;

    const store = useDashboardStore();
    await store.loadDashboard();

    expect(store.nozzleTemperatureRows).toEqual([
      { key: "right_hotend", label: "右热端", current: 220, target: 220 },
      { key: "left_hotend", label: "左热端", current: 195, target: 200 },
    ]);
    expect(store.compactHotendLabel("right_hotend", "右热端")).toBe("R");
    expect(store.compactHotendLabel("left_hotend", "左热端")).toBe("L");
  });

  it("keeps dashboard AMS units expanded by default when there are at most two units", () => {
    const store = useDashboardStore();
    store.dashboard = amsDashboard(2);

    expect(store.dashboardAmsCompactMode).toBe(false);
    expect(store.dashboardAmsUnitRows).toHaveLength(2);
    expect(store.dashboardAmsUnitCollapsed("0")).toBe(false);
    expect(store.dashboardAmsUnitCollapsed("1")).toBe(false);
  });

  it("collapses all dashboard AMS units by default when there are at least three units", () => {
    const store = useDashboardStore();
    store.dashboard = amsDashboard(3);

    expect(store.dashboardAmsCompactMode).toBe(true);
    expect(store.dashboardAmsUnitRows).toHaveLength(3);
    expect(store.dashboardAmsUnitRows.every((unit) => store.dashboardAmsUnitCollapsed(unit.key))).toBe(true);
  });

  it("toggles one dashboard AMS unit without changing the others", () => {
    const store = useDashboardStore();
    store.dashboard = amsDashboard(4);

    store.toggleDashboardAmsUnitCollapsed("1");
    expect(store.dashboardAmsUnitCollapsed("0")).toBe(true);
    expect(store.dashboardAmsUnitCollapsed("1")).toBe(false);
    expect(store.dashboardAmsUnitCollapsed("2")).toBe(true);

    store.toggleDashboardAmsUnitCollapsed("1");
    expect(store.dashboardAmsUnitCollapsed("1")).toBe(true);
  });

  it("clears dashboard AMS unit collapse overrides when the selected printer changes", () => {
    const printers = usePrintersStore();
    printers.printers = [printerFixture, { ...printerFixture, id: 2, name: "P2", serial: "SN002" }];
    printers.selectedPrinterId = 1;
    const store = useDashboardStore();
    store.dashboard = amsDashboard(4);
    store.toggleDashboardAmsUnitCollapsed("1");

    expect(store.dashboardAmsUnitCollapsed("1")).toBe(false);

    printers.selectedPrinterId = 2;

    expect(store.dashboardAmsUnitCollapsed("1")).toBe(true);
    expect(store.dashboardAmsUnitCollapseOverrides).toEqual({});
  });

  it("drops dashboard AMS unit collapse overrides for units that disappear", () => {
    const store = useDashboardStore();
    store.dashboard = amsDashboard(4);
    store.toggleDashboardAmsUnitCollapsed("3");

    expect(store.dashboardAmsUnitCollapsed("3")).toBe(false);

    store.dashboard = amsDashboard(3);
    store.dashboard = amsDashboard(4);

    expect(store.dashboardAmsUnitCollapsed("3")).toBe(true);
  });
});
