import { beforeEach, describe, expect, it } from "vitest";
import { useInventoryStore } from "./inventory";
import { mockApi, requestPaths, resetStoreTest } from "./testHelpers";

describe("useInventoryStore", () => {
  beforeEach(resetStoreTest);

  it("loads filament catalog, stock summary and selected spool events", async () => {
    const fetchMock = mockApi((path) => {
      if (path === "/filament/brands") return [{ id: 1, name: "Bambu", aliases: [], created_at: "2026-05-06T00:00:00Z", updated_at: "2026-05-06T00:00:00Z" }];
      if (path === "/filament/type-series") return [{ id: 1, brand_id: 1, material_type: "PLA", series_name: "Basic", brand_ids: [1], brands: [], sku_count: 1, spool_count: 1, created_at: "2026-05-06T00:00:00Z", updated_at: "2026-05-06T00:00:00Z" }];
      if (path === "/filament/color-mappings") return [];
      if (path === "/filament/color-mapping-gaps") return [];
      if (path === "/filament/skus") return [{ id: 1, brand_id: 1, material: "PLA", series: "Basic", color_name: "White", color_hex: "#ffffff", nominal_weight_g: 1000, filament_diameter_mm: 1.75, sealed_quantity: 2, created_at: "2026-05-06T00:00:00Z", updated_at: "2026-05-06T00:00:00Z" }];
      if (path === "/filament/spools") return [{ id: 1, sku_id: 1, sku_label: "Bambu PLA White", identity_source: "manual", status: "sealed", used_weight_g: 0, manual_quantity_protected: false, created_at: "2026-05-06T00:00:00Z", updated_at: "2026-05-06T00:00:00Z" }];
      if (path === "/filament/inventory/summary") return { totals: { skus: 1 }, skus: [], sealed_stock: [], opened_spools: [], ams_spools: [], needs_location_spools: [] };
      if (path === "/filament/spools/1/events") return { events: [{ id: 1, spool_id: 1, event_type: "created", message: "created", created_at: "2026-05-06T00:00:00Z" }] };
      throw new Error(`Unexpected request: ${path}`);
    });

    const store = useInventoryStore();
    await store.loadInventory();

    expect(store.filamentBrands[0].name).toBe("Bambu");
    expect(store.filamentSkus).toHaveLength(1);
    expect(store.selectedFilamentSpoolId).toBe(1);
    expect(store.selectedFilamentSpoolEvents?.events).toHaveLength(1);
    expect(requestPaths(fetchMock)).toContain("/filament/inventory/summary");
  });
});
