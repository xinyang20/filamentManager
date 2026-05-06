import { computed, nextTick, reactive, ref, watch } from "vue";
import { acceptHMRUpdate, defineStore, storeToRefs } from "pinia";
import { apiRequest, formatCell, numeric } from "../api";
import { type InventoryDialogKey, type SortDirection } from "../app/navigation";
import {
  filamentAmsRemainingWeight,
  filamentSpoolRemainingLabel,
  filamentSpoolRemainingWeight,
  filamentWeight,
  normalizeFilamentHex,
} from "../app/filamentMetrics";
import type {
  AmsOverview,
  FilamentBrand,
  FilamentColorMapping,
  FilamentColorMappingGap,
  FilamentInventorySummary,
  FilamentSku,
  FilamentSpool,
  FilamentSpoolEvents,
  FilamentTypeSeries,
} from "../types";
import { useAmsStore } from "./ams";
import { useI18nStore } from "./i18n";
import { useNavigationStore } from "./navigation";
import { usePresentationStore } from "./presentation";
import { usePrintersStore } from "./printers";
import { useUiStore } from "./ui";

export const useInventoryStore = defineStore("inventory", () => {
  const uiStore = useUiStore();
  const { error, message } = storeToRefs(uiStore);
  const { t } = useI18nStore();
  const { withLoading } = uiStore;
  const navigationStore = () => useNavigationStore();
  const printersStore = () => usePrintersStore();
  const amsStore = () => useAmsStore();
  const presentationStore = () => usePresentationStore();

  const spools = ref<Record<string, any>[]>([]);

  const filamentBrands = ref<FilamentBrand[]>([]);

  const filamentTypeSeries = ref<FilamentTypeSeries[]>([]);

  const filamentColorMappings = ref<FilamentColorMapping[]>([]);

  const filamentColorMappingGaps = ref<FilamentColorMappingGap[]>([]);

  const filamentSkus = ref<FilamentSku[]>([]);

  const filamentSpools = ref<FilamentSpool[]>([]);

  const filamentInventorySummary = ref<FilamentInventorySummary | null>(null);

  const inventoryTab = ref<"skus" | "spools" | "ams" | "detail">("skus");

  const selectedFilamentSpoolId = ref<number | null>(null);

  const selectedFilamentSpoolEvents = ref<FilamentSpoolEvents | null>(null);

  const inventoryAmsOverviews = ref<Record<string, AmsOverview>>({});

  const inventoryPrinterStates = ref<Record<string, Record<string, any> | null>>({});

  const inventoryDialog = reactive<{
    key: InventoryDialogKey | null;
    context: Record<string, any> | null;
  }>({
    key: null,
    context: null,
  });

  const inventoryTableSorts = reactive<Record<string, { key: string; direction: SortDirection }>>({
    pendingConfirm: { key: "id", direction: "asc" },
    needsLocation: { key: "id", direction: "asc" },
    sealedStock: { key: "id", direction: "asc" },
    amsLoaded: { key: "printer", direction: "asc" },
    openedUnused: { key: "id", direction: "asc" },
    history: { key: "time", direction: "desc" },
    brands: { key: "id", direction: "asc" },
    typeSeries: { key: "id", direction: "asc" },
    skus: { key: "id", direction: "asc" },
    colorMappings: { key: "id", direction: "asc" },
    colorGaps: { key: "id", direction: "asc" },
  });

  const pinyinCollator = new Intl.Collator("zh-Hans-CN-u-co-pinyin", {
    numeric: true,
    sensitivity: "base",
  });

  const inventoryChartColors = ["#00ae42", "#0086d6", "#f4a925", "#c12e1f", "#5e43b7", "#8e9089", "#ff6a13", "#2842ad"];


  const filamentBrandForm = reactive({
    name: "",
    aliases: "",
    default_empty_spool_weight_g: null as number | null,
    note: "",
  });

  const editingFilamentBrandId = ref<number | null>(null);


  const filamentTypeSeriesForm = reactive({
    brand_id: null as number | null,
    material_type: "PLA",
    series_name: "",
    empty_spool_weight_g: null as number | null,
    note: "",
  });

  const editingFilamentTypeSeriesId = ref<number | null>(null);


  const filamentColorMappingForm = reactive({
    brand_id: null as number | null,
    type_series_id: null as number | null,
    material: "PLA",
    series: "",
    hex_value: "",
    official_name: "",
    note: "",
  });

  const editingFilamentColorMappingId = ref<number | null>(null);


  const filamentSkuForm = reactive({
    brand_id: null as number | null,
    type_series_id: null as number | null,
    material: "PLA",
    series: "",
    color_name: "",
    color_value: "",
    nominal_weight_g: 1000,
    empty_spool_weight_g: null as number | null,
    filament_diameter_mm: 1.75,
    tray_info_idx: "",
    sealed_quantity: 0,
    note: "",
  });

  const editingFilamentSkuId = ref<number | null>(null);

  const skuReviewSourceSpoolId = ref<number | null>(null);

  const filamentSkuFilters = reactive({
    search: "",
    brand_id: null as number | null,
    type_series_id: null as number | null,
    nominal_weight_g: null as number | null,
    color_state: "all",
  });

  const inventoryHistorySearch = ref("");


  const filamentSpoolForm = reactive({
    brand_id: null as number | null,
    type_series_id: null as number | null,
    sku_id: null as number | null,
    status: "opened_in_storage",
    tray_uuid: "",
    tag_uid: "",
    current_remaining_g: null as number | null,
    manual_location: "",
    note: "",
  });

  const sealedStockAdjustForm = reactive({
    sku_id: null as number | null,
    current_quantity: 0,
    target_quantity: 0,
    note: "",
  });


  const quantityAdjustForm = reactive({
    current_remaining_g: null as number | null,
    remain_percent: null as number | null,
    source: "manual_adjust",
    note: "",
  });

  const locationAdjustForm = reactive({
    printer_id: null as number | null,
    ams_id: "",
    tray_id: "",
    manual_location: "",
    note: "",
  });

  const dryingEventForm = reactive({
    duration_minutes: null as number | null,
    temperature_c: null as number | null,
    note: "",
  });


  const bindForm = reactive({
    slot_id: "",
    spool_id: "",
  });


  const spoolStatusOptions = computed(() => [
    { label: presentationStore().displayCell("sealed"), value: "sealed" },
    { label: presentationStore().displayCell("opened"), value: "opened" },
    { label: presentationStore().displayCell("active"), value: "active" },
    { label: presentationStore().displayCell("archived"), value: "archived" },
  ]);

  const filamentInventoryTabOptions = computed(() => [
    { label: t("inventory.skuStock"), value: "skus" },
    { label: t("inventory.realSpools"), value: "spools" },
    { label: t("inventory.amsCurrent"), value: "ams" },
    { label: t("inventory.spoolDetail"), value: "detail" },
  ]);

  const filamentSpoolStatusOptions = computed(() => [
    { label: presentationStore().displayCell("opened_in_storage"), value: "opened_in_storage" },
    { label: presentationStore().displayCell("loaded_in_ams"), value: "loaded_in_ams" },
    { label: presentationStore().displayCell("needs_location"), value: "needs_location" },
    { label: t("inventory.status.empty"), value: "empty" },
    { label: t("inventory.status.archived"), value: "archived" },
    { label: presentationStore().displayCell("unknown"), value: "unknown" },
  ]);

  const inventoryPageOptions = computed(() => [
    { key: "stock" as const, label: t("inventory.stockManagement") },
    { key: "history" as const, label: t("inventory.historySpools") },
    { key: "brands" as const, label: t("inventory.brands") },
    { key: "types" as const, label: t("inventory.typeSeries") },
    { key: "skus" as const, label: t("inventory.skus") },
    { key: "colors" as const, label: t("inventory.colorMappings") },
  ]);

  const quantityAdjustSourceOptions = computed(() => [
    { label: t("inventory.manualAdjust"), value: "manual_adjust" },
    { label: t("inventory.weighing"), value: "weighing" },
  ]);

  const filamentBrandOptions = computed(() => [
    { label: t("inventory.noBrand"), value: null },
    ...filamentBrands.value.map((brand) => ({ label: brand.name, value: brand.id })),
  ]);

  const filamentRequiredBrandOptions = computed(() =>
    filamentBrands.value.map((brand) => ({ label: brand.name, value: brand.id })),
  );

  const filamentTypeSeriesOptions = computed(() =>
    filamentTypeSeries.value.map((row) => ({
      label: [row.brand_name, filamentTypeSeriesLabel(row)].filter(Boolean).join(" · "),
      value: row.id,
    })),
  );

  const filamentColorMappingTypeSeriesOptions = computed(() =>
    filamentTypeSeries.value
      .filter((row) => !filamentColorMappingForm.brand_id || row.brand_id === filamentColorMappingForm.brand_id)
      .map((row) => ({
        label: [row.brand_name, filamentTypeSeriesLabel(row)].filter(Boolean).join(" · "),
        value: row.id,
      })),
  );

  const filamentSkuOptions = computed(() => [
    { label: t("inventory.noSku"), value: null },
    ...filamentSkus.value.map((sku) => ({ label: filamentSkuLabel(sku), value: sku.id })),
  ]);

  const filamentSkuFilterBrandOptions = computed(() => [
    { label: t("inventory.allBrands"), value: null },
    ...filamentBrands.value.map((brand) => ({ label: brand.name, value: brand.id })),
  ]);

  const filamentSkuFilterTypeSeriesOptions = computed(() => [
    { label: t("inventory.allTypeSeries"), value: null },
    ...filamentTypeSeries.value
      .filter((row) => !filamentSkuFilters.brand_id || row.brand_id === filamentSkuFilters.brand_id)
      .map((row) => ({
        label: [row.brand_name, filamentTypeSeriesLabel(row)].filter(Boolean).join(" · "),
        value: row.id,
      })),
  ]);

  const filamentSkuWeightOptions = computed(() => {
    const weights = Array.from(
      new Set(
        filamentSkus.value
          .map((sku) => numeric(sku.nominal_weight_g))
          .filter((value): value is number => value !== null && value >= 0)
          .map((value) => Math.round(value)),
      ),
    ).sort((left, right) => left - right);
    return [
      { label: t("inventory.allWeights"), value: null },
      ...weights.map((weight) => ({ label: filamentWeight(weight), value: weight })),
    ];
  });

  const filamentSkuColorStateOptions = computed(() => [
    { label: t("inventory.allColorStates"), value: "all" },
    { label: t("inventory.colorComplete"), value: "complete" },
    { label: t("inventory.colorIncomplete"), value: "incomplete" },
    { label: t("inventory.missingColorName"), value: "missing_name" },
    { label: t("inventory.missingColorHex"), value: "missing_hex" },
  ]);

  const filteredFilamentSkus = computed(() =>
    filamentSkus.value.filter((sku) => {
      if (filamentSkuFilters.brand_id && sku.brand_id !== filamentSkuFilters.brand_id) return false;
      if (filamentSkuFilters.type_series_id && sku.type_series_id !== filamentSkuFilters.type_series_id) return false;
      if (filamentSkuFilters.nominal_weight_g !== null) {
        const weight = numeric(sku.nominal_weight_g);
        if (weight === null || Math.round(weight) !== filamentSkuFilters.nominal_weight_g) return false;
      }
      if (!filamentSkuMatchesColorState(sku, filamentSkuFilters.color_state)) return false;
      const query = filamentSkuFilters.search.trim().toLowerCase();
      return !query || filamentSkuSearchText(sku).includes(query);
    }),
  );

  const filamentSpoolBrandOptions = computed(() => [
    { label: t("inventory.noBrand"), value: null },
    ...filamentBrands.value.map((brand) => ({ label: brand.name, value: brand.id })),
  ]);

  const filamentSpoolTypeSeriesOptions = computed(() => {
    if (!filamentSpoolForm.brand_id) return [{ label: t("inventory.selectBrandFirst"), value: null, disabled: true }];
    return [
      { label: t("inventory.noTypeSeries"), value: null },
      ...filamentTypeSeries.value
        .filter((row) => row.brand_id === filamentSpoolForm.brand_id)
        .map((row) => ({ label: filamentTypeSeriesLabel(row), value: row.id })),
    ];
  });

  const filamentSpoolSkuOptions = computed(() => {
    if (!filamentSpoolForm.type_series_id) return [{ label: t("inventory.selectTypeSeriesFirst"), value: null, disabled: true }];
    return [
      { label: t("inventory.noSku"), value: null },
      ...filamentSkus.value
        .filter((sku) => sku.type_series_id === filamentSpoolForm.type_series_id)
        .map((sku) => ({ label: filamentSkuCompactLabel(sku), value: sku.id })),
    ];
  });

  watch(
    () => filamentColorMappingForm.brand_id,
    (brandId) => {
      if (!brandId || !filamentColorMappingForm.type_series_id) return;
      const selected = filamentTypeSeries.value.find((row) => row.id === filamentColorMappingForm.type_series_id);
      if (selected && selected.brand_id !== brandId) filamentColorMappingForm.type_series_id = null;
    },
  );

  watch(
    () => filamentSkuFilters.brand_id,
    (brandId) => {
      const selected = filamentTypeSeries.value.find((row) => row.id === filamentSkuFilters.type_series_id);
      if (!brandId || (selected && selected.brand_id !== brandId)) filamentSkuFilters.type_series_id = null;
    },
  );

  watch(
    () => filamentSpoolForm.brand_id,
    (brandId) => {
      const selectedType = filamentTypeSeries.value.find((row) => row.id === filamentSpoolForm.type_series_id);
      if (!brandId || (selectedType && selectedType.brand_id !== brandId)) filamentSpoolForm.type_series_id = null;
      const selectedSku = filamentSkus.value.find((sku) => sku.id === filamentSpoolForm.sku_id);
      if (!brandId || (selectedSku && selectedSku.brand_id !== brandId)) filamentSpoolForm.sku_id = null;
    },
  );

  watch(
    () => filamentSpoolForm.type_series_id,
    (typeSeriesId) => {
      const selectedSku = filamentSkus.value.find((sku) => sku.id === filamentSpoolForm.sku_id);
      if (!typeSeriesId || (selectedSku && selectedSku.type_series_id !== typeSeriesId)) filamentSpoolForm.sku_id = null;
    },
  );

  watch(
    () => filamentSpoolForm.sku_id,
    (skuId) => {
      const sku = filamentSkus.value.find((row) => row.id === skuId);
      if (!sku) return;
      filamentSpoolForm.type_series_id = sku.type_series_id ?? null;
      filamentSpoolForm.brand_id = sku.brand_id ?? null;
    },
  );

  const selectedFilamentSpool = computed(() =>
    filamentSpools.value.find((spool) => spool.id === selectedFilamentSpoolId.value) || filamentSpools.value[0] || null,
  );

  const filamentAmsRows = computed(() =>
    amsStore().amsSlots.map((slot) => ({
      slot,
      spool: filamentSpools.value.find((item) => item.id === Number(slot.filament_spool_id)) || null,
    })),
  );

  const filamentStockSkus = computed(() => filamentSkus.value.filter((sku) => sku.sealed_quantity > 0));

  const filamentOpenedUnusedSpools = computed(() =>
    filamentSpools.value.filter((spool) => {
      if (spool.current_ams_id || spool.current_tray_id) return false;
      if (!["opened_in_storage", "needs_location", "unknown"].includes(spool.status)) return false;
      const remaining = filamentSpoolRemainingWeight(spool);
      if (remaining !== null) return remaining > 0;
      const remainPercent = numeric(spool.last_ams_remain_percent);
      if (remainPercent !== null) return remainPercent > 0;
      return true;
    }),
  );

  const sortedNeedsLocationSpools = computed(() =>
    sortInventoryRows(filamentInventorySummary.value?.needs_location_spools || [], "needsLocation"),
  );

  const pendingConfirmSpools = computed(() =>
    filamentSpools.value.filter((spool) => isFilamentSpoolPendingConfirm(spool) && !isFilamentSpoolSkuReviewDeferred(spool)),
  );

  const deferredConfirmSpools = computed(() =>
    filamentSpools.value.filter((spool) => isFilamentSpoolPendingConfirm(spool) && isFilamentSpoolSkuReviewDeferred(spool)),
  );

  const sortedPendingConfirmSpools = computed(() => sortInventoryRows(pendingConfirmSpools.value, "pendingConfirm"));

  const sortedFilamentStockSkus = computed(() => sortInventoryRows(filamentStockSkus.value, "sealedStock"));

  const sortedFilamentAmsRows = computed(() => sortInventoryRows(filamentAmsRows.value, "amsLoaded"));

  const sortedFilamentOpenedUnusedSpools = computed(() => sortInventoryRows(filamentOpenedUnusedSpools.value, "openedUnused"));

  const historicalFilamentSpools = computed(() =>
    filamentSpools.value.filter((spool) => ["empty", "archived"].includes(spool.status)),
  );

  const filteredHistoricalFilamentSpools = computed(() => {
    const query = inventoryHistorySearch.value.trim().toLowerCase();
    if (!query) return historicalFilamentSpools.value;
    return historicalFilamentSpools.value.filter((spool) =>
      [
        spool.id,
        filamentSpoolLabel(spool),
        filamentSpoolStatusLabel(spool.status),
        filamentSpoolLastLocation(spool),
        filamentSpoolRemainingLabel(spool),
        filamentSpoolHistoryTime(spool),
        spool.official_spool_uid,
        spool.note,
      ]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  });

  const sortedHistoricalFilamentSpools = computed(() => sortInventoryRows(filteredHistoricalFilamentSpools.value, "history"));

  const sortedFilamentBrands = computed(() => sortInventoryRows(filamentBrands.value, "brands"));

  const sortedFilamentTypeSeries = computed(() => sortInventoryRows(filamentTypeSeries.value, "typeSeries"));

  const sortedFilteredFilamentSkus = computed(() => sortInventoryRows(filteredFilamentSkus.value, "skus"));

  const sortedFilamentColorMappings = computed(() => sortInventoryRows(filamentColorMappings.value, "colorMappings"));

  const sortedFilamentColorMappingGaps = computed(() => sortInventoryRows(filamentColorMappingGaps.value, "colorGaps"));

  const inventoryRealSpools = computed(() => filamentSpools.value.filter((spool) => !["empty", "archived"].includes(spool.status)));

  const inventorySealedWeightG = computed(() =>
    filamentSkus.value.reduce((total, sku) => total + Number(sku.sealed_quantity || 0) * (numeric(sku.nominal_weight_g) || 0), 0),
  );

  const inventoryRealSpoolWeightG = computed(() =>
    inventoryRealSpools.value.reduce((total, spool) => {
      const remaining = filamentSpoolRemainingWeight(spool);
      return total + (remaining ?? numeric(spool.nominal_weight_g) ?? 0);
    }, 0),
  );

  const inventoryTotalWeightG = computed(() => inventorySealedWeightG.value + inventoryRealSpoolWeightG.value);

  const inventoryTotalRolls = computed(() =>
    filamentSkus.value.reduce((total, sku) => total + Number(sku.sealed_quantity || 0), 0) + inventoryRealSpools.value.length,
  );

  const inventoryPendingConfirmCount = computed(() => pendingConfirmSpools.value.length);

  const inventoryTypeBreakdown = computed(() => {
    const rows = new Map<string, { key: string; label: string; grams: number; rolls: number }>();
    const add = (keyValue: unknown, grams: number, rolls: number) => {
      const key = String(keyValue || t("inventory.unknownType"));
      if (!rows.has(key)) rows.set(key, { key, label: key, grams: 0, rolls: 0 });
      const row = rows.get(key)!;
      row.grams += grams;
      row.rolls += rolls;
    };
    for (const sku of filamentSkus.value) {
      const quantity = Number(sku.sealed_quantity || 0);
      if (quantity <= 0) continue;
      add(sku.material, quantity * (numeric(sku.nominal_weight_g) || 0), quantity);
    }
    for (const spool of inventoryRealSpools.value) {
      add(spool.material, filamentSpoolRemainingWeight(spool) ?? numeric(spool.nominal_weight_g) ?? 0, 1);
    }
    return [...rows.values()].sort((left, right) => right.grams - left.grams || pinyinCollator.compare(left.label, right.label));
  });

  const inventoryMaxTypeWeightG = computed(() => Math.max(1, ...inventoryTypeBreakdown.value.map((row) => row.grams)));

  const inventoryTypePieStyle = computed(() => {
    const total = inventoryTypeBreakdown.value.reduce((sum, row) => sum + row.grams, 0);
    if (total <= 0) return { background: "rgba(18, 28, 24, 0.08)" };
    let cursor = 0;
    const stops = inventoryTypeBreakdown.value.map((row, index) => {
      const start = cursor;
      cursor += (row.grams / total) * 100;
      const color = inventoryChartColors[index % inventoryChartColors.length];
      return `${color} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`;
    });
    return { background: `conic-gradient(${stops.join(", ")})` };
  });

  const filamentColorMappingByContext = computed(() => {
    const rows = new Map<string, FilamentColorMapping>();
    for (const mapping of filamentColorMappings.value) {
      const key = filamentColorMappingKey(mapping, mapping.color_hex || mapping.hex_value);
      if (key) rows.set(key, mapping);
    }
    return rows;
  });

  const unmappedFilamentColors = computed(() => {
    const rows = new Map<string, { hex: string; brand_id: number; brand_name: string; material: string; series: string; sources: Set<string> }>();
    const add = (value: unknown, source: string, context: Record<string, any> | null | undefined) => {
      const hex = normalizeFilamentHex(value);
      const normalized = normalizeFilamentColorContext(context);
      if (!hex || !normalized) return;
      const key = filamentColorMappingKey(normalized, hex);
      if (!key || filamentColorMappingByContext.value.has(key)) return;
      if (!rows.has(key)) rows.set(key, { hex, ...normalized, sources: new Set() });
      rows.get(key)?.sources.add(source);
    };
    for (const slot of amsStore().amsSlots) {
      const context = slotFilamentColorContext(slot);
      add(slot.color || slot.tray_color, slot.location_label || `AMS ${formatCell(slot.ams_id)} / ${formatCell(slot.tray_id)}`, context);
      const cols = Array.isArray(slot.raw?.cols) ? slot.raw.cols : [];
      for (const color of cols) add(color, slot.location_label || `AMS ${formatCell(slot.ams_id)} / ${formatCell(slot.tray_id)}`, context);
    }
    for (const sku of filamentSkus.value) add(sku.color_value, filamentSkuLabel(sku), sku);
    for (const spool of filamentSpools.value) add(spool.color_value, filamentSpoolLabel(spool), spool);
    return [...rows.values()]
      .map((row) => ({ ...row, sources: [...row.sources].slice(0, 3).join(" · ") }))
      .sort((left, right) => [left.brand_name, left.material, left.series, left.hex].join("|").localeCompare([right.brand_name, right.material, right.series, right.hex].join("|")));
  });

  async function loadInventory() {
    const [
      brandResult,
      typeSeriesResult,
      colorMappingResult,
      gapResult,
      skuResult,
      spoolResult,
      summaryResult,
      inventoryAmsResult,
    ] = await Promise.all([
      apiRequest<FilamentBrand[]>("/filament/brands"),
      apiRequest<FilamentTypeSeries[]>("/filament/type-series"),
      apiRequest<FilamentColorMapping[]>("/filament/color-mappings"),
      apiRequest<FilamentColorMappingGap[]>("/filament/color-mapping-gaps"),
      apiRequest<FilamentSku[]>("/filament/skus"),
      apiRequest<FilamentSpool[]>("/filament/spools"),
      apiRequest<FilamentInventorySummary>("/filament/inventory/summary"),
      loadInventoryAmsGlobal(),
    ]);
    filamentBrands.value = brandResult;
    filamentTypeSeries.value = typeSeriesResult;
    filamentColorMappings.value = colorMappingResult;
    filamentColorMappingGaps.value = gapResult;
    filamentSkus.value = skuResult;
    filamentSpools.value = spoolResult;
    filamentInventorySummary.value = summaryResult;
    amsStore().amsSlots = inventoryAmsResult.slots;
    inventoryAmsOverviews.value = inventoryAmsResult.overviews;
    inventoryPrinterStates.value = inventoryAmsResult.states;
    spools.value = spoolResult.map((spool) => ({
      id: spool.legacy_spool_id || spool.id,
      display_name: spool.sku_label || `${t("table.spool")} ${spool.id}`,
      material: spool.material,
      series: spool.series,
      color: spool.color_value || spool.color_name,
      status: spool.status,
      sealed_quantity: 0,
      current_printer_id: spool.current_printer_id,
      current_ams_id: spool.current_ams_id,
      current_tray_id: spool.current_tray_id,
    }));
    if (!selectedFilamentSpoolId.value && spoolResult.length) {
      selectedFilamentSpoolId.value = spoolResult[0].id;
    }
    if (selectedFilamentSpoolId.value) {
      await loadFilamentSpoolEvents(selectedFilamentSpoolId.value);
    }
  }


  async function loadInventoryAmsGlobal(): Promise<{
    slots: Record<string, any>[];
    overviews: Record<string, AmsOverview>;
    states: Record<string, Record<string, any> | null>;
  }> {
    if (!printersStore().printers.length) return { slots: [], overviews: {}, states: {} };
    const rows = await Promise.all(
      printersStore().printers.map(async (printer) => {
        const [slotResult, overviewResult, stateResult] = await Promise.all([
          apiRequest<Record<string, any>[]>(`/printers/${printer.id}/ams/slots`),
          apiRequest<AmsOverview>(`/printers/${printer.id}/ams/overview`),
          apiRequest<Record<string, any> | null>(`/printers/${printer.id}/state`),
        ]);
        return {
          printer,
          slots: slotResult.map((slot) => ({
            ...slot,
            printer_id: slot.printer_id ?? printer.id,
            printer_name: printer.name,
            printer_host: printer.host,
          })),
          overview: overviewResult,
          state: stateResult,
        };
      }),
    );
    return {
      slots: rows.flatMap((row) => row.slots),
      overviews: Object.fromEntries(rows.map((row) => [String(row.printer.id), row.overview])),
      states: Object.fromEntries(rows.map((row) => [String(row.printer.id), row.state])),
    };
  }


  async function loadFilamentSpoolEvents(spoolId: number) {
    selectedFilamentSpoolEvents.value = await apiRequest<FilamentSpoolEvents>(`/filament/spools/${spoolId}/events`);
  }


  function openInventoryDialog(key: InventoryDialogKey, context: Record<string, any> | null = null) {
    inventoryDialog.key = key;
    inventoryDialog.context = context;
  }


  function closeInventoryDialog() {
    const previousKey = inventoryDialog.key;
    inventoryDialog.key = null;
    inventoryDialog.context = null;
    if (previousKey === "sku") skuReviewSourceSpoolId.value = null;
  }


  function openFilamentBrandCreate() {
    resetFilamentBrandForm();
    openInventoryDialog("brand");
  }


  function resetFilamentBrandForm() {
    editingFilamentBrandId.value = null;
    filamentBrandForm.name = "";
    filamentBrandForm.aliases = "";
    filamentBrandForm.note = "";
    filamentBrandForm.default_empty_spool_weight_g = null;
  }


  function editFilamentBrand(brand: FilamentBrand) {
    editingFilamentBrandId.value = brand.id;
    filamentBrandForm.name = brand.name;
    filamentBrandForm.aliases = (brand.aliases || []).join(", ");
    filamentBrandForm.note = brand.note || "";
    filamentBrandForm.default_empty_spool_weight_g = null;
    openInventoryDialog("brand", brand);
  }


  async function saveFilamentBrand() {
    if (!filamentBrandForm.name.trim()) return;
    await withLoading(async () => {
      const editingId = editingFilamentBrandId.value;
      await apiRequest<FilamentBrand>(editingId ? `/filament/brands/${editingId}` : "/filament/brands", {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify({
          name: filamentBrandForm.name.trim(),
          aliases: filamentBrandForm.aliases.split(",").map((item) => item.trim()).filter(Boolean),
          note: filamentBrandForm.note || null,
        }),
      });
      resetFilamentBrandForm();
      closeInventoryDialog();
      await loadInventory();
      message.value = t(editingId ? "inventory.brandUpdated" : "inventory.brandCreated");
    });
  }


  async function deleteFilamentBrand(brand: FilamentBrand) {
    const confirmed = window.confirm(t("inventory.deleteBrandConfirm", { id: brand.id }));
    if (!confirmed) return;
    await withLoading(async () => {
      await apiRequest(`/filament/brands/${brand.id}`, { method: "DELETE" });
      if (editingFilamentBrandId.value === brand.id) resetFilamentBrandForm();
      await loadInventory();
      message.value = t("inventory.brandDeleted");
    });
  }


  function openFilamentTypeSeriesCreate() {
    resetFilamentTypeSeriesForm();
    openInventoryDialog("typeSeries");
  }


  function resetFilamentTypeSeriesForm() {
    editingFilamentTypeSeriesId.value = null;
    Object.assign(filamentTypeSeriesForm, {
      brand_id: null,
      material_type: "PLA",
      series_name: "",
      empty_spool_weight_g: null,
      note: "",
    });
  }


  function editFilamentTypeSeries(row: FilamentTypeSeries) {
    editingFilamentTypeSeriesId.value = row.id;
    Object.assign(filamentTypeSeriesForm, {
      brand_id: row.brand_id ?? row.brand_ids?.[0] ?? null,
      material_type: row.material_type,
      series_name: row.series_name,
      empty_spool_weight_g: row.empty_spool_weight_g ?? null,
      note: row.note || "",
    });
    openInventoryDialog("typeSeries", row);
  }


  async function saveFilamentTypeSeries() {
    if (!filamentTypeSeriesForm.brand_id || !filamentTypeSeriesForm.material_type.trim() || !filamentTypeSeriesForm.series_name.trim()) return;
    await withLoading(async () => {
      const editingId = editingFilamentTypeSeriesId.value;
      await apiRequest<FilamentTypeSeries>(editingId ? `/filament/type-series/${editingId}` : "/filament/type-series", {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify({
          brand_id: filamentTypeSeriesForm.brand_id,
          material_type: filamentTypeSeriesForm.material_type.trim(),
          series_name: filamentTypeSeriesForm.series_name.trim(),
          empty_spool_weight_g: presentationStore().optionalNumber(filamentTypeSeriesForm.empty_spool_weight_g),
          note: filamentTypeSeriesForm.note || null,
        }),
      });
      resetFilamentTypeSeriesForm();
      closeInventoryDialog();
      await loadInventory();
      message.value = t(editingId ? "inventory.typeSeriesUpdated" : "inventory.typeSeriesCreated");
    });
  }


  async function deleteFilamentTypeSeries(row: FilamentTypeSeries) {
    const confirmed = window.confirm(t("inventory.deleteTypeSeriesConfirm", { id: row.id }));
    if (!confirmed) return;
    await withLoading(async () => {
      await apiRequest(`/filament/type-series/${row.id}`, { method: "DELETE" });
      if (editingFilamentTypeSeriesId.value === row.id) resetFilamentTypeSeriesForm();
      await loadInventory();
      message.value = t("inventory.typeSeriesDeleted");
    });
  }


  function openFilamentColorMappingCreate() {
    resetFilamentColorMappingForm();
    openInventoryDialog("colorMapping");
  }


  function resetFilamentColorMappingForm() {
    editingFilamentColorMappingId.value = null;
    filamentColorMappingForm.brand_id = null;
    filamentColorMappingForm.type_series_id = null;
    filamentColorMappingForm.material = "PLA";
    filamentColorMappingForm.series = "";
    filamentColorMappingForm.hex_value = "";
    filamentColorMappingForm.official_name = "";
    filamentColorMappingForm.note = "";
  }


  function editFilamentColorMapping(mapping: FilamentColorMapping) {
    editingFilamentColorMappingId.value = mapping.id;
    filamentColorMappingForm.brand_id = mapping.brand_id ?? null;
    filamentColorMappingForm.type_series_id = mapping.type_series_id ?? null;
    filamentColorMappingForm.material = mapping.material || "PLA";
    filamentColorMappingForm.series = mapping.series || "";
    filamentColorMappingForm.hex_value = mapping.color_hex || mapping.hex_value || "";
    filamentColorMappingForm.official_name = mapping.color_name || mapping.official_name || "";
    filamentColorMappingForm.note = mapping.note || "";
    openInventoryDialog("colorMapping", mapping);
  }


  function startFilamentColorMapping(value: unknown, context?: Record<string, any> | null) {
    const hex = normalizeFilamentHex(value);
    if (!hex) return;
    const normalized = normalizeFilamentColorContext(context);
    navigationStore().inventoryPage = "colors";
    editingFilamentColorMappingId.value = null;
    filamentColorMappingForm.brand_id = normalized?.brand_id ?? null;
    filamentColorMappingForm.type_series_id = normalized?.type_series_id ?? null;
    filamentColorMappingForm.material = normalized?.material || "PLA";
    filamentColorMappingForm.series = normalized?.series || "";
    filamentColorMappingForm.hex_value = hex;
    filamentColorMappingForm.official_name = "";
    filamentColorMappingForm.note = "";
    openInventoryDialog("colorMapping", normalized || null);
  }


  async function saveFilamentColorMapping() {
    const typeSeriesId =
      filamentColorMappingForm.type_series_id ||
      findTypeSeriesId(filamentColorMappingForm.material, filamentColorMappingForm.series, filamentColorMappingForm.brand_id);
    if (!filamentColorMappingForm.brand_id || !typeSeriesId || !filamentColorMappingForm.hex_value.trim() || !filamentColorMappingForm.official_name.trim()) return;
    await withLoading(async () => {
      const editingId = editingFilamentColorMappingId.value;
      await apiRequest<FilamentColorMapping>(editingId ? `/filament/color-mappings/${editingId}` : "/filament/color-mappings", {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify({
          brand_id: filamentColorMappingForm.brand_id,
          type_series_id: typeSeriesId,
          color_hex: filamentColorMappingForm.hex_value,
          color_name: filamentColorMappingForm.official_name.trim(),
          note: filamentColorMappingForm.note || null,
        }),
      });
      resetFilamentColorMappingForm();
      closeInventoryDialog();
      await loadInventory();
      message.value = t(editingId ? "inventory.colorMappingUpdated" : "inventory.colorMappingCreated");
    });
  }


  async function deleteFilamentColorMapping(mapping: FilamentColorMapping) {
    await withLoading(async () => {
      await apiRequest(`/filament/color-mappings/${mapping.id}`, { method: "DELETE" });
      if (editingFilamentColorMappingId.value === mapping.id) resetFilamentColorMappingForm();
      await loadInventory();
      message.value = t("inventory.colorMappingDeleted");
    });
  }


  function filamentSkuPayload() {
    const nominalWeight = presentationStore().optionalNumber(filamentSkuForm.nominal_weight_g);
    return {
      type_series_id: filamentSkuForm.type_series_id,
      color_name: filamentSkuForm.color_name || null,
      color_hex: filamentSkuForm.color_value || null,
      nominal_weight_g: nominalWeight ?? 1000,
      filament_diameter_mm: presentationStore().optionalNumber(filamentSkuForm.filament_diameter_mm) ?? 1.75,
      tray_info_idx: filamentSkuForm.tray_info_idx || null,
      sealed_quantity: editingFilamentSkuId.value ? undefined : presentationStore().optionalNumber(filamentSkuForm.sealed_quantity) ?? 0,
      note: filamentSkuForm.note || null,
    };
  }


  function openFilamentSkuCreate() {
    skuReviewSourceSpoolId.value = null;
    resetFilamentSkuForm();
    openInventoryDialog("sku");
  }


  function resetFilamentSkuForm() {
    editingFilamentSkuId.value = null;
    Object.assign(filamentSkuForm, {
      brand_id: null,
      type_series_id: null,
      material: "PLA",
      series: "",
      color_name: "",
      color_value: "",
      nominal_weight_g: 1000,
      empty_spool_weight_g: null,
      filament_diameter_mm: 1.75,
      tray_info_idx: "",
      sealed_quantity: 0,
      note: "",
    });
  }


  function editFilamentSku(sku: FilamentSku, options: { reviewSpoolId?: number | null } = {}) {
    editingFilamentSkuId.value = sku.id;
    skuReviewSourceSpoolId.value = options.reviewSpoolId ?? null;
    Object.assign(filamentSkuForm, {
      brand_id: sku.brand_id ?? null,
      type_series_id: sku.type_series_id ?? sku.type_series_ids?.[0] ?? null,
      material: sku.material || "PLA",
      series: sku.series || "",
      color_name: sku.color_name || "",
      color_value: sku.color_hex || sku.color_value || "",
      nominal_weight_g: sku.nominal_weight_g,
      empty_spool_weight_g: sku.empty_spool_weight_g ?? null,
      filament_diameter_mm: sku.filament_diameter_mm,
      tray_info_idx: sku.tray_info_idx || "",
      sealed_quantity: sku.sealed_quantity,
      note: sku.note || "",
    });
    openInventoryDialog("sku", sku);
  }


  function cancelFilamentSkuEdit() {
    skuReviewSourceSpoolId.value = null;
    resetFilamentSkuForm();
    closeInventoryDialog();
  }


  function resetFilamentSkuFilters() {
    Object.assign(filamentSkuFilters, {
      search: "",
      brand_id: null,
      type_series_id: null,
      nominal_weight_g: null,
      color_state: "all",
    });
  }


  async function saveFilamentSku() {
    if (!filamentSkuForm.type_series_id) return;
    await withLoading(async () => {
      const editingId = editingFilamentSkuId.value;
      const reviewSpoolId = skuReviewSourceSpoolId.value;
      const previousSku = editingId ? filamentSkus.value.find((sku) => sku.id === editingId) : null;
      const targetSealedQuantity = Math.max(0, Math.round(presentationStore().optionalNumber(filamentSkuForm.sealed_quantity) ?? 0));
      const savedSku = await apiRequest<FilamentSku>(editingId ? `/filament/skus/${editingId}` : "/filament/skus", {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify(filamentSkuPayload()),
      });
      if (editingId && previousSku) {
        const delta = targetSealedQuantity - Number(previousSku.sealed_quantity || 0);
        if (delta !== 0) {
          await apiRequest<FilamentSku>(`/filament/skus/${editingId}/sealed-stock-adjust`, {
            method: "POST",
            body: JSON.stringify({ delta, reason: "sku edit" }),
          });
        }
      }
      if (reviewSpoolId && savedSku?.id) {
        await apiRequest<FilamentSpool>(`/filament/spools/${reviewSpoolId}`, {
          method: "PATCH",
          body: JSON.stringify({ sku_id: savedSku.id }),
        });
        await apiRequest<FilamentSpool>(`/filament/spools/${reviewSpoolId}/confirm-sku`, { method: "POST" });
      }
      skuReviewSourceSpoolId.value = null;
      resetFilamentSkuForm();
      closeInventoryDialog();
      await loadInventory();
      message.value = t(reviewSpoolId ? "inventory.skuConfirmed" : editingId ? "inventory.skuUpdated" : "inventory.skuCreated");
    });
  }


  async function deleteFilamentSku(sku: FilamentSku) {
    const sealedQuantity = Number(sku.sealed_quantity || 0);
    const realSpoolCount = Number(sku.opened_spool_count || 0) + Number(sku.ams_spool_count || 0);
    const forceDelete = sealedQuantity > 0 && realSpoolCount === 0;
    const confirmed = window.confirm(
      t(forceDelete ? "inventory.forceDeleteSkuConfirm" : "inventory.deleteSkuConfirm", {
        id: sku.id,
        quantity: sealedQuantity,
      }),
    );
    if (!confirmed) return;
    await withLoading(async () => {
      await apiRequest(`/filament/skus/${sku.id}${forceDelete ? "?force=true" : ""}`, { method: "DELETE" });
      if (editingFilamentSkuId.value === sku.id) resetFilamentSkuForm();
      await loadInventory();
      message.value = t("inventory.skuDeleted");
    });
  }


  function openSealedStockAdjust(sku: FilamentSku) {
    sealedStockAdjustForm.sku_id = sku.id;
    sealedStockAdjustForm.current_quantity = Number(sku.sealed_quantity || 0);
    sealedStockAdjustForm.target_quantity = Number(sku.sealed_quantity || 0);
    sealedStockAdjustForm.note = "";
    openInventoryDialog("stockAdjust", sku);
  }


  async function saveSealedStockAdjust() {
    const sku = filamentSkus.value.find((item) => item.id === sealedStockAdjustForm.sku_id);
    if (!sku) return;
    const target = Math.max(0, Math.round(presentationStore().optionalNumber(sealedStockAdjustForm.target_quantity) ?? 0));
    const delta = target - Number(sku.sealed_quantity || 0);
    await withLoading(async () => {
      if (delta !== 0) {
        await apiRequest<FilamentSku>(`/filament/skus/${sku.id}/sealed-stock-adjust`, {
          method: "POST",
          body: JSON.stringify({ delta, reason: sealedStockAdjustForm.note || "stock dialog" }),
        });
      }
      closeInventoryDialog();
      await loadInventory();
      message.value = t("inventory.stockAdjusted");
    });
  }


  async function adjustFilamentSkuStock(sku: FilamentSku, delta: number) {
    await withLoading(async () => {
      await apiRequest<FilamentSku>(`/filament/skus/${sku.id}/sealed-stock-adjust`, {
        method: "POST",
        body: JSON.stringify({ delta, reason: "manual" }),
      });
      await loadInventory();
      message.value = t("inventory.stockAdjusted");
    });
  }


  function openConfirmFilamentSpoolSku(spool: FilamentSpool | Record<string, any>) {
    openInventoryDialog("skuConfirm", spool);
  }


  function editSkuFromConfirmDialog() {
    const spool = inventoryDialog.context;
    const spoolId = numeric(spool?.id);
    const reviewSpoolId = spoolId !== null ? Math.round(spoolId) : null;
    const sku = filamentSkus.value.find((item) => item.id === Number(spool?.sku_id));
    navigationStore().inventoryPage = "skus";
    if (sku) {
      editFilamentSku(sku, { reviewSpoolId });
      return;
    }
    prepareFilamentSkuCreateFromSpool(spool, reviewSpoolId);
    openInventoryDialog("sku", spool ?? null);
  }


  function prepareFilamentSkuCreateFromSpool(spool: Record<string, any> | null | undefined, reviewSpoolId: number | null) {
    resetFilamentSkuForm();
    skuReviewSourceSpoolId.value = reviewSpoolId;
    const raw = presentationStore().record(presentationStore().record(spool?.config).ams_raw);
    const firstTypeSeries = presentationStore().arrayOfRecord(spool?.type_series)[0] || null;
    const firstBrand = presentationStore().arrayOfRecord(spool?.brands)[0] || null;
    const material = presentationStore().firstText(spool?.material, raw.tray_type, raw.filament_type, firstTypeSeries?.material_type, "PLA");
    const series = presentationStore().firstText(spool?.series, raw.tray_sub_brands, raw.tray_info_idx, raw.filament_name, firstTypeSeries?.series_name);
    const brandId = numeric(spool?.brand_id ?? firstBrand?.id ?? firstTypeSeries?.brand_id);
    const typeSeriesId =
      numeric(spool?.type_series_id ?? firstTypeSeries?.id) ??
      (material && series ? findTypeSeriesId(material, series, brandId) : null);
    const nominalWeight = numeric(
      spool?.nominal_weight_g ??
        spool?.initial_net_weight_g ??
        raw.tray_weight_g ??
        raw.tray_weight ??
        raw.filament_weight_g ??
        raw.filament_weight ??
        raw.nominal_weight_g ??
        raw.net_weight_g ??
        raw.net_weight ??
        raw.weight_g ??
        raw.weight,
    );
    Object.assign(filamentSkuForm, {
      brand_id: brandId,
      type_series_id: typeSeriesId,
      material: material || "PLA",
      series,
      color_name: presentationStore().firstText(
        spool?.color_name,
        raw.tray_color_name,
        raw.color_name,
        raw.filament_color_name,
        raw.color_display_name,
      ),
      color_value: normalizeFilamentHex(presentationStore().firstText(spool?.color_hex, spool?.color_value, raw.tray_color, raw.color)) || "",
      nominal_weight_g: nominalWeight ?? 1000,
      empty_spool_weight_g: numeric(spool?.empty_spool_weight_g ?? firstTypeSeries?.empty_spool_weight_g),
      filament_diameter_mm: 1.75,
      tray_info_idx: presentationStore().firstText(raw.tray_info_idx),
      sealed_quantity: 0,
      note: presentationStore().firstText(spool?.note),
    });
  }


  function inventoryDialogSkuLabel(): string {
    const sku = inventoryDialog.context as FilamentSku | null;
    return sku ? filamentSkuLabel(sku) : "—";
  }


  function inventoryDialogSpoolLabel(): string {
    return filamentSpoolLabel(inventoryDialog.context);
  }


  async function confirmFilamentSpoolSku(spool: FilamentSpool | Record<string, any>) {
    const spoolId = Number(spool.id);
    if (!Number.isFinite(spoolId)) return;
    await withLoading(async () => {
      await apiRequest<FilamentSpool>(`/filament/spools/${spoolId}/confirm-sku`, { method: "POST" });
      closeInventoryDialog();
      await loadInventory();
      message.value = t("inventory.skuConfirmed");
    });
  }


  function openCreateFilamentSpoolDialog() {
    Object.assign(filamentSpoolForm, {
      brand_id: null,
      type_series_id: null,
      sku_id: null,
      status: "opened_in_storage",
      tray_uuid: "",
      tag_uid: "",
      current_remaining_g: null,
      manual_location: "",
      note: "",
    });
    openInventoryDialog("spoolCreate");
  }


  async function createFilamentSpool() {
    await withLoading(async () => {
      const spool = await apiRequest<FilamentSpool>("/filament/spools", {
        method: "POST",
        body: JSON.stringify({
          sku_id: filamentSpoolForm.sku_id || null,
          status: filamentSpoolForm.status,
          official_spool_uid: filamentSpoolForm.tray_uuid || filamentSpoolForm.tag_uid || null,
          actual_weight_g: presentationStore().optionalNumber(filamentSpoolForm.current_remaining_g),
          storage_location: filamentSpoolForm.manual_location || null,
          note: filamentSpoolForm.note || null,
        }),
      });
      selectedFilamentSpoolId.value = spool.id;
      filamentSpoolForm.tray_uuid = "";
      filamentSpoolForm.tag_uid = "";
      filamentSpoolForm.current_remaining_g = null;
      filamentSpoolForm.manual_location = "";
      filamentSpoolForm.note = "";
      closeInventoryDialog();
      await loadInventory();
      message.value = t("inventory.spoolCreated");
    });
  }


  async function openFilamentSpoolDialog(spool: FilamentSpool | Record<string, any>) {
    await selectFilamentSpool(spool);
    openInventoryDialog("spoolDetail", spool);
  }


  async function selectFilamentSpool(spool: FilamentSpool | Record<string, any>) {
    selectedFilamentSpoolId.value = Number(spool.id);
    quantityAdjustForm.current_remaining_g = spool.actual_weight_g ?? spool.current_remaining_g ?? null;
    quantityAdjustForm.remain_percent = spool.last_ams_remain_percent ?? null;
    quantityAdjustForm.note = "";
    locationAdjustForm.printer_id = spool.current_printer_id ?? null;
    locationAdjustForm.ams_id = spool.current_ams_id || "";
    locationAdjustForm.tray_id = spool.current_tray_id || "";
    locationAdjustForm.manual_location = spool.storage_location || spool.manual_location || "";
    locationAdjustForm.note = "";
    await loadFilamentSpoolEvents(Number(spool.id));
  }


  async function adjustSelectedFilamentQuantity() {
    if (!selectedFilamentSpool.value) return;
    let actualWeight = presentationStore().optionalNumber(quantityAdjustForm.current_remaining_g);
    if (actualWeight === null) {
      const percent = presentationStore().optionalNumber(quantityAdjustForm.remain_percent);
      const nominal = numeric(
        selectedFilamentSpool.value.nominal_weight_g ?? selectedFilamentSpool.value.initial_net_weight_g,
      );
      if (percent !== null && nominal !== null && nominal > 0) {
        actualWeight = (nominal * percent) / 100;
      }
    }
    if (actualWeight === null) {
      error.value = t("inventory.remainingWeightRequired");
      return;
    }
    await withLoading(async () => {
      await apiRequest<FilamentSpool>(`/filament/spools/${selectedFilamentSpool.value!.id}/weight`, {
        method: "POST",
        body: JSON.stringify({
          actual_weight_g: actualWeight,
          note: quantityAdjustForm.note || null,
        }),
      });
      quantityAdjustForm.note = "";
      closeInventoryDialog();
      await loadInventory();
      message.value = t("inventory.quantityAdjusted");
    });
  }


  async function updateSelectedFilamentLocation() {
    if (!selectedFilamentSpool.value) return;
    await withLoading(async () => {
      await apiRequest<FilamentSpool>(`/filament/spools/${selectedFilamentSpool.value!.id}/location`, {
        method: "POST",
        body: JSON.stringify({
          printer_id: presentationStore().optionalNumber(locationAdjustForm.printer_id),
          ams_id: locationAdjustForm.ams_id || null,
          tray_id: locationAdjustForm.tray_id || null,
          storage_location: locationAdjustForm.manual_location || null,
          note: locationAdjustForm.note || null,
        }),
      });
      locationAdjustForm.note = "";
      closeInventoryDialog();
      await loadInventory();
      message.value = t("inventory.locationSaved");
    });
  }


  async function updateFilamentSpoolStatus(spool: FilamentSpool | Record<string, any>, status: string) {
    const spoolId = Number(spool.id);
    if (!Number.isFinite(spoolId)) return;
    const confirmed = window.confirm(t(`inventory.confirmStatus.${status}`, { id: spoolId }));
    if (!confirmed) return;
    await withLoading(async () => {
      const updated = await apiRequest<FilamentSpool>(`/filament/spools/${spoolId}/status`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      selectedFilamentSpoolId.value = updated.id;
      closeInventoryDialog();
      await loadInventory();
      message.value = t(`inventory.statusUpdated.${status}`);
    });
  }


  async function resolveFilamentUidConflict(spool: FilamentSpool | Record<string, any>, action: string) {
    const spoolId = Number(spool.id);
    if (!Number.isFinite(spoolId)) return;
    const confirmed = window.confirm(t(`inventory.uidConflictConfirm.${action}`, { id: spoolId }));
    if (!confirmed) return;
    await withLoading(async () => {
      const updated = await apiRequest<FilamentSpool>(`/filament/spools/${spoolId}/resolve-uid-conflict`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      selectedFilamentSpoolId.value = updated.id;
      closeInventoryDialog();
      await loadInventory();
      message.value = t(`inventory.uidConflictResolved.${action}`);
    });
  }


  async function bindSlot() {
    if (!bindForm.slot_id || !bindForm.spool_id) return;
    await withLoading(async () => {
      await apiRequest(`/ams/slots/${Number(bindForm.slot_id)}/bind`, {
        method: "POST",
        body: JSON.stringify({ spool_id: Number(bindForm.spool_id) }),
      });
      await loadInventory();
      message.value = t("message.slotBound");
    });
  }


  function normalizeFilamentColorContext(context: Record<string, any> | null | undefined) {
    if (!context) return null;
    const brandId = numeric(context.brand_id ?? context.filament_brand_id);
    const brandName = context.brand_name ?? context.filament_brand_name;
    const typeSeriesId = numeric(context.type_series_id ?? context.filament_type_series_id);
    const material = String(context.material ?? context.filament_material ?? context.tray_type ?? "").trim();
    const series = String(context.series ?? context.filament_series ?? context.tray_sub_brands ?? "").trim();
    if (brandId === null || !material || !series) return null;
    return {
      brand_id: Math.round(brandId),
      brand_name: String(brandName || ""),
      type_series_id: typeSeriesId === null ? findTypeSeriesId(material, series, Math.round(brandId)) : Math.round(typeSeriesId),
      material,
      series,
    };
  }


  function filamentColorMappingKey(context: Record<string, any> | null | undefined, value: unknown): string | null {
    const normalized = normalizeFilamentColorContext(context);
    const hex = normalizeFilamentHex(value);
    if (!normalized || !hex) return null;
    return [normalized.brand_id, normalized.material.toLowerCase(), normalized.series.toLowerCase(), hex].join("|");
  }


  function mappedFilamentColorName(value: unknown, context?: Record<string, any> | null): string | null {
    const key = filamentColorMappingKey(context, value);
    const mapping = key ? filamentColorMappingByContext.value.get(key) : null;
    return mapping?.color_name || mapping?.official_name || null;
  }


  function filamentColorDisplay(value: unknown, fallbackName?: unknown, context?: Record<string, any> | null): string {
    const mapped = mappedFilamentColorName(value, context);
    if (mapped) return mapped;
    if (fallbackName) return String(fallbackName);
    const hex = normalizeFilamentHex(value);
    return hex || formatCell(value);
  }


  function colorNeedsMapping(value: unknown, context?: Record<string, any> | null): boolean {
    const hex = normalizeFilamentHex(value);
    const ownName = String(
      context?.color_name ||
        context?.official_name ||
        context?.tray_color_name ||
        context?.filament_color_name ||
        context?.color_display_name ||
        "",
    ).trim();
    if (hex && ownName) return false;
    const key = filamentColorMappingKey(context, value);
    return Boolean(key && !filamentColorMappingByContext.value.has(key));
  }


  function slotFilamentColorContext(slot: Record<string, any> | null | undefined) {
    if (!slot) return null;
    const direct = normalizeFilamentColorContext(slot);
    if (direct) return direct;
    return filamentSpools.value.find((item) => item.id === Number(slot.filament_spool_id)) || null;
  }


  function filamentSkuMatchesColorState(sku: FilamentSku, state: string): boolean {
    const hasName = Boolean(String(sku.color_name || "").trim());
    const hasHex = Boolean(normalizeFilamentHex(sku.color_hex || sku.color_value));
    if (state === "complete") return hasName && hasHex;
    if (state === "incomplete") return !hasName || !hasHex;
    if (state === "missing_name") return !hasName;
    if (state === "missing_hex") return !hasHex;
    return true;
  }


  function filamentSkuSearchText(sku: FilamentSku): string {
    const weight = numeric(sku.nominal_weight_g);
    return [
      sku.id,
      sku.brand_name,
      filamentBrandDisplay(sku.brands),
      sku.material,
      sku.series,
      filamentTypeSeriesDisplay(sku.type_series),
      sku.color_name,
      sku.color_hex,
      sku.color_value,
      sku.nominal_weight_g,
      weight !== null ? `${Math.round(weight)}g` : null,
      weight !== null ? `${Math.round(weight)} g` : null,
      weight !== null && weight % 1000 === 0 ? `${Math.round(weight / 1000)}kg` : null,
      sku.sealed_quantity,
      sku.note,
    ]
      .map((value) => String(value ?? ""))
      .join(" ")
      .toLowerCase();
  }


  function filamentSkuLabel(sku: FilamentSku | Record<string, any>): string {
    const colorValue = sku.color_hex || sku.color_value;
    const color = colorValue || sku.color_name ? filamentColorDisplay(colorValue, sku.color_name, sku) : null;
    return [sku.brand_name, sku.series, sku.material, color]
      .filter(Boolean)
      .join(" · ") || `SKU ${sku.id}`;
  }


  function filamentSkuCompactLabel(sku: FilamentSku): string {
    const colorValue = sku.color_hex || sku.color_value;
    const color = colorValue || sku.color_name ? filamentColorDisplay(colorValue, sku.color_name, sku) : null;
    const weight = numeric(sku.nominal_weight_g);
    return [color || `SKU ${sku.id}`, weight !== null ? `${Math.round(weight)} g` : null].filter(Boolean).join(" · ");
  }


  function filamentSpoolLabel(spool: FilamentSpool | Record<string, any> | null | undefined): string {
    if (!spool) return "—";
    const colorValue = spool.color_hex || spool.color_value;
    const color = colorValue || spool.color_name ? filamentColorDisplay(colorValue, spool.color_name, spool) : null;
    return [spool.brand_name, spool.series, spool.material, color].filter(Boolean).join(" · ") || spool.sku_label || `#${spool.id}`;
  }


  function filamentSpoolCurrentPlace(spool: FilamentSpool | Record<string, any> | null | undefined): string {
    if (!spool) return "—";
    const amsRow = filamentAmsRows.value.find((row) => row.spool?.id === spool.id);
    if (amsRow) return filamentAmsSlotLocationLabel(amsRow.slot);
    return filamentSpoolLocation(spool);
  }


  function filamentAmsFilamentLabel(slot: Record<string, any>, spool: FilamentSpool | Record<string, any> | null | undefined): string {
    return spool ? filamentSpoolLabel(spool) : slotMaterialColorLabel(slot);
  }


  function printerDisplayName(printerId: unknown): string {
    const id = numeric(printerId);
    const printer = printersStore().printers.find((item) => item.id === id);
    return printer?.name || formatCell(printerId);
  }


  function amsUnitForSlot(slot: Record<string, any> | null | undefined): Record<string, any> | null {
    if (!slot) return null;
    const overview = navigationStore().activeView === "ams"
      ? amsStore().amsOverview
      : inventoryAmsOverviews.value[String(slot.printer_id)] || amsStore().amsOverview;
    if (overview) return overview.units.find((unit) => String(unit.ams_id) === String(slot.ams_id)) || null;
    return null;
  }


  function filamentAmsSlotLocationLabel(slot: Record<string, any> | null | undefined): string {
    if (!slot) return "—";
    const unit = amsUnitForSlot(slot);
    if (unit) return `${amsStore().amsTitle(unit)} / ${amsStore().slotDisplayLabel(slot)}`;
    return slot.location_label || `AMS ${formatCell(slot.ams_id)} / ${amsStore().slotDisplayLabel(slot)}`;
  }


  function filamentTypeSeriesLabel(row: FilamentTypeSeries | Record<string, any> | null | undefined): string {
    if (!row) return "—";
    return [row.material_type, row.series_name].filter(Boolean).join(" · ") || `#${row.id}`;
  }


  function filamentTypeSeriesDisplay(rows: Record<string, any>[] | undefined): string {
    if (!rows?.length) return "—";
    return rows.map((row) => filamentTypeSeriesLabel(row)).join(", ");
  }


  function filamentBrandDisplay(rows: Record<string, any>[] | undefined): string {
    if (!rows?.length) return "—";
    return rows.map((row) => row.name).filter(Boolean).join(", ") || "—";
  }


  function findTypeSeriesId(material: unknown, series: unknown, brandId?: number | null): number | null {
    const materialText = String(material || "").trim().toLowerCase();
    const seriesText = String(series || "").trim().toLowerCase();
    const row = filamentTypeSeries.value.find(
      (item) =>
        item.material_type.toLowerCase() === materialText &&
        item.series_name.toLowerCase() === seriesText &&
        (!brandId || item.brand_id === brandId),
    );
    return row?.id ?? null;
  }


  function slotColorName(slot: Record<string, any> | null | undefined): string | null {
    if (!slot) return null;
    const explicit = slot.tray_color_name || slot.color_name || slot.filament_color_name || slot.color_display_name;
    if (explicit) return String(explicit);
    const name = slot.tray_id_name;
    if (!name) return null;
    const text = String(name).trim();
    const compact = text.replace(/[-_]/g, "");
    if (/^[a-z0-9]+$/i.test(compact) && /\d/.test(compact) && !/\s/.test(text)) return null;
    const parts = text.split(/\s+/);
    let startIndex = -1;
    for (const prefix of [slot.series, slot.material]) {
      const prefixParts = String(prefix || "")
        .trim()
        .split(/\s+/)
        .filter(Boolean)
        .map((part) => part.toLowerCase());
      if (!prefixParts.length) continue;
      const lowerParts = parts.map((part) => part.toLowerCase());
      for (let index = 0; index <= lowerParts.length - prefixParts.length; index += 1) {
        if (prefixParts.every((part, offset) => lowerParts[index + offset] === part)) {
          startIndex = index + prefixParts.length;
          break;
        }
      }
      if (startIndex >= 0) break;
    }
    const candidate = startIndex >= 0 ? parts.slice(startIndex).join(" ").trim() : text;
    const hex = String(slot.color || slot.tray_color || "").replace("#", "").toLowerCase();
    if (candidate.replace("#", "").toLowerCase() === hex) return null;
    return candidate || null;
  }


  function slotColorLabel(slot: Record<string, any> | null | undefined): string {
    const rawColor = slot?.color || slot?.tray_color;
    return mappedFilamentColorName(rawColor, slotFilamentColorContext(slot)) || slotColorName(slot) || formatCell(normalizeFilamentHex(rawColor) || rawColor);
  }


  function slotMaterialColorLabel(slot: Record<string, any> | null | undefined): string {
    if (!slot) return "—";
    return [slot.material, slot.series, slotColorLabel(slot)].filter(Boolean).join(" · ") || formatCell(slot.color || slot.tray_color);
  }


  function filamentSpoolLocation(spool: FilamentSpool | Record<string, any> | null | undefined): string {
    if (!spool) return "—";
    if (spool.current_ams_id || spool.current_tray_id) {
      return `AMS ${formatCell(spool.current_ams_id)} / ${t("form.slotId")} ${formatCell(spool.current_tray_id)}`;
    }
    return spool.storage_location || spool.manual_location || "—";
  }


  function filamentSpoolLastLocation(spool: FilamentSpool | Record<string, any> | null | undefined): string {
    if (!spool) return "—";
    const current = filamentSpoolLocation(spool);
    if (current !== "—") return current;
    const last = presentationStore().record(spool.last_location || spool.config?.last_location);
    if (last.ams_id || last.tray_id) {
      return `AMS ${formatCell(last.ams_id)} / ${t("form.slotId")} ${formatCell(last.tray_id)}`;
    }
    return presentationStore().firstText(last.storage_location, spool.storage_location, spool.manual_location) || "—";
  }


  function filamentSpoolHistoryTime(spool: FilamentSpool | Record<string, any> | null | undefined): string {
    if (!spool) return "—";
    const value =
      spool.status === "empty"
        ? spool.empty_at || spool.config?.empty_at || spool.status_changed_at || spool.updated_at
        : spool.archived_at || spool.config?.archived_at || spool.status_changed_at || spool.updated_at;
    return formatCell(value);
  }


  function filamentSpoolStatusLabel(status: unknown): string {
    if (status === "empty") return t("inventory.status.empty");
    if (status === "archived") return t("inventory.status.archived");
    return presentationStore().displayCell(status);
  }


  function filamentSpoolNeedsUidConflictResolution(spool: FilamentSpool | Record<string, any> | null | undefined): boolean {
    return Boolean(spool?.config?.review_reason === "archived_uid_reappeared");
  }


  function filamentSkuReviewDescription(spool: FilamentSpool | Record<string, any> | null | undefined): string {
    if (filamentSpoolNeedsUidConflictResolution(spool)) return t("inventory.uidConflictDescription");
    if (spool?.config?.sku_review_reason === "ams_filament_change") return t("inventory.confirmSkuReplacementDescription");
    return t("inventory.confirmSkuDescription");
  }


  function skuSealedWeight(sku: FilamentSku | Record<string, any>): number {
    return Number(sku.sealed_quantity || 0) * (numeric(sku.nominal_weight_g) || 0);
  }


  function skuOpenedWeight(sku: FilamentSku | Record<string, any>): number {
    return filamentSpools.value
      .filter((spool) => spool.sku_id === sku.id && !["empty", "archived"].includes(spool.status))
      .reduce((total, spool) => total + (filamentSpoolRemainingWeight(spool) ?? numeric(spool.nominal_weight_g) ?? 0), 0);
  }


  async function jumpToInventorySection(id: string) {
    await nextTick();
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }


  function toggleInventorySort(table: string, key: string) {
    const state = inventoryTableSorts[table] || { key: "id", direction: "asc" as SortDirection };
    inventoryTableSorts[table] = {
      key,
      direction: state.key === key && state.direction === "asc" ? "desc" : "asc",
    };
  }


  function inventorySortIndicator(table: string, key: string): string {
    const state = inventoryTableSorts[table];
    if (!state || state.key !== key) return "";
    return state.direction === "asc" ? "↑" : "↓";
  }


  function sortInventoryRows<T>(rows: readonly T[], table: string): T[] {
    const state = inventoryTableSorts[table] || { key: "id", direction: "asc" as SortDirection };
    const direction = state.direction === "desc" ? -1 : 1;
    return [...rows].sort((left, right) => {
      const primary = compareInventoryValues(
        inventorySortValue(table, left, state.key),
        inventorySortValue(table, right, state.key),
      );
      if (primary !== 0) return primary * direction;
      return compareInventoryValues(inventoryRowId(left), inventoryRowId(right));
    });
  }


  function inventorySortValue(table: string, row: unknown, key: string): unknown {
    const item = row as Record<string, any>;
    if (table === "needsLocation") {
      if (key === "id") return item.id;
      if (key === "spool") return filamentSpoolLabel(item);
      if (key === "location") return filamentSpoolLocation(item);
      if (key === "identity") return item.official_spool_uid || item.identity_key;
    }
    if (table === "pendingConfirm") {
      if (key === "id") return item.id;
      if (key === "spool") return filamentSpoolLabel(item);
      if (key === "remaining") return filamentSpoolRemainingWeight(item) ?? numeric(item.last_ams_remain_percent);
      if (key === "location") return filamentSpoolCurrentPlace(item);
      if (key === "status") return filamentSpoolStatusLabel(item.status);
    }
    if (table === "sealedStock" || table === "skus") {
      if (key === "id") return item.id;
      if (key === "filament") return filamentSkuLabel(item);
      if (key === "brand") return filamentBrandDisplay(item.brands) || item.brand_name;
      if (key === "material") return filamentTypeSeriesDisplay(item.type_series) || [item.material, item.series].filter(Boolean).join(" ");
      if (key === "color") return filamentColorDisplay(item.color_hex || item.color_value, item.color_name, item);
      if (key === "weight") return item.nominal_weight_g;
      if (key === "sealed") return item.sealed_quantity;
    }
    if (table === "amsLoaded") {
      const slot = item.slot || {};
      const spool = item.spool || null;
      if (key === "printer") return slot.printer_name || printerDisplayName(slot.printer_id);
      if (key === "slot") return filamentAmsSlotLocationLabel(slot);
      if (key === "filament") return filamentAmsFilamentLabel(slot, spool);
      if (key === "remaining") return filamentAmsRemainingWeight(slot, spool) ?? numeric(slot.remain);
      if (key === "status") return filamentAmsState(slot, spool);
    }
    if (table === "openedUnused") {
      if (key === "id") return item.id;
      if (key === "spool") return filamentSpoolLabel(item);
      if (key === "status") return filamentSpoolStatusLabel(item.status);
      if (key === "remaining") return filamentSpoolRemainingWeight(item) ?? numeric(item.last_ams_remain_percent);
      if (key === "location") return filamentSpoolLocation(item);
      if (key === "identity") return item.identity_key || item.official_spool_uid;
    }
    if (table === "history") {
      if (key === "id") return item.id;
      if (key === "spool") return filamentSpoolLabel(item);
      if (key === "status") return filamentSpoolStatusLabel(item.status);
      if (key === "location") return filamentSpoolLastLocation(item);
      if (key === "remaining") return filamentSpoolRemainingWeight(item) ?? numeric(item.last_ams_remain_percent);
      if (key === "time") return filamentSpoolHistoryTime(item);
      if (key === "note") return item.note;
    }
    if (table === "brands") {
      if (key === "id") return item.id;
      if (key === "brand") return item.name;
      if (key === "aliases") return (item.aliases || []).join(", ");
      if (key === "typeSeries") return item.type_series_count;
      if (key === "skus") return item.sku_count;
      if (key === "spools") return item.spool_count;
      if (key === "note") return item.note;
    }
    if (table === "typeSeries") {
      if (key === "id") return item.id;
      if (key === "brand") return filamentBrandDisplay(item.brands) || item.brand_name;
      if (key === "material") return filamentTypeSeriesLabel(item);
      if (key === "emptyWeight") return item.empty_spool_weight_g;
      if (key === "skus") return item.sku_count;
      if (key === "spools") return item.spool_count;
    }
    if (table === "colorMappings") {
      if (key === "id") return item.id;
      if (key === "brand") return item.brand_name;
      if (key === "material") return [item.material_type || item.material, item.series_name || item.series].filter(Boolean).join(" ");
      if (key === "hex") return item.color_hex || item.hex_value;
      if (key === "color") return item.color_name || item.official_name;
      if (key === "note") return item.note;
    }
    if (table === "colorGaps") {
      if (key === "id") return item.sku_id;
      if (key === "brand") return filamentBrandDisplay(item.brands);
      if (key === "material") return filamentTypeSeriesDisplay(item.type_series);
      if (key === "color") return item.color_name;
      if (key === "hex") return item.color_hex;
      if (key === "source") return (item.missing || []).join(", ");
    }
    return item[key] ?? inventoryRowId(row);
  }


  function inventoryRowId(row: unknown): unknown {
    const item = row as Record<string, any>;
    return item.id ?? item.sku_id ?? item.slot?.id ?? item.slot?.global_tray_id ?? item.slot?.tray_id;
  }


  function compareInventoryValues(left: unknown, right: unknown): number {
    const leftEmpty = left === null || left === undefined || left === "";
    const rightEmpty = right === null || right === undefined || right === "";
    if (leftEmpty && rightEmpty) return 0;
    if (leftEmpty) return 1;
    if (rightEmpty) return -1;
    const leftNumber = typeof left === "number" ? left : null;
    const rightNumber = typeof right === "number" ? right : null;
    if (leftNumber !== null && rightNumber !== null) return leftNumber - rightNumber;
    return pinyinCollator.compare(String(left), String(right));
  }


  function filamentAmsState(slot: Record<string, any>, spool: FilamentSpool | null): string {
    if (slot.is_transitioning) return t("inventory.transitioning");
    if (!slot.filament_spool_id && slot.identity_source === "manual_required") return t("inventory.manualRequired");
    if (isFilamentSpoolSkuReviewDeferred(spool)) return t("inventory.waitingRfidReview");
    if (isFilamentSpoolPendingConfirm(spool)) return t("inventory.pendingConfirm");
    if (spool) return t("inventory.bound");
    return t("inventory.unbound");
  }


  function isFilamentSpoolPendingConfirm(spool: FilamentSpool | Record<string, any> | null | undefined): boolean {
    return Boolean(spool && (spool.status === "unknown" || spool.config?.needs_sku_review));
  }


  function isFilamentSpoolSkuReviewDeferred(spool: FilamentSpool | Record<string, any> | null | undefined): boolean {
    if (!isFilamentSpoolPendingConfirm(spool)) return false;
    const slot = filamentSpoolCurrentAmsSlot(spool);
    if (!slot) return false;
    const noPayload = !amsSlotHasStableFilamentPayload(slot) && !spool?.sku_id;
    if (!noPayload) return false;
    return isAmsSlotRfidOrTransitioning(slot) || isPrinterPrintingOrPaused(slot.printer_id ?? spool?.current_printer_id);
  }


  function filamentSpoolCurrentAmsSlot(spool: FilamentSpool | Record<string, any> | null | undefined): Record<string, any> | null {
    if (!spool) return null;
    return (
      amsStore().amsSlots.find((slot) => Number(slot.filament_spool_id) === Number(spool.id)) ||
      amsStore().amsSlots.find(
        (slot) =>
          Number(slot.printer_id) === Number(spool.current_printer_id) &&
          String(slot.ams_id) === String(spool.current_ams_id) &&
          String(slot.tray_id) === String(spool.current_tray_id),
      ) ||
      null
    );
  }


  function amsSlotHasStableFilamentPayload(slot: Record<string, any> | null | undefined): boolean {
    if (!slot) return false;
    const raw = presentationStore().record(slot.raw);
    const directFields = [
      slot.material,
      slot.series,
      slot.color,
      slot.tray_color,
      slot.color_name,
      slot.tray_color_name,
      raw.tray_type,
      raw.filament_type,
      raw.tray_sub_brands,
      raw.tray_info_idx,
      raw.tray_color,
      raw.color,
      raw.tray_color_name,
      raw.color_name,
      raw.filament_color_name,
      raw.color_display_name,
    ];
    if (directFields.some((value) => String(value ?? "").trim())) return true;
    const cols = Array.isArray(raw.cols) ? raw.cols : [];
    return cols.some((value) => String(value ?? "").trim());
  }


  function isAmsSlotRfidOrTransitioning(slot: Record<string, any> | null | undefined): boolean {
    if (!slot) return false;
    if (slot.is_transitioning) return true;
    const raw = presentationStore().record(slot.raw);
    const state = String(slot.state_name || slot.tray_state_name || slot.slot_state || slot.state || raw.state || raw.tray_state || "")
      .trim()
      .toLowerCase();
    return ["4", "5", "10", "17", "21", "25", "27", "rfid_reading", "reading", "filament_present"].includes(state) ||
      state.includes("rfid") ||
      state.includes("reading") ||
      state.includes("transition");
  }


  function isPrinterPrintingOrPaused(printerId: unknown): boolean {
    const id = numeric(printerId);
    if (id === null) return false;
    const state = inventoryPrinterStates.value[String(Math.round(id))] || {};
    const gcodeState = String(state.gcode_state || presentationStore().record(state.payload).gcode_state || presentationStore().record(presentationStore().record(state.payload).print).gcode_state || "")
      .trim()
      .toUpperCase();
    return ["RUNNING", "PAUSE", "PAUSED", "PREPARE", "SLICING", "M400_PAUSE"].includes(gcodeState);
  }


  return {
    spools,
    filamentBrands,
    filamentTypeSeries,
    filamentColorMappings,
    filamentColorMappingGaps,
    filamentSkus,
    filamentSpools,
    filamentInventorySummary,
    inventoryTab,
    selectedFilamentSpoolId,
    selectedFilamentSpoolEvents,
    inventoryAmsOverviews,
    inventoryPrinterStates,
    inventoryDialog,
    inventoryTableSorts,
    inventoryChartColors,
    filamentBrandForm,
    editingFilamentBrandId,
    filamentTypeSeriesForm,
    editingFilamentTypeSeriesId,
    filamentColorMappingForm,
    editingFilamentColorMappingId,
    filamentSkuForm,
    editingFilamentSkuId,
    skuReviewSourceSpoolId,
    filamentSkuFilters,
    inventoryHistorySearch,
    filamentSpoolForm,
    sealedStockAdjustForm,
    quantityAdjustForm,
    locationAdjustForm,
    dryingEventForm,
    bindForm,
    spoolStatusOptions,
    filamentInventoryTabOptions,
    filamentSpoolStatusOptions,
    inventoryPageOptions,
    quantityAdjustSourceOptions,
    filamentBrandOptions,
    filamentRequiredBrandOptions,
    filamentTypeSeriesOptions,
    filamentColorMappingTypeSeriesOptions,
    filamentSkuOptions,
    filamentSkuFilterBrandOptions,
    filamentSkuFilterTypeSeriesOptions,
    filamentSkuWeightOptions,
    filamentSkuColorStateOptions,
    filteredFilamentSkus,
    filamentSpoolBrandOptions,
    filamentSpoolTypeSeriesOptions,
    filamentSpoolSkuOptions,
    selectedFilamentSpool,
    filamentAmsRows,
    filamentStockSkus,
    filamentOpenedUnusedSpools,
    sortedNeedsLocationSpools,
    pendingConfirmSpools,
    deferredConfirmSpools,
    sortedPendingConfirmSpools,
    sortedFilamentStockSkus,
    sortedFilamentAmsRows,
    sortedFilamentOpenedUnusedSpools,
    historicalFilamentSpools,
    filteredHistoricalFilamentSpools,
    sortedHistoricalFilamentSpools,
    sortedFilamentBrands,
    sortedFilamentTypeSeries,
    sortedFilteredFilamentSkus,
    sortedFilamentColorMappings,
    sortedFilamentColorMappingGaps,
    inventoryRealSpools,
    inventorySealedWeightG,
    inventoryRealSpoolWeightG,
    inventoryTotalWeightG,
    inventoryTotalRolls,
    inventoryPendingConfirmCount,
    inventoryTypeBreakdown,
    inventoryMaxTypeWeightG,
    inventoryTypePieStyle,
    filamentColorMappingByContext,
    unmappedFilamentColors,
    loadInventory,
    loadInventoryAmsGlobal,
    loadFilamentSpoolEvents,
    openInventoryDialog,
    closeInventoryDialog,
    openFilamentBrandCreate,
    resetFilamentBrandForm,
    editFilamentBrand,
    saveFilamentBrand,
    deleteFilamentBrand,
    openFilamentTypeSeriesCreate,
    resetFilamentTypeSeriesForm,
    editFilamentTypeSeries,
    saveFilamentTypeSeries,
    deleteFilamentTypeSeries,
    openFilamentColorMappingCreate,
    resetFilamentColorMappingForm,
    editFilamentColorMapping,
    startFilamentColorMapping,
    saveFilamentColorMapping,
    deleteFilamentColorMapping,
    filamentSkuPayload,
    openFilamentSkuCreate,
    resetFilamentSkuForm,
    editFilamentSku,
    cancelFilamentSkuEdit,
    resetFilamentSkuFilters,
    saveFilamentSku,
    deleteFilamentSku,
    openSealedStockAdjust,
    saveSealedStockAdjust,
    adjustFilamentSkuStock,
    openConfirmFilamentSpoolSku,
    editSkuFromConfirmDialog,
    prepareFilamentSkuCreateFromSpool,
    inventoryDialogSkuLabel,
    inventoryDialogSpoolLabel,
    confirmFilamentSpoolSku,
    openCreateFilamentSpoolDialog,
    createFilamentSpool,
    openFilamentSpoolDialog,
    selectFilamentSpool,
    adjustSelectedFilamentQuantity,
    updateSelectedFilamentLocation,
    updateFilamentSpoolStatus,
    resolveFilamentUidConflict,
    bindSlot,
    normalizeFilamentColorContext,
    filamentColorMappingKey,
    mappedFilamentColorName,
    filamentColorDisplay,
    colorNeedsMapping,
    slotFilamentColorContext,
    filamentSkuMatchesColorState,
    filamentSkuSearchText,
    filamentSkuLabel,
    filamentSkuCompactLabel,
    filamentSpoolLabel,
    filamentSpoolCurrentPlace,
    filamentAmsFilamentLabel,
    printerDisplayName,
    amsUnitForSlot,
    filamentAmsSlotLocationLabel,
    filamentTypeSeriesLabel,
    filamentTypeSeriesDisplay,
    filamentBrandDisplay,
    findTypeSeriesId,
    slotColorName,
    slotColorLabel,
    slotMaterialColorLabel,
    filamentSpoolLocation,
    filamentSpoolLastLocation,
    filamentSpoolHistoryTime,
    filamentSpoolStatusLabel,
    filamentSpoolNeedsUidConflictResolution,
    filamentSkuReviewDescription,
    skuSealedWeight,
    skuOpenedWeight,
    jumpToInventorySection,
    toggleInventorySort,
    inventorySortIndicator,
    sortInventoryRows,
    inventorySortValue,
    inventoryRowId,
    compareInventoryValues,
    filamentAmsState,
    isFilamentSpoolPendingConfirm,
    isFilamentSpoolSkuReviewDeferred,
    filamentSpoolCurrentAmsSlot,
    amsSlotHasStableFilamentPayload,
    isAmsSlotRfidOrTransitioning,
    isPrinterPrintingOrPaused,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useInventoryStore, import.meta.hot));
}
