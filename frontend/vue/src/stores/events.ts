import { computed, reactive, ref } from "vue";
import { acceptHMRUpdate, defineStore, storeToRefs } from "pinia";
import { apiRequest, numeric } from "../api";
import type { HmsCodeInfo, HmsCodeStats, UnifiedEvent } from "../types";
import { useI18nStore } from "./i18n";
import { usePresentationStore } from "./presentation";
import { usePrintersStore } from "./printers";

export const useEventsStore = defineStore("events", () => {
  const i18nStore = useI18nStore();
  const { locale } = storeToRefs(i18nStore);
  const { t } = i18nStore;
  const printersStore = () => usePrintersStore();
  const presentationStore = () => usePresentationStore();

  const events = ref<UnifiedEvent[]>([]);

  const eventFilters = reactive({
    type: "",
    severity: "",
    active: "",
  });

  const hmsCodes = ref<HmsCodeInfo[]>([]);

  const selectedHmsStats = ref<HmsCodeStats | null>(null);

  const selectedHms = ref<Record<string, any> | null>(null);

  const selectedEvent = ref<UnifiedEvent | null>(null);

  const eventSeverityOptions = computed(() => [
    { label: t("events.allSeverities"), value: "" },
    { label: t("values.info"), value: "info" },
    { label: t("values.warning"), value: "warning" },
    { label: t("values.error"), value: "error" },
  ]);

  const eventActiveOptions = computed(() => [
    { label: t("events.allStates"), value: "" },
    { label: t("common.unresolved"), value: "active" },
    { label: t("common.resolved"), value: "inactive" },
  ]);

  const filteredEvents = computed(() => {
    return events.value.filter((item) => {
      if (eventFilters.type && item.type !== eventFilters.type) return false;
      if (eventFilters.severity && item.severity !== eventFilters.severity) return false;
      if (eventFilters.active === "active" && item.active !== true) return false;
      if (eventFilters.active === "inactive" && item.active !== false) return false;
      return true;
    });
  });

  async function loadEvents() {
    const params = new URLSearchParams({ limit: "120" });
    if (printersStore().selectedPrinterId) params.set("printer_id", String(printersStore().selectedPrinterId));
    if (eventFilters.type) params.set("type", eventFilters.type);
    if (eventFilters.severity) params.set("severity", eventFilters.severity);
    if (eventFilters.active === "active") params.set("active", "true");
    if (eventFilters.active === "inactive") params.set("active", "false");
    events.value = await apiRequest<UnifiedEvent[]>(`/events?${params.toString()}`);
  }


  async function openHmsDetails(item: Record<string, any>) {
    selectedHms.value = item;
    selectedHmsStats.value = null;
    if (!hmsCodes.value.length) {
      hmsCodes.value = await apiRequest<HmsCodeInfo[]>("/hms/codes");
    }
    const shortCode = item.short_code || item.code;
    if (shortCode) {
      const params = new URLSearchParams({ days: "30" });
      if (printersStore().selectedPrinterId) params.set("printer_id", String(printersStore().selectedPrinterId));
      selectedHmsStats.value = await apiRequest<HmsCodeStats>(`/hms/codes/${encodeURIComponent(String(shortCode))}/stats?${params.toString()}`);
    }
  }


  function hmsKnowledge(item: Record<string, any> | null) {
    if (!item) return null;
    return hmsCodes.value.find((code) => code.short_code === item.short_code) || null;
  }


  function hmsMessage(item: Record<string, any>) {
    const info = hmsKnowledge(item);
    if (locale.value === "zh-CN") return item.message_zh || info?.message_zh || item.message;
    return item.message_en || info?.message_en || item.message;
  }


  function hmsSuggestion(item: Record<string, any> | null) {
    if (!item) return "";
    const info = hmsKnowledge(item);
    return locale.value === "zh-CN"
      ? item.suggestion_zh || info?.suggestion_zh || ""
      : item.suggestion_en || info?.suggestion_en || "";
  }


  function eventTone(event: UnifiedEvent | Record<string, any>) {
    if (event.severity === "error" || event.severity === "fatal") return "bad";
    if (event.severity === "warning") return "warn";
    return "good";
  }


  function eventTypeLabel(item: UnifiedEvent | Record<string, any>) {
    const type = String(item.type || item.event_type || "");
    const directKey = `eventTypes.${type}`;
    const direct = t(directKey);
    if (direct !== directKey) return direct;
    if (type.startsWith("printer.command.")) {
      const command = presentationStore().record(item.data).command || type.replace("printer.command.", "");
      return `${t("events.printerCommand")} · ${presentationStore().displayCell(command)}`;
    }
    return type;
  }


  function eventMessage(item: UnifiedEvent | Record<string, any>) {
    const data = presentationStore().record(item.data);
    const type = String(item.type || item.event_type || "");
    if (type.startsWith("hms.")) return hmsEventMessage(item, data);
    if (data.command || type.startsWith("printer.command.")) {
      return t("events.commandReceived", { command: presentationStore().displayCell(data.command || type.replace("printer.command.", "")) });
    }
    if (type === "print.started") return t("events.printStarted", { file: eventPrintName(data) });
    if (type === "print.paused") return t("events.printPaused", { file: eventPrintName(data) });
    if (type === "print.resumed") return t("events.printResumed", { file: eventPrintName(data) });
    if (type === "print.finished") return t("events.printFinished", { file: eventPrintName(data) });
    if (type === "print.failed") return t("events.printFailed", { file: eventPrintName(data) });
    if (type === "print.cancelled") return t("events.printCancelled", { file: eventPrintName(data) });
    if (type === "printer.connection.restored") return t("events.connectionRestored");
    if (type === "printer.connection.disconnected") return t("events.connectionDisconnected", { reason: presentationStore().displayCell(data.error) });
    if (type === "ams.unit.updated") return t("events.amsUnitUpdated", { ams: presentationStore().displayCell(data.ams_id), type: presentationStore().displayCell(data.ams_type_name || data.module_type) });
    if (type === "ams.slot.updated") {
      return t("events.amsSlotUpdated", {
        slot: eventAmsSlotLabel(data),
        state: eventAmsSlotStateLabel(data.state),
        material: presentationStore().displayCell(data.material),
        remain: data.remain === null || data.remain === undefined ? "—" : `${data.remain}%`,
      });
    }
    if (type === "filament.spool.pending_confirmation") return t("events.filamentSkuReviewPending", { spool: presentationStore().displayCell(data.filament_spool_id), slot: eventAmsSlotLabel(data) });
    if (type === "spool.discovered") return t("events.spoolDiscovered", { spool: presentationStore().displayCell(data.filament_spool_id), slot: eventAmsSlotLabel(data) });
    if (type === "spool.unidentified") return t("events.spoolUnidentified", { slot: eventAmsSlotLabel(data) });
    if (type === "slot.identity_fallback") return t("events.slotIdentityFallback", { slot: eventAmsSlotLabel(data) });
    if (type === "spool.location_changed") return t("events.spoolLocationUpdated");
    if (type === "loaded_to_ams") return t("events.inventoryLoadedToAms", { spool: presentationStore().displayCell(item.spool_id), slot: eventAmsSlotLabel(data) });
    if (type === "unloaded_from_ams") return t("events.inventoryUnloadedFromAms", { spool: presentationStore().displayCell(item.spool_id), slot: eventAmsSlotLabel(data) });
    if (type === "opened_from_stock") return t("events.inventoryOpenedFromStock", { spool: presentationStore().displayCell(item.spool_id) });
    if (type === "sealed_stock_adjusted") return t("events.inventorySealedAdjusted");
    if (type === "location_updated") return t("events.inventoryLocationUpdated", { spool: presentationStore().displayCell(item.spool_id) });
    if (type === "weight_updated") return t("events.inventoryWeightUpdated", { spool: presentationStore().displayCell(item.spool_id) });
    if (type === "needs_location") return t("events.inventoryNeedsLocation", { spool: presentationStore().displayCell(item.spool_id) });
    if (type === "sku_confirmed") return t("events.inventorySkuConfirmed", { spool: presentationStore().displayCell(item.spool_id) });
    if (type === "storage.scan" || type === "storage.scan.finished") return t("events.storageScanFinished");
    if (type === "storage.scan_failed" || type === "storage.scan.failed") return t("events.storageScanFailed", { reason: presentationStore().displayCell(data.error || item.message) });
    return String(item.message || "");
  }


  function hmsEventMessage(item: UnifiedEvent | Record<string, any>, data: Record<string, any>) {
    const shortCode = presentationStore().displayCell(data.short_code || data.code);
    const detail = locale.value === "zh-CN" ? data.message_zh || data.message : data.message_en || data.message;
    const active = item.active === false || String(item.type || item.event_type || "") === "hms.recovered" ? t("common.resolved") : t("common.unresolved");
    return t("events.hmsSemantic", { code: shortCode, state: active, detail: presentationStore().displayCell(detail) });
  }


  function eventPrintName(data: Record<string, any>): string {
    return presentationStore().displayCell(data.gcode_file || data.task_id || data.subtask_name);
  }


  function eventAmsSlotLabel(data: Record<string, any>): string {
    const ams = presentationStore().displayCell(data.ams_id);
    const tray = numeric(data.tray_id);
    const slot = tray === null ? presentationStore().displayCell(data.tray_id) : `${Math.round(tray) + 1}`;
    return `AMS ${ams} / ${t("table.tray")} ${slot}`;
  }


  function eventAmsSlotStateLabel(value: unknown): string {
    const key = String(value ?? "").trim().toLowerCase();
    if (!key) return "—";
    const mapped = t(`amsSlotStates.${key}`);
    if (mapped !== `amsSlotStates.${key}`) return mapped;
    return presentationStore().displayCell(value);
  }


  function eventCurrentLabel(item: UnifiedEvent | Record<string, any>): string {
    if (item.active === null || item.active === undefined) return "--";
    return item.active ? t("common.unresolved") : t("common.resolved");
  }


  function openEventDetails(item: UnifiedEvent) {
    selectedEvent.value = item;
  }


  function eventRawMessage(item: UnifiedEvent | Record<string, any> | null | undefined): string {
    if (!item) return "—";
    return String(item.message || "—");
  }


  function prettyJson(value: unknown): string {
    if (value === null || value === undefined || value === "") return "—";
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }


  return {
    events,
    eventFilters,
    hmsCodes,
    selectedHmsStats,
    selectedHms,
    selectedEvent,
    eventSeverityOptions,
    eventActiveOptions,
    filteredEvents,
    loadEvents,
    openHmsDetails,
    hmsKnowledge,
    hmsMessage,
    hmsSuggestion,
    eventTone,
    eventTypeLabel,
    eventMessage,
    hmsEventMessage,
    eventPrintName,
    eventAmsSlotLabel,
    eventAmsSlotStateLabel,
    eventCurrentLabel,
    openEventDetails,
    eventRawMessage,
    prettyJson,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useEventsStore, import.meta.hot));
}
