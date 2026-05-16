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

  it("labels sensor ranges and detects drying units", () => {
    const store = useAmsStore();

    expect(store.amsSensorRangeOptions[1]).toEqual({ label: "24 小时", value: "24" });
    expect(store.amsIsDrying({ dry_status_name: "drying" })).toBe(true);
    expect(store.amsIsDrying({ dry_status: "idle", dry_time: 0 })).toBe(false);
    expect(store.amsIsDrying({ dry_status: "idle", dry_time: 629 })).toBe(false);
    expect(store.amsIsDrying({ dry_status_name: "cooling", dry_time: 629 })).toBe(false);
    expect(store.amsIsDrying({ dry_time: 629 })).toBe(true);
  });

  it("saves AMS nicknames against the selected printer and reloads the label", async () => {
    const fetchMock = mockApi((path, init) => {
      if (path === "/printers/2/ams-labels/128") {
        expect(init.method).toBe("PATCH");
        expect(JSON.parse(String(init.body))).toEqual({ display_name: "P2S HT" });
        return { id: 2, printer_id: 2, ams_id: "128", display_name: "P2S HT", created_at: "", updated_at: "" };
      }
      if (path === "/printers/2/state") return {};
      if (path === "/printers/2/ams/overview") {
        return {
          summary: { ams_count: 1, slot_count: 1, loaded_count: 0, empty_count: 0, transitioning_count: 1, unknown_type_count: 0 },
          units: [{ ams_id: "128", display_name: "P2S HT", ams_type_name: "AMS HT", updated_at: "2026-05-06T00:00:00Z", slots: [] }],
        };
      }
      if (path === "/printers/2/ams/slots") return [];
      if (path === "/events?printer_id=2&limit=50") return [];
      if (path === "/filament/color-mappings") return [];
      if (path === "/printers/2/ams/128/sensor-history?hours=24") return { printer_id: 2, ams_id: "128", hours: 24, points: [], temperature: {}, humidity: {} };
      throw new Error(`Unexpected request: ${path}`);
    });
    usePrintersStore().selectedPrinterId = 2;
    const store = useAmsStore();
    store.amsLabelDrafts["128"] = " P2S HT ";
    store.amsLabelEditing["128"] = true;

    await store.saveAmsLabel({ ams_id: "128" });

    expect(requestPaths(fetchMock)[0]).toBe("/printers/2/ams-labels/128");
    expect(store.amsLabelEditing["128"]).toBe(false);
    expect(store.amsOverview?.units[0].display_name).toBe("P2S HT");
  });
});
