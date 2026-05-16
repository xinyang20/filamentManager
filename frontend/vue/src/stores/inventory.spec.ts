import { beforeEach, describe, expect, it } from "vitest";
import { nextTick } from "vue";
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

  it("sorts SKU brand and type-series selectors and filters type-series by brand", async () => {
    const store = useInventoryStore();
    store.filamentBrands = [
      { id: 2, name: "Zeta", aliases: [], created_at: "", updated_at: "" },
      { id: 1, name: "Alpha", aliases: [], created_at: "", updated_at: "" },
    ];
    store.filamentTypeSeries = [
      { id: 3, brand_id: 2, brand_name: "Zeta", material_type: "PETG", series_name: "Basic", brand_ids: [2], brands: [], sku_count: 0, spool_count: 0, created_at: "", updated_at: "" },
      { id: 2, brand_id: 1, brand_name: "Alpha", material_type: "PLA", series_name: "Matte", brand_ids: [1], brands: [], sku_count: 0, spool_count: 0, created_at: "", updated_at: "" },
      { id: 1, brand_id: 1, brand_name: "Alpha", material_type: "ABS", series_name: "ABS", brand_ids: [1], brands: [], sku_count: 0, spool_count: 0, created_at: "", updated_at: "" },
    ];

    expect(store.filamentRequiredBrandOptions.map((item) => item.label)).toEqual(["Alpha", "Zeta"]);

    store.filamentSkuForm.brand_id = 1;
    expect(store.filamentSkuTypeSeriesOptions.map((item) => item.label)).toEqual(["ABS · ABS", "PLA · Matte"]);

    store.filamentSkuForm.type_series_id = 1;
    store.filamentSkuForm.brand_id = 2;
    await nextTick();
    expect(store.filamentSkuForm.type_series_id).toBeNull();
    expect(store.filamentSkuTypeSeriesOptions.map((item) => item.label)).toEqual(["PETG · Basic"]);
  });

  it("adjusts edited SKU stock without rewriting SKU details or reloading AMS data", async () => {
    const store = useInventoryStore();
    const sku = {
      id: 1,
      brand_id: 1,
      brand_name: "Bambu",
      type_series_id: 1,
      material: "PLA",
      series: "Basic",
      color_name: "Black",
      color_hex: "000000",
      color_value: "000000",
      nominal_weight_g: 1000,
      filament_diameter_mm: 1.75,
      tray_info_idx: "",
      sealed_quantity: 3,
      note: "",
      type_series_ids: [1],
      type_series: [],
      brands: [],
      created_at: "2026-05-06T00:00:00Z",
      updated_at: "2026-05-06T00:00:00Z",
    };
    store.filamentSkus = [sku];
    store.filamentTypeSeries = [
      { id: 1, brand_id: 1, brand_name: "Bambu", material_type: "PLA", series_name: "Basic", brand_ids: [1], brands: [], sku_count: 1, spool_count: 0, created_at: "", updated_at: "" },
    ];
    store.editFilamentSku(sku);
    store.filamentSkuForm.sealed_quantity = 5;

    const fetchMock = mockApi((path, init) => {
      if (path === "/filament/skus/1/sealed-stock-adjust") {
        expect(init.method).toBe("POST");
        expect(JSON.parse(String(init.body))).toMatchObject({ delta: 2, reason: "sku edit" });
        return { ...sku, sealed_quantity: 5 };
      }
      if (path === "/filament/color-mappings") return [];
      if (path === "/filament/color-mapping-gaps") return [];
      if (path === "/filament/skus") return [{ ...sku, sealed_quantity: 5 }];
      if (path === "/filament/spools") return [];
      if (path === "/filament/inventory/summary") return { totals: { skus: 1 }, skus: [], sealed_stock: [], opened_spools: [], ams_spools: [], needs_location_spools: [] };
      throw new Error(`Unexpected request: ${path}`);
    });

    await store.saveFilamentSku();

    const calls = fetchMock.mock.calls.map(([input, init]) => ({
      path: String(input).replace(/^\/api/, ""),
      method: init?.method || "GET",
    }));
    expect(calls).not.toContainEqual({ path: "/filament/skus/1", method: "PATCH" });
    expect(calls.some((call) => call.path.includes("/ams/"))).toBe(false);
    expect(store.filamentSkus[0].sealed_quantity).toBe(5);
  });

  it("saves type series without reloading printer AMS data", async () => {
    const store = useInventoryStore();
    store.filamentTypeSeriesForm.brand_id = 1;
    store.filamentTypeSeriesForm.material_type = "PLA";
    store.filamentTypeSeriesForm.series_name = "Basic";

    const typeSeries = { id: 1, brand_id: 1, brand_name: "Bambu", material_type: "PLA", series_name: "Basic", brand_ids: [1], brands: [], sku_count: 0, spool_count: 0, created_at: "", updated_at: "" };
    const fetchMock = mockApi((path, init) => {
      if (path === "/filament/type-series" && init.method === "POST") return typeSeries;
      if (path === "/filament/brands") return [{ id: 1, name: "Bambu", aliases: [], created_at: "", updated_at: "" }];
      if (path === "/filament/type-series") return [typeSeries];
      if (path === "/filament/color-mappings") return [];
      if (path === "/filament/color-mapping-gaps") return [];
      if (path === "/filament/skus") return [];
      if (path === "/filament/spools") return [];
      if (path === "/filament/inventory/summary") return { totals: { skus: 0 }, skus: [], sealed_stock: [], opened_spools: [], ams_spools: [], needs_location_spools: [] };
      throw new Error(`Unexpected request: ${path}`);
    });

    await store.saveFilamentTypeSeries();

    const paths = requestPaths(fetchMock);
    expect(paths).toContain("/filament/type-series");
    expect(paths.some((path) => path.includes("/ams/"))).toBe(false);
    expect(store.filamentTypeSeries).toHaveLength(1);
  });
});
