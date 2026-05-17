import { computed, ref } from "vue";
import { acceptHMRUpdate, defineStore, storeToRefs } from "pinia";
import { API_BASE, apiRequest, formatCell, numeric } from "../api";
import { filamentColor } from "../app/filamentMetrics";
import type { Dashboard, DashboardSummaryItem, DeviceCapabilities, FilamentColorMapping, PrinterCameraCapabilities } from "../types";
import { useAmsStore } from "./ams";
import { useEventsStore } from "./events";
import { useI18nStore } from "./i18n";
import { useInventoryStore } from "./inventory";
import { usePreferencesStore } from "./preferences";
import { usePresentationStore } from "./presentation";
import { usePrintersStore } from "./printers";
import { useUiStore } from "./ui";

export const useDashboardStore = defineStore("dashboard", () => {
  const i18nStore = useI18nStore();
  const uiStore = useUiStore();
  const { locale } = storeToRefs(i18nStore);
  const { error, message } = storeToRefs(uiStore);
  const { t } = i18nStore;
  const { withLoading } = uiStore;
  const preferencesStore = () => usePreferencesStore();
  const printersStore = () => usePrintersStore();
  const amsStore = () => useAmsStore();
  const eventsStore = () => useEventsStore();
  const inventoryStore = () => useInventoryStore();
  const presentationStore = () => usePresentationStore();

  const dashboardSummary = ref<DashboardSummaryItem[]>([]);

  const dashboard = ref<Dashboard | null>(null);

  const deviceCapabilities = ref<DeviceCapabilities | null>(null);

  const cameraCapabilities = ref<PrinterCameraCapabilities | null>(null);

  const cameraStreamError = ref(false);

  const cameraStreamToken = ref(Date.now());

  const cameraLightboxOpen = ref(false);

  const snapshot = computed(() => dashboard.value?.device_snapshot || {});

  const state = computed(() => dashboard.value?.state || amsStore().stateSnapshot || {});

  const derived = computed(() => presentationStore().record(snapshot.value.derived_status));

  const temperatures = computed(() => presentationStore().record(snapshot.value.temperatures));

  const fans = computed(() => presentationStore().record(snapshot.value.fans));

  const network = computed(() => presentationStore().record(snapshot.value.network));

  const hardware = computed(() => presentationStore().record(snapshot.value.hardware));

  const fanRows = computed(() => dashboardFanRows(fans.value, hardware.value));

  const readableNetworkHardware = computed(() => networkHardwareRows(network.value, hardware.value));

  const camera = computed(() => presentationStore().record(snapshot.value.camera));

  const cameraOptions = computed(() => presentationStore().record(snapshot.value.camera_options));

  const capabilityVisibleFields = computed(() => new Set(deviceCapabilities.value?.visible_fields || []));

  const shouldShowDashboardCamera = computed(() => cameraStatusRows.value.length > 0 || capabilityVisibleFields.value.has("camera"));

  const shouldShowDashboardLiveCamera = computed(() => Boolean(printersStore().selectedPrinterId && (cameraCapabilities.value?.available || shouldShowDashboardCamera.value)));

  const cameraStreamSrc = computed(() => {
    if (!printersStore().selectedPrinterId || !cameraCapabilities.value?.available) return "";
    return `${API_BASE}/printers/${printersStore().selectedPrinterId}/camera/mjpeg?t=${cameraStreamToken.value}`;
  });

  const cameraLivePlaceholder = computed(() => {
    if (cameraStreamError.value) return t("dashboard.cameraStreamError");
    if (cameraCapabilities.value?.available) return t("dashboard.cameraStreamConnecting");
    const detail = String(cameraCapabilities.value?.detail || "");
    if (detail.includes("322")) return t("dashboard.cameraStreamLanLiveviewRequired");
    return t("dashboard.cameraStreamUnavailable");
  });

  const shouldShowChamberTemperature = computed(() => capabilityVisibleFields.value.has("chamber_temperature") || temperatures.value.chamber !== undefined);

  const readableCamera = computed(() => cameraRows(camera.value, cameraOptions.value));

  const detectionRows = computed(() => {
    const keys = new Set([
      "spaghetti_detector",
      "pileup_detector",
      "nozzle_clumping_detector",
      "airprint_detector",
      "first_layer_inspector",
      "printing_monitor",
      "buildplate_marker_detector",
      "allow_skip_parts",
    ]);
    return presentationStore().entries(cameraOptions.value).filter(([key]) => keys.has(key));
  });

  const cameraStatusRows = computed(() => {
    const optionKeys = new Set(["ipcam_record", "timelapse", "xcam_status", "raw_cfg"]);
    const optionRows = presentationStore().entries(cameraOptions.value).filter(([key]) => optionKeys.has(key));
    return [...readableCamera.value, ...optionRows];
  });

  const amsStatus = computed(() => presentationStore().record(snapshot.value.ams_status));

  const coverage = computed(() => presentationStore().record(snapshot.value.data_coverage));

  const coverageStatusRows = computed(() => presentationStore().entries(coverage.value).map(([key, item]) => ({
    key,
    received: presentationStore().record(item).received === true,
  })));

  const hmsErrors = computed(() => presentationStore().arrayOfRecord(snapshot.value.hms_errors));

  const dashboardHmsRows = computed(() => {
    const unresolved = hmsErrors.value.filter((item) => item.active !== false && item.actionable !== false);
    const resolvedOrMuted = hmsErrors.value.filter((item) => item.active === false || item.actionable === false).slice(0, 3);
    return [...unresolved, ...resolvedOrMuted];
  });

  const recentEvents = computed(() => dashboard.value?.recent_events || eventsStore().events);

  const activeDerivedStatuses = computed(() => {
    const rows = presentationStore().entries(derived.value).filter(([key, value]) => {
      if (typeof value !== "boolean") return false;
      if (!value) return false;
      if (!dashboardHasActiveTask() && ["printing", "preparing", "actual_printing", "paused"].includes(key)) return false;
      if (key === "printing" && (derived.value.preparing === true || derived.value.actual_printing === true)) return false;
      return !["current_plate_id"].includes(key);
    });
    return rows.slice(0, 4);
  });

  const layerFraction = computed(() => {
    if (!dashboardHasActiveTask()) return "";
    const printStatus = presentationStore().record(snapshot.value.print_status);
    const current = numeric(printStatus.layer_num ?? state.value.layer_num);
    const total = numeric(printStatus.total_layer_num ?? state.value.total_layer_num);
    if (current === null || total === null || total <= 0) return "";
    return `${Math.round(current)} / ${Math.round(total)}`;
  });

  const remainingTimeLabel = computed(() => {
    if (!dashboardHasActiveTask()) return "";
    return presentationStore().formatDurationMinutes(presentationStore().record(snapshot.value.print_status).mc_remaining_time ?? state.value.mc_remaining_time);
  });

  const rawOverviewItems = computed<DashboardSummaryItem[]>(() => {
    if (dashboardSummary.value.length) return dashboardSummary.value;
    return printersStore().printers.map((printer) => ({ printer, state: null, device_snapshot: null }));
  });

  const overviewItems = computed<DashboardSummaryItem[]>(() => {
    const query = String(preferencesStore().overviewControls.search || "").trim().toLowerCase();
    const filtered = rawOverviewItems.value.filter((item) => {
      const haystack = [
        item.printer.name,
        item.printer.host,
        summaryStatusLabel(item),
        presentationStore().record(summarySnapshot(item).hardware).model,
        presentationStore().record(summarySnapshot(item).firmware).hardware_version,
      ].join(" ").toLowerCase();
      if (query && !haystack.includes(query)) return false;
      if (preferencesStore().overviewControls.filter === "online") return item.printer.connection_status === "connected";
      if (preferencesStore().overviewControls.filter === "offline") return item.printer.connection_status !== "connected";
      if (preferencesStore().overviewControls.filter === "printing") return summaryDerived(item).printing === true || summaryDerived(item).actual_printing === true;
      if (preferencesStore().overviewControls.filter === "attention") return summaryHasAttention(item);
      if (preferencesStore().overviewControls.filter === "hms") return summaryActiveHmsCount(item) > 0;
      return true;
    });
    return filtered.sort(compareOverviewItems);
  });

  const overviewStats = computed(() => {
    const items = rawOverviewItems.value;
    const total = items.length;
    const connected = items.filter((item) => item.printer.connection_status === "connected").length;
    const printing = items.filter((item) => summaryDerived(item).printing === true).length;
    const attention = items.filter((item) => summaryHasAttention(item)).length;
    return [
      { label: t("overview.totalPrinters"), value: total, foot: t("overview.totalPrintersFoot") },
      { label: t("overview.connected"), value: connected, foot: t("overview.connectedFoot", { total }) },
      { label: t("overview.printing"), value: printing, foot: t("overview.printingFoot") },
      { label: t("overview.needsAttention"), value: attention, foot: t("overview.needsAttentionFoot") },
    ];
  });

  const dashboardAmsSummaryRows = computed(() => {
    const units = dashboard.value?.ams_units || [];
    const slots = dashboard.value?.ams_slots || [];
    const statusLabel = dashboardAmsStatusLabel(amsStatus.value);
    return [
      [t("ams.amsCount"), units.length],
      [t("ams.slotCount"), slots.length],
      [t("ams.loadedCount"), slots.filter((slot) => isDashboardAmsLoaded(slot)).length],
      [t("ams.emptyCount"), slots.filter((slot) => dashboardAmsSlotState(slot) === "empty").length],
      [t("ams.transitioningCount"), slots.filter((slot) => isDashboardAmsTransitioning(slot)).length],
      [t("dashboard.amsStatus"), statusLabel],
    ] as [string, unknown][];
  });

  const dashboardAmsUnitRows = computed(() => {
    const units = dashboard.value?.ams_units || [];
    const slots = dashboard.value?.ams_slots || [];
    const activeSlot = dashboardActiveAmsSlot(slots, amsStatus.value);
    const knownUnitIds = new Set(units.map((unit) => String(unit.ams_id)));
    const rows = units.map((unit, index) => dashboardAmsUnitVisual(unit, slots, index, activeSlot));
    const orphanIds = Array.from(new Set(slots.map((slot) => String(slot.ams_id)).filter((amsId) => !knownUnitIds.has(amsId))));
    orphanIds.forEach((amsId) => {
      rows.push(dashboardAmsUnitVisual({ ams_id: amsId, ams_type_name: "AMS" }, slots, rows.length, activeSlot));
    });
    return rows;
  });

  const canRequestFullRefresh = computed(() => printersStore().selectedPrinter?.connection_status === "connected");


  async function requestRefreshFull() {
    if (!printersStore().selectedPrinterId) return;
    if (!canRequestFullRefresh.value) {
      await withLoading(loadDashboard);
      error.value = t("error.fullRefreshNotConnected");
      return;
    }
    await withLoading(async () => {
      const previousMarker = dashboardRefreshMarker(dashboard.value);
      await apiRequest<Record<string, string>>(`/printers/${printersStore().selectedPrinterId}/refresh-full`, { method: "POST" });
      const refreshed = await waitForDashboardRefresh(previousMarker);
      if (!refreshed) await loadDashboard();
      message.value = t("message.fullRefreshRequested");
    });
  }


  async function fetchDashboard() {
    if (!printersStore().selectedPrinterId) return null;
    return apiRequest<Dashboard>(`/printers/${printersStore().selectedPrinterId}/dashboard`);
  }


  async function loadDashboard() {
    if (!printersStore().selectedPrinterId) return;
    const [result, capabilities, cameraCapabilityResult, colorMappingResult] = await Promise.all([
      fetchDashboard(),
      apiRequest<DeviceCapabilities>(`/printers/${printersStore().selectedPrinterId}/capabilities`),
      apiRequest<PrinterCameraCapabilities>(`/printers/${printersStore().selectedPrinterId}/camera/capabilities`).catch((error) => ({
        available: false,
        detail: error instanceof Error ? error.message : String(error),
      })),
      apiRequest<FilamentColorMapping[]>("/filament/effective-color-mappings"),
    ]);
    if (result) dashboard.value = result;
    deviceCapabilities.value = capabilities;
    cameraCapabilities.value = cameraCapabilityResult;
    cameraStreamError.value = false;
    inventoryStore().effectiveFilamentColorMappings = colorMappingResult;
  }


  function restartCameraStream() {
    cameraStreamError.value = false;
    cameraStreamToken.value = Date.now();
  }


  function openCameraLightbox() {
    cameraLightboxOpen.value = true;
  }


  function closeCameraLightbox() {
    cameraLightboxOpen.value = false;
  }


  function handleCameraStreamError() {
    cameraStreamError.value = true;
  }


  function handleCameraStreamLoaded() {
    cameraStreamError.value = false;
  }


  async function loadOverview() {
    const summaryResult = await apiRequest<DashboardSummaryItem[]>("/dashboard/summary");
    dashboardSummary.value = summaryResult;
    if (!printersStore().selectedPrinterId && dashboardSummary.value.length) {
      printersStore().selectedPrinterId = dashboardSummary.value[0].printer.id;
    }
  }


  function summarySnapshot(item: DashboardSummaryItem): Record<string, any> {
    return presentationStore().record(item.device_snapshot);
  }


  function summaryState(item: DashboardSummaryItem): Record<string, any> {
    return presentationStore().record(item.state);
  }


  function summaryDerived(item: DashboardSummaryItem): Record<string, any> {
    return presentationStore().record(summarySnapshot(item).derived_status);
  }


  function summaryTemperatures(item: DashboardSummaryItem): Record<string, any> {
    return presentationStore().record(summarySnapshot(item).temperatures);
  }


  function summaryNetwork(item: DashboardSummaryItem): Record<string, any> {
    return presentationStore().record(summarySnapshot(item).network);
  }


  function summaryCoverage(item: DashboardSummaryItem): Record<string, any> {
    return presentationStore().record(summarySnapshot(item).data_coverage);
  }


  function summaryCoveragePercent(item: DashboardSummaryItem) {
    const rows = presentationStore().entries(summaryCoverage(item));
    if (!rows.length) return 0;
    const received = rows.filter(([, value]) => presentationStore().record(value).received === true).length;
    return Math.round((received / rows.length) * 100);
  }


  function summaryActiveHmsCount(item: DashboardSummaryItem) {
    return presentationStore().arrayOfRecord(summarySnapshot(item).hms_errors).filter((event) => event.active !== false && event.actionable !== false).length;
  }


  function summaryHasAttention(item: DashboardSummaryItem) {
    const connectionStatus = item.printer.connection_status;
    return (connectionStatus !== "connected" && connectionStatus !== "connecting")
      || Boolean(item.printer.last_error)
      || summaryDerived(item).has_error === true
      || summaryActiveHmsCount(item) > 0;
  }


  function summaryTone(item: DashboardSummaryItem) {
    if (summaryHasAttention(item)) return "bad";
    if (item.printer.connection_status === "connecting") return "warn";
    if (item.printer.connection_status === "connected") return "good";
    return "muted";
  }


  function compareOverviewItems(left: DashboardSummaryItem, right: DashboardSummaryItem) {
    if (preferencesStore().overviewControls.sort === "printing") {
      return Number(summaryDerived(right).printing === true || summaryDerived(right).actual_printing === true)
        - Number(summaryDerived(left).printing === true || summaryDerived(left).actual_printing === true)
        || left.printer.name.localeCompare(right.printer.name, locale.value);
    }
    if (preferencesStore().overviewControls.sort === "name") {
      return left.printer.name.localeCompare(right.printer.name, locale.value);
    }
    if (preferencesStore().overviewControls.sort === "last_sync") {
      return Date.parse(String(right.printer.last_sync_at || "")) - Date.parse(String(left.printer.last_sync_at || ""));
    }
    return Number(summaryHasAttention(right)) - Number(summaryHasAttention(left))
      || Number(summaryDerived(right).printing === true || summaryDerived(right).actual_printing === true)
      - Number(summaryDerived(left).printing === true || summaryDerived(left).actual_printing === true)
      || left.printer.name.localeCompare(right.printer.name, locale.value);
  }


  function summaryStatusLabel(item: DashboardSummaryItem) {
    const derivedValue = summaryDerived(item);
    const stateValue = summaryState(item);
    if (item.printer.connection_status !== "connected" && item.printer.connection_status !== "connecting") {
      return presentationStore().displayCell(item.printer.connection_status);
    }
    if (summaryHasAttention(item)) return t("overview.needsAttention");
    if (derivedValue.user_state) return presentationStore().displayCell(derivedValue.user_state);
    if (derivedValue.preparing === true) return t("values.preparing");
    if (derivedValue.actual_printing === true) return t("values.actual_printing");
    if (derivedValue.printing === true) return t("values.printing");
    if (derivedValue.paused === true) return t("values.paused");
    if (derivedValue.idle === true) return t("values.idle");
    return presentationStore().displayCell(stateValue.gcode_state || item.printer.connection_status);
  }


  function summaryTaskName(item: DashboardSummaryItem) {
    const stateValue = summaryState(item);
    return formatCell(stateValue.subtask_name || stateValue.gcode_file || t("dashboard.noActiveTask"));
  }


  function summaryProgress(item: DashboardSummaryItem) {
    return Math.round(presentationStore().percent(summaryState(item).mc_percent));
  }


  function summaryLayerFraction(item: DashboardSummaryItem) {
    const printStatus = presentationStore().record(summarySnapshot(item).print_status);
    const current = printStatus.layer_num ?? summaryState(item).layer_current ?? summaryState(item).layer_num;
    const total = printStatus.total_layer_num ?? summaryState(item).layer_total ?? summaryState(item).total_layer_num;
    if (current === undefined && total === undefined) return "--";
    return `${presentationStore().softCell(current)} / ${presentationStore().softCell(total)}`;
  }


  function summaryStage(item: DashboardSummaryItem) {
    const printStatus = presentationStore().record(summarySnapshot(item).print_status);
    return presentationStore().displayCell(printStatus.stg_cur_name || printStatus.sub_stage_name || printStatus.stage_name || summaryState(item).gcode_state || item.printer.connection_status);
  }


  function summaryTemperature(item: DashboardSummaryItem, key: string) {
    return formatCell(summaryTemperatures(item)[key]);
  }


  function summaryWifi(item: DashboardSummaryItem) {
    return formatCell(summaryNetwork(item).wifi_signal);
  }


  function fanDisplayPercent(item: unknown): number | null {
    const value = presentationStore().record(item);
    const parsed = numeric(value.percent);
    if (parsed === null) return null;
    return Math.max(0, Math.min(100, Math.round(parsed)));
  }


  function dashboardFanRows(fanValue: Record<string, any>, hardwareValue: Record<string, any>) {
    const rows = presentationStore().entries(fanValue)
      .filter(([key, item]) => key !== "fan_gear" && fanDisplayPercent(item) !== null) as [string, unknown][];
    const present = new Set(rows.map(([key]) => key));
    const parts = presentationStore().arrayOfRecord(presentationStore().record(hardwareValue.airduct).parts);
    for (const part of parts) {
      const key = airductPartKey(part);
      if (!key || present.has(key)) continue;
      const mappedSpeedKey = airductPartSpeedKey(key);
      if (mappedSpeedKey && present.has(mappedSpeedKey)) continue;
      const percentValue = numeric(part.state ?? part.tar_state);
      if (percentValue === null) continue;
      rows.push([key, { percent: Math.max(0, Math.min(100, Math.round(percentValue))), raw: percentValue }]);
      present.add(key);
    }
    const fanGear = fanValue.fan_gear;
    if (!rows.length && fanDisplayPercent(fanGear) !== null) rows.push(["fan_gear", fanGear]);
    return rows.sort(([left], [right]) => dashboardFanRowSortValue(left) - dashboardFanRowSortValue(right));
  }


  function dashboardFanRowSortValue(key: string) {
    const order: Record<string, number> = {
      cooling_fan_speed: 10,
      toolhead_fan: 10,
      big_fan1_speed: 20,
      right_aux_fan: 20,
      left_aux_fan: 30,
      big_fan2_speed: 40,
      exhaust_fan: 40,
      heatbreak_fan_speed: 50,
    };
    return order[key] ?? 100;
  }


  function airductPartKey(part: Record<string, any>) {
    const name = String(part.part_name || "");
    if (name) return name;
    const id = numeric(part.id);
    if (id === 16) return "toolhead_fan";
    if (id === 32) return "right_aux_fan";
    if (id === 48) return "exhaust_fan";
    if (id === 160) return "left_aux_fan";
    return "";
  }


  function airductPartSpeedKey(partKey: string) {
    const mapping: Record<string, string> = {
      toolhead_fan: "cooling_fan_speed",
      right_aux_fan: "big_fan1_speed",
      exhaust_fan: "big_fan2_speed",
    };
    return mapping[partKey] || "";
  }


  function derivedStatusTone(key: string) {
    if (key === "has_error") return "bad";
    if (key === "paused" || key === "ams_filament_change" || key === "ams_rfid_identifying") return "warn";
    return "good";
  }


  function cameraRows(value: Record<string, any>, optionValue: Record<string, any> = {}) {
    const allowed = [
      "ipcam_record",
      "timelapse",
      "xcam_status",
      "cfg",
      "resolution",
      "liveview_preview",
      "brtc_service",
      "rtsp_url",
      "cap_pic_enable",
      "ipcam_dev",
      "mode_bits",
      "bs_state",
      "agora_service",
      "tutk_server",
      "first_layer_inspector",
      "printing_monitor",
      "buildplate_marker_detector",
      "print_halt",
    ];
    return allowed
      .filter((key) => {
        if (Object.prototype.hasOwnProperty.call(optionValue, key)) return false;
        if (key === "cfg" && Object.prototype.hasOwnProperty.call(optionValue, "raw_cfg")) return false;
        const item = value[key];
        return item !== null && item !== undefined && item !== "" && typeof item !== "object";
      })
      .map((key) => [key, key === "rtsp_url" ? Boolean(value[key]) : value[key]] as [string, unknown]);
  }


  function networkHardwareRows(networkValue: Record<string, any>, hardwareValue: Record<string, any>) {
    const rows: [string, unknown][] = [];
    const networkKeys = ["wifi_signal", "wifi_signal_raw", "wired_network", "ip", "ipv4", "ssid", "hostname", "mac"];
    const hardwareKeys = [
      "nozzle_type",
      "nozzle_diameter",
      "extruder_count",
      "nozzle_count",
      "upgrade_state",
      "ext_tool",
      "laser",
      "fourth_axis",
    ];
    for (const key of networkKeys) pushPrimitiveRow(rows, key, networkValue[key]);
    for (const key of hardwareKeys) pushPrimitiveRow(rows, key, hardwareValue[key]);
    pushObjectSummary(rows, "toolhead", hardwareValue.toolhead);
    pushObjectSummary(rows, "bed", hardwareValue.bed);
    pushObjectSummary(rows, "plate", hardwareValue.plate);
    pushObjectSummary(rows, "airduct", hardwareValue.airduct);
    pushObjectSummary(rows, "ctc", hardwareValue.ctc);
    pushObjectSummary(rows, "cam", hardwareValue.cam);
    pushObjectSummary(rows, "device_nozzle", hardwareValue.device_nozzle);
    return rows;
  }


  function pushPrimitiveRow(rows: [string, unknown][], key: string, value: unknown) {
    if (value === null || value === undefined || value === "" || typeof value === "object") return;
    rows.push([key, value]);
  }


  function pushObjectSummary(rows: [string, unknown][], key: string, value: unknown) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return;
    const source = value as Record<string, unknown>;
    if (key === "airduct") {
      const mode = source.modeCur_name || source.modeFunc_name || source.subMode_name || source.modeCur || source.modeFunc || source.subMode;
      pushPrimitiveRow(rows, "airduct_mode", mode);
      return;
    }
    if (key === "plate") {
      const plate = source.cur_id_name || source.name || source.id || source.cur_id || source.type;
      pushPrimitiveRow(rows, "plate", displayPlateName(plate));
      return;
    }
    const summaryKeys = [
      "state",
      "status",
      "type",
      "id",
      "name",
      "sn",
      "serial_number",
      "diameter",
      "current_nozzle_id",
      "target_nozzle_id",
      "cur_id",
      "cur_id_name",
      "modeCur_name",
      "modeFunc_name",
      "subMode_name",
    ];
    const parts = summaryKeys
      .filter((item) => source[item] !== null && source[item] !== undefined && source[item] !== "" && typeof source[item] !== "object")
      .map((item) => `${presentationStore().fieldLabel(item)}: ${presentationStore().displayCell(source[item])}`);
    if (parts.length) rows.push([key, parts.join(" · ")]);
  }


  function displayPlateName(value: unknown) {
    const text = String(value ?? "").trim();
    if (!text) return "";
    if (/cool\s*\(?super\s*tack\)?/i.test(text) || text === "P0301") return t("values.cool_supertack_plate");
    return presentationStore().displayCell(value);
  }


  function dashboardActiveAmsSlot(slots: Record<string, any>[], status: Record<string, any>) {
    const marked = slots.find((slot) => slot.is_active);
    if (marked) return marked;
    const activeGlobalTray = firstSetBit(status.tray_hall_out_bits);
    if (activeGlobalTray !== null) {
      const activeByBit = slots.find((slot) => numeric(slot.global_tray_id) === activeGlobalTray);
      if (activeByBit) return activeByBit;
    }
    const trayNow = numeric(status.tray_now);
    if (trayNow === null || trayNow < 0 || trayNow >= 255) return undefined;
    return slots.find((slot) => {
      const globalTray = numeric(slot.global_tray_id);
      const tray = numeric(slot.tray_id);
      return globalTray === trayNow || tray === trayNow;
    });
  }


  function firstSetBit(value: unknown): number | null {
    const mask = bitmaskNumber(value);
    if (mask === null || mask <= 0) return null;
    let bit = 0;
    let cursor = mask;
    while ((cursor & 1) === 0) {
      bit += 1;
      cursor = Math.floor(cursor / 2);
    }
    return bit;
  }


  function bitmaskNumber(value: unknown): number | null {
    if (value === null || value === undefined || value === "") return null;
    if (typeof value === "number") return Number.isFinite(value) ? value : null;
    const parsed = Number.parseInt(String(value).trim(), 16);
    return Number.isFinite(parsed) ? parsed : null;
  }


  function dashboardAmsActiveSlotLabel(slot: Record<string, any> | null | undefined, status: Record<string, any>) {
    if (slot) return amsStore().activeSlotDisplayLabel(slot);
    const trayNow = numeric(status.tray_now);
    if (trayNow !== null && trayNow >= 0 && trayNow < 255) return `${t("table.tray")} ${Math.round(trayNow) + 1}`;
    return "--";
  }


  function dashboardActiveMaterialLabel(slot: Record<string, any> | null | undefined) {
    if (!slot) return "--";
    const parts = [slot.material || slot.tray_type, slot.series || slot.tray_sub_brands, inventoryStore().slotColorLabel(slot)].filter(Boolean).map(String);
    const remain = numeric(slot.remain);
    if (remain !== null && remain >= 0) parts.push(`${Math.round(remain)}%`);
    return parts.length ? parts.join(" · ") : "--";
  }


  function dashboardAmsStatusLabel(status: Record<string, any>) {
    const main = status.ams_status_main_name ?? status.ams_status_main;
    const sub = status.ams_status_sub_name ?? status.ams_status_sub;
    const labels = [main, sub]
      .filter((item) => item !== null && item !== undefined && item !== "")
      .map((item) => presentationStore().displayCell(item));
    return labels.length ? labels.join(" · ") : "--";
  }


  function dashboardAmsSlotState(slot: Record<string, any>) {
    return String(slot.state_name || slot.tray_state_name || slot.slot_state || "").toLowerCase();
  }


  function isDashboardAmsLoaded(slot: Record<string, any>) {
    const stateText = dashboardAmsSlotState(slot);
    return stateText === "loaded" || stateText.includes("loaded") || Boolean(slot.material || slot.tray_type);
  }


  function isDashboardAmsTransitioning(slot: Record<string, any>) {
    const stateText = dashboardAmsSlotState(slot);
    return slot.is_transitioning === true || ["transitioning", "loading", "unloading"].some((item) => stateText.includes(item));
  }


  function dashboardAmsUnitVisual(
    unit: Record<string, any>,
    slots: Record<string, any>[],
    index: number,
    activeSlot?: Record<string, any> | null,
  ) {
    const unitSlots = slots
      .filter((slot) => String(slot.ams_id) === String(unit.ams_id))
      .sort((left, right) => dashboardAmsSlotSortValue(left) - dashboardAmsSlotSortValue(right));
    return {
      key: String(unit.ams_id),
      title: amsStore().amsTitle(unit),
      code: `#${unit.ams_id}`,
      meta: dashboardAmsUnitMeta(unit),
      slots: unitSlots.map((slot, slotIndex) => ({
        key: amsStore().slotKey(slot),
        label: dashboardAmsSlotShortLabel(slot, unit, index, slotIndex),
        material: dashboardAmsSlotMaterial(slot),
        remain: dashboardAmsSlotRemain(slot),
        active: slot.is_active === true || isSameDashboardAmsSlot(slot, activeSlot),
        loaded: isDashboardAmsLoaded(slot),
        style: { "--filament-color": filamentColor(slot.color || slot.tray_color) },
      })),
    };
  }


  function isSameDashboardAmsSlot(slot: Record<string, any>, activeSlot?: Record<string, any> | null) {
    if (!activeSlot || !Object.keys(activeSlot).length) return false;
    if (slot.id !== undefined && activeSlot.id !== undefined && String(slot.id) === String(activeSlot.id)) return true;
    if (String(slot.ams_id) !== String(activeSlot.ams_id)) return false;
    const slotGlobalTray = numeric(slot.global_tray_id);
    const activeGlobalTray = numeric(activeSlot.global_tray_id);
    if (slotGlobalTray !== null && activeGlobalTray !== null) return slotGlobalTray === activeGlobalTray;
    return String(slot.tray_id) === String(activeSlot.tray_id);
  }


  function dashboardAmsSlotSortValue(slot: Record<string, any>) {
    const userTray = numeric(slot.user_tray_id);
    if (userTray !== null) return userTray;
    const tray = numeric(slot.tray_id);
    if (tray !== null) return tray + 1;
    return 999;
  }


  function dashboardAmsSlotShortLabel(slot: Record<string, any>, unit: Record<string, any>, unitIndex: number, slotIndex: number) {
    const type = String(unit.ams_type_name || "");
    if (type === "AMS HT" || String(unit.ams_id) === "128") return "HT-A";
    const letter = String.fromCharCode(65 + Math.max(0, Math.min(25, unitIndex)));
    const tray = numeric(slot.user_tray_id) ?? ((numeric(slot.tray_id) ?? slotIndex) + 1);
    return `${letter}${Math.round(tray)}`;
  }


  function dashboardAmsSlotMaterial(slot: Record<string, any>) {
    return presentationStore().softCell(slot.material || slot.tray_type);
  }


  function dashboardAmsSlotRemain(slot: Record<string, any>) {
    const remain = numeric(slot.remain);
    if (remain === null || remain < 0) return "--";
    return `${Math.round(remain)}%`;
  }


  function dashboardAmsUnitMeta(unit: Record<string, any>) {
    const parts = [
      unit.ams_type_name && unit.display_name ? unit.ams_type_name : "",
      dashboardAmsEnvironmentLabel(unit),
      unit.dry_status_name || unit.dry_status ? `${t("ams.dryStatus")} ${presentationStore().displayCell(unit.dry_status_name || unit.dry_status)}` : "",
    ].filter(Boolean).map(String);
    return parts.length ? parts.join(" · ") : "--";
  }


  function dashboardAmsEnvironmentLabel(unit: Record<string, any>) {
    const parts = [];
    const temperature = numeric(unit.temperature);
    const humidity = amsStore().amsHumidity(unit);
    if (temperature !== null) parts.push(`${Math.round(temperature)}°C`);
    if (humidity !== null && humidity !== undefined && humidity !== "") parts.push(`${presentationStore().softCell(humidity)}%`);
    return parts.join(" / ");
  }


  function dashboardTaskTitle() {
    const terminalLog = dashboardTerminalLog();
    if (terminalLog) return formatCell(terminalLog.print_name || terminalLog.gcode_file || t("dashboard.noActiveTask"));
    if (!dashboardHasActiveTask()) return t("dashboard.noActiveTask");
    const printStatus = presentationStore().record(snapshot.value.print_status);
    return formatCell(state.value.subtask_name || printStatus.subtask_name || state.value.gcode_file || printStatus.gcode_file || t("dashboard.noActiveTask"));
  }


  function dashboardProgress() {
    const terminalLog = dashboardTerminalLog();
    const userState = dashboardUserStateValue();
    if (terminalLog?.status === "succeeded" || userState === "finished") return 100;
    if (!dashboardHasActiveTask()) return 0;
    const printStatus = presentationStore().record(snapshot.value.print_status);
    return Math.round(presentationStore().percent(printStatus.mc_percent ?? state.value.mc_percent));
  }


  function dashboardPrintStateLabel() {
    const terminalLog = dashboardTerminalLog();
    if (terminalLog?.status === "succeeded") return t("values.finished");
    if (terminalLog?.status === "failed") return t("values.failed_or_cancelled");
    if (terminalLog?.status === "cancelled") return t("values.cancelled");
    return presentationStore().displayCell(dashboardUserStateValue());
  }


  function dashboardPrintStageLabel() {
    if (!dashboardHasActiveTask()) return dashboardPrintStateLabel();
    const printStatus = presentationStore().record(snapshot.value.print_status);
    return presentationStore().displayCell(printStatus.stg_cur_name || printStatus.sub_stage_name || printStatus.stage_name);
  }


  function dashboardRemainingTimeMetric() {
    if (!dashboardHasActiveTask()) return "--";
    return remainingTimeLabel.value || formatCell(state.value.mc_remaining_time);
  }


  function dashboardUserStateValue() {
    return derived.value.user_state || presentationStore().record(snapshot.value.print_status).user_state || state.value.gcode_state;
  }


  function dashboardHasActiveTask() {
    if (dashboardTerminalLog()) return false;
    const userState = String(dashboardUserStateValue() || "").toUpperCase();
    if (isTerminalPrintState(userState)) return false;
    if (derived.value.preparing === true || derived.value.actual_printing === true || derived.value.paused === true) return true;
    return ["RUNNING", "PREPARE", "SLICING", "PAUSE", "PAUSED"].includes(userState);
  }


  function dashboardTerminalLog() {
    const printStatus = presentationStore().record(snapshot.value.print_status);
    const taskId = state.value.task_id || printStatus.task_id;
    const file = state.value.gcode_file || printStatus.gcode_file;
    const title = state.value.subtask_name || printStatus.subtask_name;
    const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);
    return (dashboard.value?.recent_print_logs || []).find((log) => {
      if (!terminalStatuses.has(log.status)) return false;
      if (taskId && log.task_id === taskId) return true;
      if (!taskId && file && log.gcode_file === file) return true;
      if (!taskId && title && log.print_name === title) return true;
      return false;
    }) || null;
  }


  function isTerminalPrintState(value: string) {
    return ["FINISH", "FAILED", "IDLE", "FINISHED", "FAILED_OR_CANCELLED"].includes(value);
  }


  function dashboardRefreshMarker(value: Dashboard | null) {
    const deviceSnapshot = presentationStore().record(value?.device_snapshot);
    const rawRefs = presentationStore().record(deviceSnapshot.raw_refs);
    return String(rawRefs.push_status_raw_id || rawRefs.push_status_received_at || deviceSnapshot.updated_at || presentationStore().record(value?.state).updated_at || "");
  }


  async function waitForDashboardRefresh(previousMarker: string) {
    for (let attempt = 0; attempt < 12; attempt += 1) {
      await presentationStore().delay(700);
      const next = await fetchDashboard();
      if (!next) return false;
      dashboard.value = next;
      if (dashboardRefreshMarker(next) && dashboardRefreshMarker(next) !== previousMarker) return true;
    }
    return false;
  }


  return {
    dashboardSummary,
    dashboard,
    deviceCapabilities,
    cameraCapabilities,
    cameraStreamError,
    cameraStreamToken,
    cameraLightboxOpen,
    snapshot,
    state,
    derived,
    temperatures,
    fans,
    network,
    hardware,
    fanRows,
    readableNetworkHardware,
    camera,
    cameraOptions,
    capabilityVisibleFields,
    shouldShowDashboardCamera,
    shouldShowDashboardLiveCamera,
    cameraStreamSrc,
    cameraLivePlaceholder,
    shouldShowChamberTemperature,
    readableCamera,
    detectionRows,
    cameraStatusRows,
    amsStatus,
    coverage,
    coverageStatusRows,
    hmsErrors,
    dashboardHmsRows,
    recentEvents,
    activeDerivedStatuses,
    layerFraction,
    remainingTimeLabel,
    rawOverviewItems,
    overviewItems,
    overviewStats,
    dashboardAmsSummaryRows,
    dashboardAmsUnitRows,
    canRequestFullRefresh,
    requestRefreshFull,
    fetchDashboard,
    loadDashboard,
    restartCameraStream,
    openCameraLightbox,
    closeCameraLightbox,
    handleCameraStreamError,
    handleCameraStreamLoaded,
    loadOverview,
    summarySnapshot,
    summaryState,
    summaryDerived,
    summaryTemperatures,
    summaryNetwork,
    summaryCoverage,
    summaryCoveragePercent,
    summaryActiveHmsCount,
    summaryHasAttention,
    summaryTone,
    compareOverviewItems,
    summaryStatusLabel,
    summaryTaskName,
    summaryProgress,
    summaryLayerFraction,
    summaryStage,
    summaryTemperature,
    summaryWifi,
    fanDisplayPercent,
    dashboardFanRows,
    dashboardFanRowSortValue,
    airductPartKey,
    airductPartSpeedKey,
    derivedStatusTone,
    cameraRows,
    networkHardwareRows,
    pushPrimitiveRow,
    pushObjectSummary,
    displayPlateName,
    dashboardActiveAmsSlot,
    firstSetBit,
    bitmaskNumber,
    dashboardAmsActiveSlotLabel,
    dashboardActiveMaterialLabel,
    dashboardAmsStatusLabel,
    dashboardAmsSlotState,
    isDashboardAmsLoaded,
    isDashboardAmsTransitioning,
    dashboardAmsUnitVisual,
    isSameDashboardAmsSlot,
    dashboardAmsSlotSortValue,
    dashboardAmsSlotShortLabel,
    dashboardAmsSlotMaterial,
    dashboardAmsSlotRemain,
    dashboardAmsUnitMeta,
    dashboardAmsEnvironmentLabel,
    dashboardTaskTitle,
    dashboardProgress,
    dashboardPrintStateLabel,
    dashboardPrintStageLabel,
    dashboardRemainingTimeMetric,
    dashboardUserStateValue,
    dashboardHasActiveTask,
    dashboardTerminalLog,
    isTerminalPrintState,
    dashboardRefreshMarker,
    waitForDashboardRefresh,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useDashboardStore, import.meta.hot));
}
