import { beforeEach, describe, expect, it } from "vitest";
import { useAmsStore } from "./ams";
import { useEventsStore } from "./events";
import { useInventoryStore } from "./inventory";
import { usePrintersStore } from "./printers";
import { mockApi, requestPaths, resetStoreTest } from "./testHelpers";

describe("useAmsStore", () => {
  beforeEach(resetStoreTest);

  it("loads AMS overview, slots and sensor histories", async () => {
    const fetchMock = mockApi((path) => {
      if (path === "/printers/1/state") return { gcode_state: "RUNNING" };
      if (path === "/printers/1/ams/overview") {
        return {
          summary: { ams_count: 1, slot_count: 1, loaded_count: 1, empty_count: 0, transitioning_count: 0, unknown_type_count: 0 },
          units: [{ ams_id: "0", display_name: "Left AMS", ams_type_name: "AMS", updated_at: "2026-05-06T00:00:00Z", slots: [] }],
        };
      }
      if (path === "/printers/1/ams/slots") return [{ ams_id: "0", tray_id: "0", material: "PLA" }];
      if (path === "/events?printer_id=1&limit=50") return [{ id: 1, source: "mqtt", type: "ams.slot.updated", event_type: "ams.slot.updated", severity: "info", message: "updated", created_at: "2026-05-06T00:00:00Z" }];
      if (path === "/filament/color-mappings") return [{ id: 1, color_hex: "#ffffff", created_at: "2026-05-06T00:00:00Z", updated_at: "2026-05-06T00:00:00Z" }];
      if (path === "/printers/1/ams/0/sensor-history?hours=24") return { printer_id: 1, ams_id: "0", hours: 24, points: [{ sampled_at: "2026-05-06T00:00:00Z", temperature: 30, humidity: 20 }], temperature: {}, humidity: {} };
      throw new Error(`Unexpected request: ${path}`);
    });
    usePrintersStore().selectedPrinterId = 1;

    const store = useAmsStore();
    await store.loadAms();

    expect(store.amsOverview?.summary.slot_count).toBe(1);
    expect(store.amsSlots).toHaveLength(1);
    expect(store.amsSensorHistories["0"].points).toHaveLength(1);
    expect(useEventsStore().events).toHaveLength(1);
    expect(useInventoryStore().filamentColorMappings).toHaveLength(1);
    expect(requestPaths(fetchMock)).toContain("/printers/1/ams/overview");
  });
});
