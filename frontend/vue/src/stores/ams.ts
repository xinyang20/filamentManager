import { computed, reactive, ref } from "vue";
import { acceptHMRUpdate, defineStore } from "pinia";
import { apiRequest, numeric } from "../api";
import type { AmsOverview, AmsSensorHistory, AmsSlotHistorySample, FilamentColorMapping, MetricSample, UnifiedEvent } from "../types";
import { useDashboardStore } from "./dashboard";
import { useEventsStore } from "./events";
import { useI18nStore } from "./i18n";
import { useInventoryStore } from "./inventory";
import { usePresentationStore } from "./presentation";
import { usePrintersStore } from "./printers";
import { useUiStore } from "./ui";

export const useAmsStore = defineStore("ams", () => {
  const { t } = useI18nStore();
  const { withLoading } = useUiStore();
  const printersStore = () => usePrintersStore();
  const dashboardStore = () => useDashboardStore();
  const eventsStore = () => useEventsStore();
  const inventoryStore = () => useInventoryStore();
  const presentationStore = () => usePresentationStore();

  const stateSnapshot = ref<Record<string, any> | null>(null);

  const amsSlots = ref<Record<string, any>[]>([]);

  const amsOverview = ref<AmsOverview | null>(null);

  const amsLabelDrafts = reactive<Record<string, string>>({});

  const amsLabelEditing = reactive<Record<string, boolean>>({});

  const amsSensorRange = ref("24");

  const amsSensorHistories = ref<Record<string, AmsSensorHistory>>({});

  const selectedSlot = ref<Record<string, any> | null>(null);

  const selectedSlotHistory = ref<AmsSlotHistorySample[]>([]);

  const amsSensorRangeOptions = computed(() => [
    { label: t("metrics.range6h"), value: "6" },
    { label: t("metrics.range24h"), value: "24" },
    { label: t("metrics.range7d"), value: "168" },
    { label: t("metrics.range30d"), value: "720" },
  ]);

  const amsStats = computed(() => {
    const summary = amsOverview.value?.summary;
    return [
      { label: t("ams.amsCount"), value: summary?.ams_count ?? 0 },
      { label: t("ams.slotCount"), value: summary?.slot_count ?? 0 },
      { label: t("ams.loadedCount"), value: summary?.loaded_count ?? 0 },
      { label: t("ams.emptyCount"), value: summary?.empty_count ?? 0 },
      { label: t("ams.transitioningCount"), value: summary?.transitioning_count ?? 0 },
    ];
  });

  async function loadAms() {
    if (!printersStore().selectedPrinterId) return;
    const [stateResult, overviewResult, slotResult, eventResult, colorMappingResult] = await Promise.all([
      apiRequest<Record<string, any> | null>(`/printers/${printersStore().selectedPrinterId}/state`),
      apiRequest<AmsOverview>(`/printers/${printersStore().selectedPrinterId}/ams/overview`),
      apiRequest<Record<string, any>[]>(`/printers/${printersStore().selectedPrinterId}/ams/slots`),
      apiRequest<UnifiedEvent[]>(`/events?printer_id=${printersStore().selectedPrinterId}&limit=50`),
      apiRequest<FilamentColorMapping[]>("/filament/effective-color-mappings"),
    ]);
    stateSnapshot.value = stateResult;
    amsOverview.value = overviewResult;
    amsSlots.value = slotResult;
    eventsStore().events = eventResult;
    inventoryStore().effectiveFilamentColorMappings = colorMappingResult;
    for (const unit of overviewResult.units) {
      amsLabelDrafts[unit.ams_id] = unit.display_name || "";
      if (!unit.display_name) amsLabelEditing[unit.ams_id] = false;
    }
    await loadAmsSensorHistories();
  }


  async function loadAmsSensorHistories() {
    if (!printersStore().selectedPrinterId || !amsOverview.value) return;
    const entries = await Promise.all(
      amsOverview.value.units
        .filter((unit) => unit.ams_id !== "unknown")
        .map(async (unit) => {
          const history = await apiRequest<AmsSensorHistory>(
            `/printers/${printersStore().selectedPrinterId}/ams/${encodeURIComponent(unit.ams_id)}/sensor-history?hours=${amsSensorRange.value}`,
          );
          return [unit.ams_id, history] as const;
        }),
    );
    amsSensorHistories.value = Object.fromEntries(entries);
  }


  async function saveAmsLabel(unit: Record<string, any>) {
    if (!printersStore().selectedPrinterId) return;
    const displayName = (amsLabelDrafts[String(unit.ams_id)] || "").trim();
    if (!displayName) {
      await clearAmsLabel(unit);
      return;
    }
    await withLoading(async () => {
      await apiRequest(`/printers/${printersStore().selectedPrinterId}/ams-labels/${encodeURIComponent(String(unit.ams_id))}`, {
        method: "PATCH",
        body: JSON.stringify({ display_name: displayName }),
      });
      amsLabelEditing[String(unit.ams_id)] = false;
      await loadAms();
    });
  }


  async function clearAmsLabel(unit: Record<string, any>) {
    if (!printersStore().selectedPrinterId) return;
    await withLoading(async () => {
      await apiRequest(`/printers/${printersStore().selectedPrinterId}/ams-labels/${encodeURIComponent(String(unit.ams_id))}`, {
        method: "DELETE",
      });
      amsLabelDrafts[String(unit.ams_id)] = "";
      amsLabelEditing[String(unit.ams_id)] = false;
      await loadAms();
    });
  }


  async function openSlotDetails(slot: Record<string, any>) {
    if (!printersStore().selectedPrinterId) return;
    selectedSlot.value = slot;
    const params = new URLSearchParams({ ams_id: String(slot.ams_id), tray_id: String(slot.tray_id), limit: "80" });
    selectedSlotHistory.value = await apiRequest<AmsSlotHistorySample[]>(
      `/printers/${printersStore().selectedPrinterId}/ams/history?${params.toString()}`,
    );
  }


  function amsTone(unit: Record<string, any>) {
    if (unit.ams_type_name === "AMS HT") return "ht";
    if (unit.ams_type_name === "AMS 2 Pro") return "pro";
    if (unit.ams_type_name === "unknown") return "unknown";
    return "standard";
  }


  function amsIsDrying(unit: Record<string, any>) {
    const status = String(unit.dry_status_name || unit.dry_status || "").trim().toLowerCase();
    if (status === "drying" || status === "烘干中") return true;
    if (status) return false;
    const dryTime = numeric(unit.dry_time);
    return dryTime !== null && dryTime > 0;
  }


  function slotKey(slot: Record<string, any>) {
    return `${slot.ams_id}-${slot.tray_id}-${slot.id || "slot"}`;
  }


  function amsSectionKey(unit: Record<string, any>) {
    return `ams.unit.${unit.ams_id}`;
  }


  function amsTitle(unit: Record<string, any>) {
    return unit.display_name || unit.ams_type_name || "AMS";
  }


  function slotDisplayLabel(slot: Record<string, any> | null | undefined) {
    if (!slot) return "--";
    const userTray = numeric(slot.user_tray_id);
    if (userTray !== null) return `${t("table.tray")} ${Math.round(userTray)}`;
    const tray = numeric(slot.tray_id);
    if (tray !== null && tray >= 0 && tray < 255) return `${t("table.tray")} ${Math.round(tray) + 1}`;
    return presentationStore().softCell(slot.tray_id);
  }


  function activeSlotDisplayLabel(slot: Record<string, any> | null | undefined) {
    if (!slot) return "--";
    return `AMS #${presentationStore().softCell(slot.ams_id)} / ${slotDisplayLabel(slot)}`;
  }


  function amsHumidity(unit: Record<string, any>) {
    return unit.humidity_raw ?? unit.humidity;
  }


  function amsHumidityLabel(unit: Record<string, any>) {
    const text = presentationStore().softCell(amsHumidity(unit));
    return text === "--" ? "--" : `${text}%`;
  }


  function amsPageUnitVisual(unit: Record<string, any>, index: number) {
    return dashboardStore().dashboardAmsUnitVisual(unit, presentationStore().arrayOfRecord(unit.slots), index, presentationStore().record(unit.active_slot));
  }


  function toggleAmsLabelEditor(unit: Record<string, any>) {
    const key = String(unit.ams_id);
    amsLabelDrafts[key] = String(unit.display_name || "");
    amsLabelEditing[key] = !amsLabelEditing[key];
  }


  function amsSensorChartItems(amsId: string): MetricSample[] {
    const history = amsSensorHistories.value[amsId];
    if (!history) return [];
    return history.points.flatMap((point, index) => {
      const items: MetricSample[] = [];
      if (point.temperature !== null && point.temperature !== undefined) {
        items.push({
          id: index * 2,
          metric: `ams.${amsId}.temperature`,
          value_float: point.temperature,
          unit: "celsius",
          sampled_at: point.sampled_at,
        });
      }
      if (point.humidity !== null && point.humidity !== undefined) {
        items.push({
          id: index * 2 + 1,
          metric: `ams.${amsId}.humidity`,
          value_float: point.humidity,
          unit: "percent",
          sampled_at: point.sampled_at,
        });
      }
      return items;
    });
  }


  function slotHistoryChanges(kind: "material" | "remain" | "rfid" | "calibration") {
    const rows: { time: string; before: string; after: string }[] = [];
    for (let index = 1; index < selectedSlotHistory.value.length; index += 1) {
      const previous = selectedSlotHistory.value[index - 1];
      const current = selectedSlotHistory.value[index];
      const before = slotHistoryValue(previous, kind);
      const after = slotHistoryValue(current, kind);
      if (before !== after) rows.push({ time: current.sampled_at, before, after });
    }
    return rows.slice(-8).reverse();
  }


  function slotHistoryValue(sample: AmsSlotHistorySample, kind: string) {
    if (kind === "material") return `${presentationStore().softCell(sample.material)} / ${inventoryStore().filamentColorDisplay(sample.color)}`;
    if (kind === "remain") return presentationStore().softCell(sample.remain);
    if (kind === "rfid") return presentationStore().softCell(sample.rfid_status);
    return `K ${presentationStore().softCell(sample.k)} / ${presentationStore().softCell(sample.cali_idx)}`;
  }


  return {
    stateSnapshot,
    amsSlots,
    amsOverview,
    amsLabelDrafts,
    amsLabelEditing,
    amsSensorRange,
    amsSensorHistories,
    selectedSlot,
    selectedSlotHistory,
    amsSensorRangeOptions,
    amsStats,
    loadAms,
    loadAmsSensorHistories,
    saveAmsLabel,
    clearAmsLabel,
    openSlotDetails,
    amsTone,
    amsIsDrying,
    slotKey,
    amsSectionKey,
    amsTitle,
    slotDisplayLabel,
    activeSlotDisplayLabel,
    amsHumidity,
    amsHumidityLabel,
    amsPageUnitVisual,
    toggleAmsLabelEditor,
    amsSensorChartItems,
    slotHistoryChanges,
    slotHistoryValue,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useAmsStore, import.meta.hot));
}
