import { beforeEach, describe, expect, it } from "vitest";
import { nextTick } from "vue";
import { useInventoryStore } from "./inventory";
import { useI18nStore } from "./i18n";
import { mockApi, requestPaths, resetStoreTest } from "./testHelpers";

describe("useInventoryStore", () => {
  beforeEach(resetStoreTest);

  it("loads filament catalog, stock summary and selected spool events", async () => {
    const fetchMock = mockApi((path) => {
      if (path === "/filament/brands") return [{ id: 1, name: "Bambu", aliases: [], created_at: "2026-05-06T00:00:00Z", updated_at: "2026-05-06T00:00:00Z" }];
      if (path === "/filament/type-series") return [{ id: 1, brand_id: 1, material_type: "PLA", series_name: "Basic", brand_ids: [1], brands: [], sku_count: 1, spool_count: 1, created_at: "2026-05-06T00:00:00Z", updated_at: "2026-05-06T00:00:00Z" }];
      if (path === "/filament/color-mappings") return [];
      if (path === "/filament/effective-color-mappings") return [];
      if (path === "/filament/bambu-official-color-mappings") return [{ id: -1, brand_name: "Bambu Lab", material_type: "PETG", series_name: "HF", tray_info_idx: "GFG02", color_hex: "F9DFB9", official_color_code: "33401", official_color_type: "single", official_color_names: { zh: "奶油白", en: "Cream" }, official_colors: ["F9DFB9"] }];
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
    expect(store.bambuOfficialColorMappings[0].official_color_code).toBe("33401");
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

  it("filters SKUs by type first, then series", async () => {
    const store = useInventoryStore();
    store.filamentBrands = [
      { id: 1, name: "Alpha", aliases: [], created_at: "", updated_at: "" },
      { id: 2, name: "Zeta", aliases: [], created_at: "", updated_at: "" },
    ];
    store.filamentTypeSeries = [
      { id: 1, brand_id: 1, brand_name: "Alpha", material_type: "PLA", series_name: "Basic", brand_ids: [1], brands: [], sku_count: 0, spool_count: 0, created_at: "", updated_at: "" },
      { id: 2, brand_id: 1, brand_name: "Alpha", material_type: "PLA", series_name: "Matte", brand_ids: [1], brands: [], sku_count: 0, spool_count: 0, created_at: "", updated_at: "" },
      { id: 3, brand_id: 1, brand_name: "Alpha", material_type: "ABS", series_name: "ABS", brand_ids: [1], brands: [], sku_count: 0, spool_count: 0, created_at: "", updated_at: "" },
      { id: 4, brand_id: 2, brand_name: "Zeta", material_type: "PETG", series_name: "Basic", brand_ids: [2], brands: [], sku_count: 0, spool_count: 0, created_at: "", updated_at: "" },
    ];
    store.filamentSkus = [
      { id: 1, brand_id: 1, brand_name: "Alpha", type_series_id: 1, material: "PLA", series: "Basic", color_name: "White", color_hex: "FFFFFF", nominal_weight_g: 1000, filament_diameter_mm: 1.75, sealed_quantity: 0, created_at: "", updated_at: "" },
      { id: 2, brand_id: 1, brand_name: "Alpha", type_series_id: 2, material: "PLA", series: "Matte", color_name: "Black", color_hex: "000000", nominal_weight_g: 1000, filament_diameter_mm: 1.75, sealed_quantity: 0, created_at: "", updated_at: "" },
      { id: 3, brand_id: 1, brand_name: "Alpha", type_series_id: 3, material: "ABS", series: "ABS", color_name: "Red", color_hex: "FF0000", nominal_weight_g: 1000, filament_diameter_mm: 1.75, sealed_quantity: 0, created_at: "", updated_at: "" },
      { id: 4, brand_id: 2, brand_name: "Zeta", type_series_id: 4, material: "PETG", series: "Basic", color_name: "Blue", color_hex: "0000FF", nominal_weight_g: 1000, filament_diameter_mm: 1.75, sealed_quantity: 0, created_at: "", updated_at: "" },
    ];

    store.filamentSkuFilters.brand_id = 1;
    expect(store.filamentSkuFilterMaterialOptions.map((item) => item.label)).toEqual(["全部类型", "ABS", "PLA"]);
    expect(store.filamentSkuFilterSeriesOptions.map((item) => item.label)).toEqual(["请先选择类型"]);

    store.filamentSkuFilters.material_type = "PLA";
    await nextTick();
    expect(store.filamentSkuFilterSeriesOptions.map((item) => item.label)).toEqual(["全部系列", "Basic", "Matte"]);
    expect(store.sortedFilteredFilamentSkus.map((sku) => sku.id)).toEqual([1, 2]);

    store.filamentSkuFilters.series_name = "Matte";
    expect(store.sortedFilteredFilamentSkus.map((sku) => sku.id)).toEqual([2]);

    store.filamentSkuFilters.brand_id = 2;
    await nextTick();
    expect(store.filamentSkuFilters.material_type).toBeNull();
    expect(store.filamentSkuFilters.series_name).toBeNull();
    expect(store.sortedFilteredFilamentSkus.map((sku) => sku.id)).toEqual([4]);
  });

  it("formats filament labels with material before series", () => {
    const store = useInventoryStore();

    expect(store.filamentTypeSeriesLabel({ id: 1, material: "PLA", series: "Basic" })).toBe("PLA · Basic");
    expect(store.filamentSkuLabel({ id: 2, brand_name: "Bambu", material: "PLA", series: "Basic", color_name: "White" })).toBe("Bambu · PLA · Basic · White");
    expect(store.filamentSpoolLabel({ id: 3, brand_name: "Bambu", material: "PETG", series: "HF", color_name: "Cream" })).toBe("Bambu · PETG · HF · Cream");
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
      if (path === "/filament/effective-color-mappings") return [];
      if (path === "/filament/bambu-official-color-mappings") return [];
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
      if (path === "/filament/effective-color-mappings") return [];
      if (path === "/filament/bambu-official-color-mappings") return [];
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

  it("uses effective official color mappings for labels and unmapped detection", () => {
    const store = useInventoryStore();
    const mapping = {
      id: -1,
      brand_id: 1,
      brand_name: "Bambu",
      type_series_id: 1,
      material_type: "PETG",
      series_name: "HF",
      material: "PETG",
      series: "HF",
      color_name: "奶油白",
      color_hex: "F9DFB9",
      hex_value: "F9DFB9",
      official_name: "奶油白",
      color_source: "bambu_official",
      official_color_code: "33401",
      official_color_type: "single",
      official_color_names: { zh: "奶油白", en: "Cream" },
      official_colors: ["F9DFB9"],
    };
    store.effectiveFilamentColorMappings = [mapping];
    store.filamentSkus = [
      {
        id: 1,
        brand_id: 1,
        brand_name: "Bambu",
        type_series_id: 1,
        material: "PETG",
        series: "HF",
        color_name: "奶油白",
        color_hex: "F9DFB9",
        color_value: "F9DFB9",
        color_source: "bambu_official",
        official_color_names: { zh: "奶油白", en: "Cream" },
        nominal_weight_g: 1000,
        filament_diameter_mm: 1.75,
        sealed_quantity: 0,
        created_at: "",
        updated_at: "",
      },
    ];

    expect(store.filamentColorDisplay("F9DFB9", null, mapping)).toBe("奶油白");
    useI18nStore().locale = "en-US";
    expect(store.filamentColorDisplay("F9DFB9", null, mapping)).toBe("Cream");
    expect(store.mappedFilamentColorName("F9DFB9", { brand_id: 1, brand_name: "Bambu", material: "PETG", series: "HF" })).toBe("Cream");
    expect(store.unmappedFilamentColors).toHaveLength(0);
    expect(store.colorNeedsMapping("F9DFB9", mapping)).toBe(false);
  });
});
