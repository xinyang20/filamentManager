import { beforeEach, describe, expect, it } from "vitest";
import { useMaintenanceStore } from "./maintenance";
import { usePrintersStore } from "./printers";
import { mockApi, resetStoreTest } from "./testHelpers";

describe("useMaintenanceStore", () => {
  beforeEach(resetStoreTest);

  it("loads maintenance overview and selected printer items", async () => {
    mockApi((path) => {
      if (path === "/maintenance/overview") return { total_items: 1, due_count: 0, soon_count: 0, ok_count: 1, printers: [], items: [] };
      if (path === "/printers/1/maintenance") {
        return [{
          id: 1,
          printer_id: 1,
          maintenance_type: { id: 1, code: "carbon_rods", name: "Carbon rods", interval_type: "hours", default_interval: 250 },
          enabled: true,
          interval: 250,
          last_performed_print_hours: 10,
          current_print_hours: 20,
          hours_since_last: 10,
          hours_until_due: 240,
          due_status: "ok",
          history_count: 1,
        }];
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    usePrintersStore().selectedPrinterId = 1;

    const store = useMaintenanceStore();
    await store.loadMaintenance();

    expect(store.maintenanceOverview?.ok_count).toBe(1);
    expect(store.maintenanceItems).toHaveLength(1);
    expect(store.maintenanceHealthPercent).toBe(100);
  });
});
