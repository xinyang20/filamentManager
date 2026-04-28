<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import {
  Activity,
  Archive,
  Bell,
  Boxes,
  Camera,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  ClipboardList,
  Database,
  Download,
  Eye,
  EyeOff,
  FileDown,
  Gauge,
  HardDrive,
  LineChart,
  Loader2,
  Network,
  PencilLine,
  PlugZap,
  RefreshCw,
  Save,
  Search,
  Send,
  Settings,
  ShieldAlert,
  Star,
  Thermometer,
  Trash2,
  Unplug,
  Wrench,
  X,
} from "lucide-vue-next";
import { API_BASE, apiRequest, formatCell, formatUnit, numeric } from "./api";
import AppSelect from "./components/AppSelect.vue";
import MetricChart from "./components/MetricChart.vue";
import translations from "./i18n.json";
import type {
  AmsOverview,
  AmsSensorHistory,
  AmsSlotHistorySample,
  Dashboard,
  DashboardSummaryItem,
  DeviceCapabilities,
  DiscoveryCandidate,
  HmsCodeInfo,
  HmsCodeStats,
  MaintenanceOverview,
  MetricSample,
  NotificationDelivery,
  NotificationRule,
  NotificationTarget,
  Printer,
  PrinterMaintenance,
  PrintLogAnalytics,
  PrintLogEntry,
  PrintLogList,
  PrintLogSummary,
  Spool,
  StorageFile,
  StorageSummary,
  SystemInfo,
  TimelapseNote,
  UnifiedEvent,
} from "./types";

const viewKeys = ["overview", "dashboard", "events", "metrics", "printLog", "storage", "ams", "inventory", "maintenance", "notifications", "printers", "debug"] as const;
type ViewKey = (typeof viewKeys)[number];
type Locale = keyof typeof translations;
type NavGroupKey = "monitoring" | "assets" | "system";

const storedView = window.localStorage.getItem("filamentManager.activeView") as ViewKey | null;

const navItems = [
  { key: "overview", labelKey: "nav.overview", icon: Activity, group: "monitoring" },
  { key: "dashboard", labelKey: "nav.dashboard", icon: Gauge, group: "monitoring" },
  { key: "events", labelKey: "nav.events", icon: Bell, group: "monitoring" },
  { key: "metrics", labelKey: "nav.metrics", icon: LineChart, group: "monitoring" },
  { key: "printLog", labelKey: "nav.printLog", icon: ClipboardList, group: "monitoring" },
  { key: "maintenance", labelKey: "nav.maintenance", icon: Wrench, group: "monitoring" },
  { key: "ams", labelKey: "nav.ams", icon: Boxes, group: "assets" },
  { key: "inventory", labelKey: "nav.inventory", icon: Archive, group: "assets" },
  { key: "storage", labelKey: "nav.storage", icon: HardDrive, group: "assets" },
  { key: "notifications", labelKey: "nav.notifications", icon: Bell, group: "system" },
  { key: "printers", labelKey: "nav.printers", icon: Settings, group: "system" },
  { key: "debug", labelKey: "nav.debug", icon: Database, group: "system" },
] as const;

const navGroups: { key: NavGroupKey; labelKey: string }[] = [
  { key: "monitoring", labelKey: "navGroup.monitoring" },
  { key: "assets", labelKey: "navGroup.assets" },
  { key: "system", labelKey: "navGroup.system" },
];
const slotChangeKinds = ["material", "remain", "rfid", "calibration"] as const;
const experimentalFeatureDefaults = {
  timelapse: false,
  maintenance: false,
  printLog: false,
  notifications: false,
};
type ExperimentalFeatureKey = keyof typeof experimentalFeatureDefaults;
const experimentalFeatureViews: Partial<Record<ViewKey, ExperimentalFeatureKey>> = {
  storage: "timelapse",
  maintenance: "maintenance",
  printLog: "printLog",
  notifications: "notifications",
};

const locale = ref<Locale>("zh-CN");
const experimentalFeatures = reactive<Record<ExperimentalFeatureKey, boolean>>(loadExperimentalFeatureSettings());
const activeView = ref<ViewKey>(resolveInitialView(storedView));
const printers = ref<Printer[]>([]);
const selectedPrinterId = ref<number | null>(null);
const dashboardSummary = ref<DashboardSummaryItem[]>([]);
const dashboard = ref<Dashboard | null>(null);
const deviceCapabilities = ref<DeviceCapabilities | null>(null);
const metrics = ref<MetricSample[]>([]);
const metricRange = ref("6h");
const printLogs = ref<PrintLogEntry[]>([]);
const printLogSummary = ref<PrintLogSummary | null>(null);
const printLogAnalytics = ref<PrintLogAnalytics | null>(null);
const printLogTotal = ref(0);
const printLogFilters = reactive({
  printer_id: "",
  status: "",
  search: "",
  date_from: "",
  date_to: "",
  limit: 25,
  offset: 0,
});
const storageFiles = ref<StorageFile[]>([]);
const storageSummary = ref<StorageSummary | null>(null);
const storageSearch = ref("");
const storageSort = ref("modified_desc");
const storagePage = ref(1);
const storagePageSize = ref(12);
const timelapseNotes = ref<Record<string, TimelapseNote>>({});
const timelapseNoteDrafts = reactive<Record<string, string>>({});
const stateSnapshot = ref<Record<string, any> | null>(null);
const amsSlots = ref<Record<string, any>[]>([]);
const amsOverview = ref<AmsOverview | null>(null);
const amsLabelDrafts = reactive<Record<string, string>>({});
const amsLabelEditing = reactive<Record<string, boolean>>({});
const amsSensorRange = ref("24");
const amsSensorHistories = ref<Record<string, AmsSensorHistory>>({});
const spools = ref<Spool[]>([]);
const maintenanceOverview = ref<MaintenanceOverview | null>(null);
const maintenanceItems = ref<PrinterMaintenance[]>([]);
const maintenanceNotes = reactive<Record<number, string>>({});
const events = ref<UnifiedEvent[]>([]);
const eventFilters = reactive({
  type: "",
  severity: "",
  active: "",
});
const hmsCodes = ref<HmsCodeInfo[]>([]);
const selectedHmsStats = ref<HmsCodeStats | null>(null);
const selectedHms = ref<Record<string, any> | null>(null);
const selectedSlot = ref<Record<string, any> | null>(null);
const selectedSlotHistory = ref<AmsSlotHistorySample[]>([]);
const rawMqtt = ref<Record<string, any>[]>([]);
const systemInfo = ref<SystemInfo | null>(null);
const discovery = ref<DiscoveryCandidate[]>([]);
const scanning = ref(false);
const scanProgress = ref(0);
const scanPhase = ref("");
const message = ref("");
const error = ref("");
const storageResult = ref<Record<string, any> | null>(null);
const realtimeDisconnected = ref(false);
const activeLoadingCount = ref(0);
const loading = computed(() => activeLoadingCount.value > 0);
const sectionLayouts = ref<Record<string, Record<string, { hidden?: boolean; collapsed?: boolean; order?: number }>>>(loadSectionLayouts());
const transientCollapsedSections = ref<Record<string, boolean>>({});
let eventSource: EventSource | null = null;
let pollingTimer: number | null = null;
let loadingTokenSeq = 0;
const activeLoadingTokens = new Set<number>();

const printerForm = reactive({
  name: "Printer",
  host: "",
  port: 8883,
  serial: "",
  access_code: "",
  tls_enabled: true,
  certificate_verify: false,
});
const accessCodeVisible = ref(false);
const accessCodeRevealLoading = ref(false);
const overviewControls = reactive(loadOverviewControls());
const notificationTargets = ref<NotificationTarget[]>([]);
const notificationRules = ref<NotificationRule[]>([]);
const notificationDeliveries = ref<NotificationDelivery[]>([]);
const notificationTargetForm = reactive({
  id: "",
  channel: "webhook",
  name: "",
  url: "",
  token: "",
  enabled: true,
});
const notificationRuleForm = reactive({
  id: "",
  name: "",
  event_types: "",
  printer_ids: "",
  severities: "",
  quiet_start: "",
  quiet_end: "",
  repeat_suppression_minutes: 30,
  enabled: true,
});
const exportOptions = reactive({
  type: "json",
  sections: ["config", "print_logs", "ams_history", "maintenance_history", "events", "notifications"] as string[],
});

const spoolForm = reactive({
  display_name: "",
  brand: "",
  material: "",
  series: "",
  color: "",
  sealed_quantity: 1,
  status: "sealed",
});

const bindForm = reactive({
  slot_id: "",
  spool_id: "",
});

const selectedPrinter = computed(() => printers.value.find((item) => item.id === selectedPrinterId.value) || null);
const printerSelectOptions = computed(() =>
  printers.value.length
    ? printers.value.map((printer) => ({ label: `${printer.name} · ${printer.host}`, value: printer.id }))
    : [{ label: t("common.noPrinter"), value: null, disabled: true }],
);
const localeOptions = computed(() => [
  { label: "简体中文", value: "zh-CN" },
  { label: "English", value: "en-US" },
]);
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
const printLogPrinterOptions = computed(() => [
  { label: t("printLog.allPrinters"), value: "" },
  ...printers.value.map((printer) => ({ label: printer.name, value: String(printer.id) })),
]);
const printLogStatusOptions = computed(() => [
  { label: t("printLog.allStatuses"), value: "" },
  { label: t("values.running"), value: "running" },
  { label: t("values.paused"), value: "paused" },
  { label: t("values.succeeded"), value: "succeeded" },
  { label: t("values.failed"), value: "failed" },
  { label: t("values.cancelled"), value: "cancelled" },
]);
const overviewFilterOptions = computed(() => [
  { label: t("overview.filterAll"), value: "all" },
  { label: t("overview.filterOnline"), value: "online" },
  { label: t("overview.filterOffline"), value: "offline" },
  { label: t("overview.filterPrinting"), value: "printing" },
  { label: t("overview.filterAttention"), value: "attention" },
  { label: t("overview.filterHms"), value: "hms" },
]);
const overviewSortOptions = computed(() => [
  { label: t("overview.sortAttention"), value: "attention" },
  { label: t("overview.sortPrinting"), value: "printing" },
  { label: t("overview.sortName"), value: "name" },
  { label: t("overview.sortLastSync"), value: "last_sync" },
]);
const overviewDensityOptions = computed(() => [
  { label: t("overview.densityCompact"), value: "compact" },
  { label: t("overview.densityStandard"), value: "standard" },
  { label: t("overview.densityDetailed"), value: "detailed" },
]);
const notificationChannelOptions = computed(() => [
  { label: "Webhook", value: "webhook" },
  { label: "ntfy", value: "ntfy" },
]);
const exportSectionItems = computed(() => [
  { key: "config", label: t("export.sectionConfig") },
  { key: "print_logs", label: t("export.sectionPrintLogs") },
  { key: "ams_history", label: t("export.sectionAmsHistory") },
  { key: "maintenance_history", label: t("export.sectionMaintenance") },
  { key: "events", label: t("export.sectionEvents") },
  { key: "notifications", label: t("export.sectionNotifications") },
]);
const metricRangeOptions = computed(() => [
  { label: t("metrics.range1h"), value: "1h" },
  { label: t("metrics.range6h"), value: "6h" },
  { label: t("metrics.range24h"), value: "24h" },
  { label: t("metrics.range7d"), value: "7d" },
  { label: t("metrics.range30d"), value: "30d" },
]);
const storageSortOptions = computed(() => [
  { label: t("storage.sortModifiedDesc"), value: "modified_desc" },
  { label: t("storage.sortModifiedAsc"), value: "modified_asc" },
  { label: t("storage.sortSizeDesc"), value: "size_desc" },
  { label: t("storage.sortSizeAsc"), value: "size_asc" },
  { label: t("storage.sortNameAsc"), value: "name_asc" },
  { label: t("storage.sortNameDesc"), value: "name_desc" },
]);
const amsSensorRangeOptions = computed(() => [
  { label: "24h", value: "24" },
  { label: "7d", value: "168" },
]);
const spoolStatusOptions = computed(() => [
  { label: displayCell("sealed"), value: "sealed" },
  { label: displayCell("opened"), value: "opened" },
  { label: displayCell("active"), value: "active" },
  { label: displayCell("archived"), value: "archived" },
]);
const experimentalFeatureItems = computed(() => [
  {
    key: "timelapse" as const,
    label: t("debug.experimentalTimelapse"),
    description: t("debug.experimentalTimelapseHint"),
  },
  {
    key: "maintenance" as const,
    label: t("debug.experimentalMaintenance"),
    description: t("debug.experimentalMaintenanceHint"),
  },
  {
    key: "printLog" as const,
    label: t("debug.experimentalPrintLog"),
    description: t("debug.experimentalPrintLogHint"),
  },
  {
    key: "notifications" as const,
    label: t("debug.experimentalNotifications"),
    description: t("debug.experimentalNotificationsHint"),
  },
]);
const snapshot = computed(() => dashboard.value?.device_snapshot || {});
const state = computed(() => dashboard.value?.state || stateSnapshot.value || {});
const derived = computed(() => record(snapshot.value.derived_status));
const temperatures = computed(() => record(snapshot.value.temperatures));
const fans = computed(() => record(snapshot.value.fans));
const network = computed(() => record(snapshot.value.network));
const hardware = computed(() => record(snapshot.value.hardware));
const fanRows = computed(() => dashboardFanRows(fans.value, hardware.value));
const readableNetworkHardware = computed(() => networkHardwareRows(network.value, hardware.value));
const camera = computed(() => record(snapshot.value.camera));
const cameraOptions = computed(() => record(snapshot.value.camera_options));
const capabilityVisibleFields = computed(() => new Set(deviceCapabilities.value?.visible_fields || []));
const shouldShowDashboardAms = computed(() => dashboardAmsSummaryRows.value.some(([, value]) => value !== "--" && value !== 0) || capabilityVisibleFields.value.has("ams"));
const shouldShowDashboardCamera = computed(() => cameraStatusRows.value.length > 0 || capabilityVisibleFields.value.has("camera"));
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
  return entries(cameraOptions.value).filter(([key]) => keys.has(key));
});
const cameraStatusRows = computed(() => {
  const optionKeys = new Set(["ipcam_record", "timelapse", "xcam_status", "raw_cfg"]);
  const optionRows = entries(cameraOptions.value).filter(([key]) => optionKeys.has(key));
  return [...readableCamera.value, ...optionRows];
});
const amsStatus = computed(() => record(snapshot.value.ams_status));
const coverage = computed(() => record(snapshot.value.data_coverage));
const coverageStatusRows = computed(() => entries(coverage.value).map(([key, item]) => ({
  key,
  received: record(item).received === true,
})));
const hmsErrors = computed(() => arrayOfRecord(snapshot.value.hms_errors));
const recentEvents = computed(() => dashboard.value?.recent_events || events.value);
const activeDerivedStatuses = computed(() => {
  const rows = entries(derived.value).filter(([key, value]) => {
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
  const printStatus = record(snapshot.value.print_status);
  const current = numeric(printStatus.layer_num ?? state.value.layer_num);
  const total = numeric(printStatus.total_layer_num ?? state.value.total_layer_num);
  if (current === null || total === null || total <= 0) return "";
  return `${Math.round(current)} / ${Math.round(total)}`;
});
const remainingTimeLabel = computed(() => {
  if (!dashboardHasActiveTask()) return "";
  return formatDurationMinutes(record(snapshot.value.print_status).mc_remaining_time ?? state.value.mc_remaining_time);
});
const rawOverviewItems = computed<DashboardSummaryItem[]>(() => {
  if (dashboardSummary.value.length) return dashboardSummary.value;
  return printers.value.map((printer) => ({ printer, state: null, device_snapshot: null }));
});
const overviewItems = computed<DashboardSummaryItem[]>(() => {
  const query = String(overviewControls.search || "").trim().toLowerCase();
  const filtered = rawOverviewItems.value.filter((item) => {
    const haystack = [
      item.printer.name,
      item.printer.host,
      summaryStatusLabel(item),
      record(summarySnapshot(item).hardware).model,
      record(summarySnapshot(item).firmware).hardware_version,
    ].join(" ").toLowerCase();
    if (query && !haystack.includes(query)) return false;
    if (overviewControls.filter === "online") return item.printer.connection_status === "connected";
    if (overviewControls.filter === "offline") return item.printer.connection_status !== "connected";
    if (overviewControls.filter === "printing") return summaryDerived(item).printing === true || summaryDerived(item).actual_printing === true;
    if (overviewControls.filter === "attention") return summaryHasAttention(item);
    if (overviewControls.filter === "hms") return summaryActiveHmsCount(item) > 0;
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
const metricGroups = computed(() => ({
  temperatures: metrics.value.filter((item) => item.metric.startsWith("temperature.")),
  fans: metrics.value.filter((item) => item.metric.startsWith("fan.") && item.metric !== "fan.fan_gear.percent"),
  wifi: metrics.value.filter((item) => item.metric === "network.wifi_signal"),
  ams: metrics.value.filter((item) => item.metric.startsWith("ams.")),
}));
const metricTooltipLabels = computed(() => ({
  time: t("table.time"),
  value: t("table.value"),
}));

const storageStats = computed(() => {
  const files = timelapseFiles.value;
  const totalSize = files.reduce((sum, item) => sum + (item.size || 0), 0);
  const usage = storageSummary.value?.storage_usage || {};
  const cards: { label: string; value: string | number; foot?: string }[] = [
    { label: t("storage.fileCount"), value: storageFiles.value.length },
    { label: t("storage.totalSize"), value: formatBytes(totalSize) },
    { label: t("storage.timelapseCount"), value: files.length },
  ];
  cards.push(storageUsageCard("internal", usage.internal));
  cards.push(storageUsageCard("external", usage.external));
  if (usage.current_target) {
    cards.push({ label: t("storage.currentTarget"), value: storageTargetLabel(usage.current_target) });
  }
  return cards;
});
const timelapseFiles = computed(() => storageFiles.value.filter((item) => isTimelapseStorageFile(item)));
const filteredTimelapseFiles = computed(() => {
  const query = storageSearch.value.trim().toLowerCase();
  const items = query
    ? timelapseFiles.value.filter((item) => `${item.name} ${item.path}`.toLowerCase().includes(query))
    : timelapseFiles.value;
  return [...items].sort((a, b) => compareStorageFiles(a, b, storageSort.value));
});
const storageTotalPages = computed(() => Math.max(1, Math.ceil(filteredTimelapseFiles.value.length / storagePageSize.value)));
const storagePreviewFiles = computed(() => {
  const start = (storagePage.value - 1) * storagePageSize.value;
  return filteredTimelapseFiles.value.slice(start, start + storagePageSize.value);
});
const groupedTimelapseFiles = computed(() => {
  const groups: Record<string, StorageFile[]> = {};
  for (const file of filteredTimelapseFiles.value) {
    const key = String(file.modified_at || "").slice(0, 10) || t("common.none");
    groups[key] = groups[key] || [];
    groups[key].push(file);
  }
  return Object.entries(groups).map(([date, files]) => ({ date, files }));
});
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
const dashboardAmsSummaryRows = computed(() => {
  const units = dashboard.value?.ams_units || [];
  const slots = dashboard.value?.ams_slots || [];
  const activeSlot = dashboardActiveAmsSlot(slots, amsStatus.value);
  const statusLabel = dashboardAmsStatusLabel(amsStatus.value);
  return [
    [t("ams.amsCount"), units.length],
    [t("ams.slotCount"), slots.length],
    [t("ams.loadedCount"), slots.filter((slot) => isDashboardAmsLoaded(slot)).length],
    [t("ams.emptyCount"), slots.filter((slot) => dashboardAmsSlotState(slot) === "empty").length],
    [t("ams.transitioningCount"), slots.filter((slot) => isDashboardAmsTransitioning(slot)).length],
    [t("ams.activeSlot"), dashboardAmsActiveSlotLabel(activeSlot, amsStatus.value)],
    [t("dashboard.activeMaterial"), dashboardActiveMaterialLabel(activeSlot)],
    [t("dashboard.amsStatus"), statusLabel],
  ] as [string, unknown][];
});
const dashboardAmsUnitRows = computed(() => {
  const units = dashboard.value?.ams_units || [];
  const slots = dashboard.value?.ams_slots || [];
  const knownUnitIds = new Set(units.map((unit) => String(unit.ams_id)));
  const rows = units.map((unit, index) => dashboardAmsUnitVisual(unit, slots, index));
  const orphanIds = Array.from(new Set(slots.map((slot) => String(slot.ams_id)).filter((amsId) => !knownUnitIds.has(amsId))));
  orphanIds.forEach((amsId) => {
    rows.push(dashboardAmsUnitVisual({ ams_id: amsId, ams_type_name: "AMS" }, slots, rows.length));
  });
  return rows;
});
const filteredEvents = computed(() => {
  return events.value.filter((item) => {
    if (eventFilters.type && item.type !== eventFilters.type) return false;
    if (eventFilters.severity && item.severity !== eventFilters.severity) return false;
    if (eventFilters.active === "active" && item.active !== true) return false;
    if (eventFilters.active === "inactive" && item.active !== false) return false;
    return true;
  });
});
const printLogPage = computed(() => Math.floor(printLogFilters.offset / printLogFilters.limit) + 1);
const printLogTotalPages = computed(() => Math.max(1, Math.ceil(printLogTotal.value / printLogFilters.limit)));
const maintenanceStats = computed(() => [
  { label: t("maintenance.due"), value: maintenanceOverview.value?.due_count || 0, tone: "bad" },
  { label: t("maintenance.soon"), value: maintenanceOverview.value?.soon_count || 0, tone: "warn" },
  { label: t("maintenance.ok"), value: maintenanceOverview.value?.ok_count || 0, tone: "good" },
]);
const maintenanceStatusGroups = computed(() => {
  const groups = [
    { key: "due", label: t("maintenance.due"), tone: "bad" },
    { key: "soon", label: t("maintenance.soon"), tone: "warn" },
    { key: "ok", label: t("maintenance.ok"), tone: "good" },
    { key: "disabled", label: t("values.disabled"), tone: "muted" },
  ];
  return groups
    .map((group) => ({
      ...group,
      items: maintenanceItems.value.filter((item) => item.due_status === group.key),
    }))
    .filter((group) => group.items.length);
});
const maintenanceHealthPercent = computed(() => {
  const enabled = maintenanceItems.value.filter((item) => item.due_status !== "disabled");
  if (!enabled.length) return 0;
  const ok = enabled.filter((item) => item.due_status === "ok").length;
  return Math.round((ok / enabled.length) * 100);
});
const selectedPrinterPrintHours = computed(() => maintenanceItems.value[0]?.current_print_hours ?? 0);
const scanProgressLabel = computed(() => Math.round(scanProgress.value));
const scanProgressWidth = computed(() => Math.max(0, Math.min(100, scanProgress.value)));

const printerStatusTone = computed(() => {
  const status = selectedPrinter.value?.connection_status;
  if (status === "connected") return "good";
  if (status === "error") return "bad";
  if (status === "connecting") return "warn";
  return "muted";
});
const canRequestFullRefresh = computed(() => selectedPrinter.value?.connection_status === "connected");

watch(selectedPrinter, (printer) => {
  if (printer) populatePrinterForm(printer);
});

watch([storageSearch, storageSort, () => storageFiles.value.length], () => {
  storagePage.value = 1;
});

watch(overviewControls, () => {
  window.localStorage.setItem("filamentManager.overviewControls", JSON.stringify(overviewControls));
}, { deep: true });

watch(storageTotalPages, (pages) => {
  if (storagePage.value > pages) storagePage.value = pages;
});

watch(experimentalFeatures, () => {
  saveExperimentalFeatureSettings();
  if (!isViewEnabled(activeView.value)) {
    activeView.value = "overview";
    window.localStorage.setItem("filamentManager.activeView", "overview");
    void withLoading(loadCurrent);
  }
}, { deep: true });

onMounted(async () => {
  await bootstrap();
  connectEventStream();
});

onBeforeUnmount(() => {
  closeEventStream();
});

async function bootstrap() {
  await withLoading(async () => {
    await refreshPrinters();
    await loadCurrent();
  });
}

async function loadCurrent() {
  if (!isViewEnabled(activeView.value)) {
    activeView.value = "overview";
    window.localStorage.setItem("filamentManager.activeView", "overview");
  }
  if (activeView.value === "overview") {
    await loadOverview();
    return;
  }
  if (activeView.value === "events") {
    await loadEvents();
    return;
  }
  if (activeView.value === "printLog") {
    await loadPrintLog();
    return;
  }
  if (activeView.value === "maintenance") {
    await loadMaintenance();
    return;
  }
  if (activeView.value === "notifications") {
    await loadNotifications();
    return;
  }
  if (activeView.value === "inventory") {
    await loadInventory();
    return;
  }
  if (activeView.value === "debug") {
    await loadDebug();
    return;
  }
  if (!selectedPrinterId.value) return;
  if (activeView.value === "dashboard") await loadDashboard();
  if (activeView.value === "metrics") await loadMetrics();
  if (activeView.value === "storage") await loadStorage();
  if (activeView.value === "ams") await loadAms();
}

async function refreshCurrentView() {
  if (activeView.value === "dashboard") {
    await requestRefreshFull();
    return;
  }
  if (activeView.value === "storage") {
    await scanStorage();
    return;
  }
  await withLoading(async () => {
    if (activeView.value === "overview") {
      await refreshPrinters();
      await loadOverview();
      return;
    }
    if (activeView.value === "printers") {
      await refreshPrinters();
      if (selectedPrinter.value) populatePrinterForm(selectedPrinter.value);
      return;
    }
    await loadCurrent();
  });
}

async function switchView(key: ViewKey) {
  if (!isViewEnabled(key)) {
    await switchView("overview");
    return;
  }
  activeView.value = key;
  resetTransientCollapsedSections(key);
  window.localStorage.setItem("filamentManager.activeView", key);
  await withLoading(loadCurrent);
}

async function refreshPrinters() {
  printers.value = await apiRequest<Printer[]>("/printers");
  if (!selectedPrinterId.value && printers.value.length) {
    selectedPrinterId.value = printers.value[0].id;
  }
  if (selectedPrinter.value) populatePrinterForm(selectedPrinter.value);
}

async function savePrinter() {
  await withLoading(async () => {
    const updatingExisting = Boolean(selectedPrinterId.value);
    const payload: Record<string, unknown> = {
      name: printerForm.name,
      host: printerForm.host,
      port: Number(printerForm.port),
      serial: printerForm.serial,
      access_code: printerForm.access_code,
      tls_enabled: printerForm.tls_enabled,
      certificate_verify: printerForm.certificate_verify,
    };
    const printer = updatingExisting
      ? await apiRequest<Printer>(`/printers/${selectedPrinterId.value}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      })
      : await apiRequest<Printer>("/printers", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    selectedPrinterId.value = printer.id;
    await refreshPrinters();
    message.value = updatingExisting ? t("message.printerUpdated") : t("message.printerSaved");
  });
}

async function handlePrinterSelectionChanged() {
  if (selectedPrinter.value) populatePrinterForm(selectedPrinter.value);
  await loadCurrent();
}

function populatePrinterForm(printer: Printer) {
  printerForm.name = printer.name;
  printerForm.host = printer.host;
  printerForm.port = printer.port;
  printerForm.serial = printer.serial;
  printerForm.access_code = printer.access_code || "";
  printerForm.tls_enabled = printer.tls_enabled;
  printerForm.certificate_verify = printer.certificate_verify;
  accessCodeVisible.value = false;
  accessCodeRevealLoading.value = false;
}

function resetPrinterForm() {
  printerForm.name = "Printer";
  printerForm.host = "";
  printerForm.port = 8883;
  printerForm.serial = "";
  printerForm.access_code = "";
  printerForm.tls_enabled = true;
  printerForm.certificate_verify = false;
  accessCodeVisible.value = false;
  accessCodeRevealLoading.value = false;
}

function isMaskedAccessCode(value: string) {
  return value.startsWith("****");
}

async function toggleAccessCodeVisibility() {
  if (accessCodeVisible.value) {
    accessCodeVisible.value = false;
    return;
  }
  if (selectedPrinterId.value && isMaskedAccessCode(printerForm.access_code)) {
    accessCodeRevealLoading.value = true;
    error.value = "";
    try {
      const result = await apiRequest<{ access_code: string }>(`/printers/${selectedPrinterId.value}/access-code`);
      printerForm.access_code = result.access_code || "";
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err);
      return;
    } finally {
      accessCodeRevealLoading.value = false;
    }
  }
  accessCodeVisible.value = true;
}

async function scanDevices() {
  scanning.value = true;
  scanProgress.value = 2;
  scanPhase.value = t("scan.phaseStart");
  let animationFrame = 0;
  let animating = true;
  const startedAt = window.performance.now();
  const animate = () => {
    if (!animating) return;
    const elapsedSeconds = (window.performance.now() - startedAt) / 1000;
    const easedTarget = Math.min(98, 4 + 94 * (1 - Math.exp(-elapsedSeconds / 4.8)));
    scanProgress.value = Math.max(scanProgress.value, easedTarget);
    if (scanProgress.value < 34) {
      scanPhase.value = t("scan.phasePorts");
    } else if (scanProgress.value < 72) {
      scanPhase.value = t("scan.phaseVerify");
    } else {
      scanPhase.value = t("scan.phaseCollect");
    }
    animationFrame = window.requestAnimationFrame(animate);
  };
  animationFrame = window.requestAnimationFrame(animate);
  await withLoading(async () => {
    try {
      discovery.value = await apiRequest<DiscoveryCandidate[]>("/discovery/scan");
      animating = false;
      window.cancelAnimationFrame(animationFrame);
      scanProgress.value = 100;
      scanPhase.value = discovery.value.length
        ? t("scan.found", { count: discovery.value.length })
        : t("scan.notFound");
      if (discovery.value.length) {
        const first = discovery.value[0];
        printerForm.name = first.device_name || "Bambu Printer";
        printerForm.host = first.host;
        printerForm.serial = first.serial || "";
        printerForm.port = 8883;
      }
    } finally {
      animating = false;
      window.cancelAnimationFrame(animationFrame);
      window.setTimeout(() => {
        scanning.value = false;
      }, 800);
    }
  });
}

async function connectPrinter() {
  if (!selectedPrinterId.value) return;
  await withLoading(async () => {
    await apiRequest<Printer>(`/printers/${selectedPrinterId.value}/connect`, { method: "POST" });
    await refreshPrinters();
    await loadCurrent();
    message.value = t("message.connectSent");
  });
}

async function disconnectPrinter() {
  if (!selectedPrinterId.value) return;
  await withLoading(async () => {
    await apiRequest<Printer>(`/printers/${selectedPrinterId.value}/disconnect`, { method: "POST" });
    await refreshPrinters();
    await loadCurrent();
    message.value = t("message.disconnected");
  });
}

async function deletePrinterConfig(printer: Printer) {
  const confirmed = window.confirm(t("printers.deleteConfirm", { name: printer.name }));
  if (!confirmed) return;
  await withLoading(async () => {
    await apiRequest(`/printers/${printer.id}`, { method: "DELETE" });
    if (selectedPrinterId.value === printer.id) {
      selectedPrinterId.value = null;
    }
    await refreshPrinters();
    if (!selectedPrinterId.value && printers.value.length) {
      selectedPrinterId.value = printers.value[0].id;
    }
    if (selectedPrinter.value) {
      populatePrinterForm(selectedPrinter.value);
    } else {
      resetPrinterForm();
    }
    await loadCurrent();
    message.value = t("message.printerDeleted");
  });
}

async function requestRefreshFull() {
  if (!selectedPrinterId.value) return;
  if (!canRequestFullRefresh.value) {
    await withLoading(loadDashboard);
    error.value = t("error.fullRefreshNotConnected");
    return;
  }
  await withLoading(async () => {
    const previousMarker = dashboardRefreshMarker(dashboard.value);
    await apiRequest<Record<string, string>>(`/printers/${selectedPrinterId.value}/refresh-full`, { method: "POST" });
    const refreshed = await waitForDashboardRefresh(previousMarker);
    if (!refreshed) await loadDashboard();
    message.value = t("message.fullRefreshRequested");
  });
}

async function fetchDashboard() {
  if (!selectedPrinterId.value) return null;
  return apiRequest<Dashboard>(`/printers/${selectedPrinterId.value}/dashboard`);
}

async function loadDashboard() {
  if (!selectedPrinterId.value) return;
  const [result, capabilities] = await Promise.all([
    fetchDashboard(),
    apiRequest<DeviceCapabilities>(`/printers/${selectedPrinterId.value}/capabilities`),
  ]);
  if (result) dashboard.value = result;
  deviceCapabilities.value = capabilities;
}

async function loadOverview() {
  const summaryResult = await apiRequest<DashboardSummaryItem[]>("/dashboard/summary");
  dashboardSummary.value = summaryResult;
  if (!selectedPrinterId.value && dashboardSummary.value.length) {
    selectedPrinterId.value = dashboardSummary.value[0].printer.id;
  }
}

async function openPrinterDashboard(printerId: number) {
  selectedPrinterId.value = printerId;
  await switchView("dashboard");
}

async function loadMetrics() {
  if (!selectedPrinterId.value) return;
  const since = metricSince();
  const bucket = metricRange.value === "30d" || metricRange.value === "7d" ? "hour" : metricRange.value === "1h" ? "minute" : "raw";
  metrics.value = await apiRequest<MetricSample[]>(
    `/printers/${selectedPrinterId.value}/metrics?limit=1000&bucket=${bucket}&since=${encodeURIComponent(since)}`,
  );
}

async function loadPrintLog() {
  const params = new URLSearchParams({
    limit: String(printLogFilters.limit),
    offset: String(printLogFilters.offset),
  });
  if (printLogFilters.printer_id) params.set("printer_id", printLogFilters.printer_id);
  if (printLogFilters.status) params.set("status", printLogFilters.status);
  if (printLogFilters.search) params.set("search", printLogFilters.search);
  if (printLogFilters.date_from) params.set("date_from", new Date(printLogFilters.date_from).toISOString());
  if (printLogFilters.date_to) params.set("date_to", new Date(printLogFilters.date_to).toISOString());
  const analyticsParams = new URLSearchParams();
  if (printLogFilters.printer_id) analyticsParams.set("printer_id", printLogFilters.printer_id);
  if (printLogFilters.date_from) analyticsParams.set("from", new Date(printLogFilters.date_from).toISOString());
  if (printLogFilters.date_to) analyticsParams.set("to", new Date(printLogFilters.date_to).toISOString());
  const [listResult, summaryResult, analyticsResult] = await Promise.all([
    apiRequest<PrintLogList>(`/print-log?${params.toString()}`),
    apiRequest<PrintLogSummary>("/print-log/summary"),
    apiRequest<PrintLogAnalytics>(`/print-log/analytics?${analyticsParams.toString()}`),
  ]);
  printLogs.value = listResult.items;
  printLogTotal.value = listResult.total;
  printLogSummary.value = summaryResult;
  printLogAnalytics.value = analyticsResult;
}

async function applyPrintLogFilters() {
  printLogFilters.offset = 0;
  await withLoading(loadPrintLog);
}

async function changePrintLogPage(delta: number) {
  const next = printLogFilters.offset + delta * printLogFilters.limit;
  printLogFilters.offset = Math.max(0, Math.min(next, Math.max(0, printLogTotal.value - 1)));
  await withLoading(loadPrintLog);
}

async function loadStorage() {
  if (!selectedPrinterId.value) return;
  const [filesResult, summaryResult, notesResult] = await Promise.all([
    apiRequest<StorageFile[]>(`/printers/${selectedPrinterId.value}/storage/files`),
    apiRequest<StorageSummary>(`/printers/${selectedPrinterId.value}/storage/summary`),
    apiRequest<TimelapseNote[]>(`/printers/${selectedPrinterId.value}/timelapse/notes`),
  ]);
  storageFiles.value = filesResult;
  storageSummary.value = summaryResult;
  timelapseNotes.value = Object.fromEntries(notesResult.map((note) => [note.path, note]));
  for (const note of notesResult) timelapseNoteDrafts[note.path] = note.note || "";
}

async function scanStorage() {
  if (!selectedPrinterId.value) return;
  await withLoading(async () => {
    storageResult.value = await apiRequest<Record<string, any>>(`/printers/${selectedPrinterId.value}/storage/scan`, {
      method: "POST",
    });
    await loadStorage();
  });
}

async function loadAms() {
  if (!selectedPrinterId.value) return;
  const [stateResult, overviewResult, slotResult, eventResult] = await Promise.all([
    apiRequest<Record<string, any> | null>(`/printers/${selectedPrinterId.value}/state`),
    apiRequest<AmsOverview>(`/printers/${selectedPrinterId.value}/ams/overview`),
    apiRequest<Record<string, any>[]>(`/printers/${selectedPrinterId.value}/ams/slots`),
    apiRequest<UnifiedEvent[]>(`/events?printer_id=${selectedPrinterId.value}&limit=50`),
  ]);
  stateSnapshot.value = stateResult;
  amsOverview.value = overviewResult;
  amsSlots.value = slotResult;
  events.value = eventResult;
  for (const unit of overviewResult.units) {
    amsLabelDrafts[unit.ams_id] = unit.display_name || "";
    if (!unit.display_name) amsLabelEditing[unit.ams_id] = false;
  }
  await loadAmsSensorHistories();
}

async function loadAmsSensorHistories() {
  if (!selectedPrinterId.value || !amsOverview.value) return;
  const entries = await Promise.all(
    amsOverview.value.units
      .filter((unit) => unit.ams_id !== "unknown")
      .map(async (unit) => {
        const history = await apiRequest<AmsSensorHistory>(
          `/printers/${selectedPrinterId.value}/ams/${encodeURIComponent(unit.ams_id)}/sensor-history?hours=${amsSensorRange.value}`,
        );
        return [unit.ams_id, history] as const;
      }),
  );
  amsSensorHistories.value = Object.fromEntries(entries);
}

async function saveAmsLabel(unit: Record<string, any>) {
  if (!selectedPrinterId.value) return;
  const displayName = (amsLabelDrafts[String(unit.ams_id)] || "").trim();
  if (!displayName) {
    await clearAmsLabel(unit);
    return;
  }
  await withLoading(async () => {
    await apiRequest(`/printers/${selectedPrinterId.value}/ams-labels/${encodeURIComponent(String(unit.ams_id))}`, {
      method: "PATCH",
      body: JSON.stringify({ display_name: displayName }),
    });
    amsLabelEditing[String(unit.ams_id)] = false;
    await loadAms();
  });
}

async function clearAmsLabel(unit: Record<string, any>) {
  if (!selectedPrinterId.value) return;
  await withLoading(async () => {
    await apiRequest(`/printers/${selectedPrinterId.value}/ams-labels/${encodeURIComponent(String(unit.ams_id))}`, {
      method: "DELETE",
    });
    amsLabelDrafts[String(unit.ams_id)] = "";
    amsLabelEditing[String(unit.ams_id)] = false;
    await loadAms();
  });
}

async function loadMaintenance() {
  const [overviewResult, itemResult] = await Promise.all([
    apiRequest<MaintenanceOverview>("/maintenance/overview"),
    selectedPrinterId.value
      ? apiRequest<PrinterMaintenance[]>(`/printers/${selectedPrinterId.value}/maintenance`)
      : Promise.resolve([]),
  ]);
  maintenanceOverview.value = overviewResult;
  maintenanceItems.value = itemResult;
}

async function performMaintenance(item: PrinterMaintenance) {
  await withLoading(async () => {
    await apiRequest(`/maintenance/items/${item.id}/perform`, {
      method: "POST",
      body: JSON.stringify({ note: maintenanceNotes[item.id] || null }),
    });
    maintenanceNotes[item.id] = "";
    await loadMaintenance();
    message.value = t("maintenance.performed");
  });
}

async function loadInventory() {
  spools.value = await apiRequest<Spool[]>("/spools");
}

async function createSpool() {
  await withLoading(async () => {
    await apiRequest<Spool>("/spools", {
      method: "POST",
      body: JSON.stringify({
        ...spoolForm,
        brand: spoolForm.brand || null,
        material: spoolForm.material || null,
        series: spoolForm.series || null,
        color: spoolForm.color || null,
        sealed_quantity: Number(spoolForm.sealed_quantity),
      }),
    });
    spoolForm.display_name = "";
    await loadInventory();
    message.value = t("message.spoolCreated");
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

async function loadDebug() {
  const [raw, eventResult, infoResult] = await Promise.all([
    apiRequest<Record<string, any>[]>("/debug/raw-mqtt?limit=20"),
    apiRequest<UnifiedEvent[]>("/events?limit=80"),
    apiRequest<SystemInfo>("/system/info"),
  ]);
  rawMqtt.value = raw;
  events.value = eventResult;
  systemInfo.value = infoResult;
}

async function loadNotifications() {
  const [targets, rules, deliveries] = await Promise.all([
    apiRequest<NotificationTarget[]>("/notifications/targets"),
    apiRequest<NotificationRule[]>("/notifications/rules"),
    apiRequest<NotificationDelivery[]>("/notifications/deliveries?limit=50"),
  ]);
  notificationTargets.value = targets;
  notificationRules.value = rules;
  notificationDeliveries.value = deliveries;
}

async function saveNotificationTarget() {
  const payload = {
    channel: notificationTargetForm.channel,
    name: notificationTargetForm.name || notificationTargetForm.channel,
    enabled: notificationTargetForm.enabled,
    config: {
      url: notificationTargetForm.url,
      token: notificationTargetForm.token || undefined,
    },
  };
  await withLoading(async () => {
    const id = notificationTargetForm.id;
    await apiRequest(id ? `/notifications/targets/${id}` : "/notifications/targets", {
      method: id ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    resetNotificationTargetForm();
    await loadNotifications();
    message.value = t("notifications.saved");
  });
}

function editNotificationTarget(target: NotificationTarget) {
  notificationTargetForm.id = String(target.id);
  notificationTargetForm.channel = target.channel;
  notificationTargetForm.name = target.name;
  notificationTargetForm.url = String(target.display_config?.url || target.display_config?.topic_url || target.config?.url || "");
  notificationTargetForm.token = "";
  notificationTargetForm.enabled = target.enabled;
}

function resetNotificationTargetForm() {
  notificationTargetForm.id = "";
  notificationTargetForm.channel = "webhook";
  notificationTargetForm.name = "";
  notificationTargetForm.url = "";
  notificationTargetForm.token = "";
  notificationTargetForm.enabled = true;
}

async function deleteNotificationTarget(target: NotificationTarget) {
  await withLoading(async () => {
    await apiRequest(`/notifications/targets/${target.id}`, { method: "DELETE" });
    await loadNotifications();
  });
}

async function testNotificationTarget(target: NotificationTarget) {
  await withLoading(async () => {
    await apiRequest(`/notifications/targets/${target.id}/test`, { method: "POST" });
    await loadNotifications();
    message.value = t("notifications.testSent");
  });
}

async function saveNotificationRule() {
  const policy: Record<string, unknown> = {};
  if (notificationRuleForm.quiet_start) policy.quiet_start = notificationRuleForm.quiet_start;
  if (notificationRuleForm.quiet_end) policy.quiet_end = notificationRuleForm.quiet_end;
  if (notificationRuleForm.repeat_suppression_minutes) {
    policy.repeat_suppression_minutes = Number(notificationRuleForm.repeat_suppression_minutes);
  }
  const payload = {
    name: notificationRuleForm.name || t("notifications.defaultRuleName"),
    enabled: notificationRuleForm.enabled,
    event_types: splitCsv(notificationRuleForm.event_types),
    printer_ids: splitCsv(notificationRuleForm.printer_ids).map(Number).filter(Number.isFinite),
    severities: splitCsv(notificationRuleForm.severities),
    quiet_policy: policy,
  };
  await withLoading(async () => {
    const id = notificationRuleForm.id;
    await apiRequest(id ? `/notifications/rules/${id}` : "/notifications/rules", {
      method: id ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    resetNotificationRuleForm();
    await loadNotifications();
    message.value = t("notifications.ruleSaved");
  });
}

function editNotificationRule(rule: NotificationRule) {
  notificationRuleForm.id = String(rule.id);
  notificationRuleForm.name = rule.name;
  notificationRuleForm.event_types = (rule.event_types || []).join(", ");
  notificationRuleForm.printer_ids = (rule.printer_ids || []).join(", ");
  notificationRuleForm.severities = (rule.severities || []).join(", ");
  notificationRuleForm.quiet_start = String(rule.quiet_policy?.quiet_start || "");
  notificationRuleForm.quiet_end = String(rule.quiet_policy?.quiet_end || "");
  notificationRuleForm.repeat_suppression_minutes = Number(rule.quiet_policy?.repeat_suppression_minutes || 30);
  notificationRuleForm.enabled = rule.enabled;
}

function resetNotificationRuleForm() {
  notificationRuleForm.id = "";
  notificationRuleForm.name = "";
  notificationRuleForm.event_types = "";
  notificationRuleForm.printer_ids = "";
  notificationRuleForm.severities = "";
  notificationRuleForm.quiet_start = "";
  notificationRuleForm.quiet_end = "";
  notificationRuleForm.repeat_suppression_minutes = 30;
  notificationRuleForm.enabled = true;
}

async function deleteNotificationRule(rule: NotificationRule) {
  await withLoading(async () => {
    await apiRequest(`/notifications/rules/${rule.id}`, { method: "DELETE" });
    await loadNotifications();
  });
}

async function downloadSupportBundle() {
  await withLoading(async () => {
    const bundle = await apiRequest<Record<string, any>>("/support/bundle");
    bundle.frontend = {
      ...(record(bundle.frontend)),
      browser: window.navigator.userAgent,
      language: window.navigator.language,
      downloaded_at: new Date().toISOString(),
      experimental_features: { ...experimentalFeatures },
    };
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `filament-manager-support-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });
}

async function downloadExport() {
  const params = new URLSearchParams({
    type: exportOptions.type,
    sections: exportOptions.sections.join(","),
  });
  await withLoading(async () => {
    const response = await fetch(`${API_BASE}/export?${params.toString()}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = exportOptions.type === "csv" ? "filament-manager-export.zip" : "filament-manager-export.json";
    link.click();
    URL.revokeObjectURL(url);
  });
}

async function loadEvents() {
  const params = new URLSearchParams({ limit: "120" });
  if (selectedPrinterId.value) params.set("printer_id", String(selectedPrinterId.value));
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
    if (selectedPrinterId.value) params.set("printer_id", String(selectedPrinterId.value));
    selectedHmsStats.value = await apiRequest<HmsCodeStats>(`/hms/codes/${encodeURIComponent(String(shortCode))}/stats?${params.toString()}`);
  }
}

async function openSlotDetails(slot: Record<string, any>) {
  if (!selectedPrinterId.value) return;
  selectedSlot.value = slot;
  const params = new URLSearchParams({ ams_id: String(slot.ams_id), tray_id: String(slot.tray_id), limit: "80" });
  selectedSlotHistory.value = await apiRequest<AmsSlotHistorySample[]>(
    `/printers/${selectedPrinterId.value}/ams/history?${params.toString()}`,
  );
}

async function withLoading(action: () => Promise<void>) {
  const token = beginLoading();
  const watchdog = window.setTimeout(() => finishLoading(token), 20000);
  error.value = "";
  message.value = "";
  try {
    await action();
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    window.clearTimeout(watchdog);
    finishLoading(token);
  }
}

function beginLoading() {
  const token = ++loadingTokenSeq;
  activeLoadingTokens.add(token);
  activeLoadingCount.value = activeLoadingTokens.size;
  return token;
}

function finishLoading(token: number) {
  if (!activeLoadingTokens.delete(token)) return;
  activeLoadingCount.value = activeLoadingTokens.size;
}

function metricSince() {
  const now = Date.now();
  const hours: Record<string, number> = { "1h": 1, "6h": 6, "24h": 24, "7d": 24 * 7, "30d": 24 * 30 };
  return new Date(now - (hours[metricRange.value] || 6) * 60 * 60 * 1000).toISOString();
}

function connectEventStream() {
  closeEventStream();
  eventSource = new EventSource(`${apiBaseForSse()}/events/stream`);
  const refresh = () => handleRealtimeEvent();
  eventSource.onopen = () => {
    realtimeDisconnected.value = false;
    stopPollingFallback();
  };
  eventSource.onerror = () => {
    realtimeDisconnected.value = true;
    startPollingFallback();
  };
  for (const name of [
    "printer.status.updated",
    "device.snapshot.updated",
    "hms.error.active",
    "hms.error.recovered",
    "ams.unit.updated",
    "ams.slot.updated",
    "print.started",
    "print.finished",
    "print.failed",
    "print.cancelled",
    "storage.scan.finished",
    "storage.scan.failed",
  ]) {
    eventSource.addEventListener(name, refresh);
  }
}

function closeEventStream() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  stopPollingFallback();
}

function startPollingFallback() {
  if (pollingTimer !== null) return;
  pollingTimer = window.setInterval(() => {
    void loadCurrent();
  }, 10000);
}

function stopPollingFallback() {
  if (pollingTimer === null) return;
  window.clearInterval(pollingTimer);
  pollingTimer = null;
}

function handleRealtimeEvent() {
  if (activeView.value === "events") {
    void loadEvents();
    return;
  }
  void loadCurrent();
}

function apiBaseForSse() {
  return (import.meta.env.VITE_FILAMENT_MANAGER_API_URL as string | undefined)?.replace(/\/$/, "") || "/api";
}

function loadExperimentalFeatureSettings(): Record<ExperimentalFeatureKey, boolean> {
  try {
    const stored = JSON.parse(window.localStorage.getItem("filamentManager.experimentalFeatures") || "{}");
    return {
      timelapse: stored.timelapse === true,
      maintenance: stored.maintenance === true,
      printLog: stored.printLog === true,
      notifications: stored.notifications === true,
    };
  } catch {
    return { ...experimentalFeatureDefaults };
  }
}

function loadOverviewControls() {
  try {
    const stored = JSON.parse(window.localStorage.getItem("filamentManager.overviewControls") || "{}");
    return {
      search: String(stored.search || ""),
      filter: String(stored.filter || "all"),
      sort: String(stored.sort || "attention"),
      density: String(stored.density || "standard"),
    };
  } catch {
    return { search: "", filter: "all", sort: "attention", density: "standard" };
  }
}

function saveExperimentalFeatureSettings() {
  window.localStorage.setItem("filamentManager.experimentalFeatures", JSON.stringify(experimentalFeatures));
}

function resolveInitialView(view: ViewKey | null) {
  if (!viewKeys.includes(view as ViewKey)) return "overview";
  const next = view as ViewKey;
  return isViewEnabled(next) ? next : "overview";
}

function isViewEnabled(view: ViewKey) {
  const feature = experimentalFeatureViews[view];
  return !feature || experimentalFeatures[feature] === true;
}

function loadSectionLayouts() {
  try {
    const layouts = JSON.parse(window.localStorage.getItem("filamentManager.sectionLayouts") || "{}");
    if (layouts?.ams) {
      layouts.ams = Object.fromEntries(
        Object.entries(layouts.ams).filter(([key]) => !key.startsWith("ams.unit.")),
      );
    }
    return layouts;
  } catch {
    return {};
  }
}

function saveSectionLayouts() {
  window.localStorage.setItem("filamentManager.sectionLayouts", JSON.stringify(sectionLayouts.value));
}

function sectionConfig(id: string) {
  const view = activeView.value;
  const current = sectionLayouts.value[view] || {};
  if (!current[id]) {
    current[id] = {};
    sectionLayouts.value = { ...sectionLayouts.value, [view]: current };
  }
  return current[id];
}

function isSectionVisible(id: string) {
  return sectionConfig(id).hidden !== true;
}

function isSectionCollapsed(id: string) {
  if (isTransientCollapsedSection(id)) {
    if (transientCollapsedSections.value[id] !== undefined) return transientCollapsedSections.value[id];
    return defaultSectionCollapsed(id);
  }
  const current = sectionLayouts.value[activeView.value] || {};
  if (current[id]?.collapsed !== undefined) return current[id].collapsed === true;
  return defaultSectionCollapsed(id);
}

function toggleSectionCollapsed(id: string) {
  if (isTransientCollapsedSection(id)) {
    transientCollapsedSections.value = {
      ...transientCollapsedSections.value,
      [id]: !isSectionCollapsed(id),
    };
    return;
  }
  const config = sectionConfig(id);
  config.collapsed = !isSectionCollapsed(id);
  saveSectionLayouts();
}

function defaultSectionCollapsed(id: string) {
  return activeView.value === "ams" && id.startsWith("ams.unit.");
}

function isTransientCollapsedSection(id: string) {
  return activeView.value === "ams" && id.startsWith("ams.unit.");
}

function resetTransientCollapsedSections(view: ViewKey = activeView.value) {
  if (view === "ams") transientCollapsedSections.value = {};
}

function toggleSectionHidden(id: string) {
  const config = sectionConfig(id);
  config.hidden = !config.hidden;
  saveSectionLayouts();
}

function record(value: unknown): Record<string, any> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, any>) : {};
}

function arrayOfRecord(value: unknown): Record<string, any>[] {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") : [];
}

function entries(value: Record<string, any>) {
  return Object.entries(value).filter(([, item]) => item !== null && item !== undefined && item !== "");
}

function t(key: string, vars: Record<string, string | number> = {}) {
  const table = translations[locale.value] as Record<string, string>;
  const fallback = translations["zh-CN"] as Record<string, string>;
  let text = table[key] || fallback[key] || key;
  for (const [name, value] of Object.entries(vars)) {
    text = text.replace(`{${name}}`, String(value));
  }
  return text;
}

function navLabel(key: string) {
  return t(`nav.${key}`);
}

function navItemsByGroup(group: NavGroupKey) {
  return navItems.filter((item) => item.group === group && isViewEnabled(item.key));
}

function summarySnapshot(item: DashboardSummaryItem): Record<string, any> {
  return record(item.device_snapshot);
}

function summaryState(item: DashboardSummaryItem): Record<string, any> {
  return record(item.state);
}

function summaryDerived(item: DashboardSummaryItem): Record<string, any> {
  return record(summarySnapshot(item).derived_status);
}

function summaryTemperatures(item: DashboardSummaryItem): Record<string, any> {
  return record(summarySnapshot(item).temperatures);
}

function summaryNetwork(item: DashboardSummaryItem): Record<string, any> {
  return record(summarySnapshot(item).network);
}

function summaryCoverage(item: DashboardSummaryItem): Record<string, any> {
  return record(summarySnapshot(item).data_coverage);
}

function summaryCoveragePercent(item: DashboardSummaryItem) {
  const rows = entries(summaryCoverage(item));
  if (!rows.length) return 0;
  const received = rows.filter(([, value]) => record(value).received === true).length;
  return Math.round((received / rows.length) * 100);
}

function summaryActiveHmsCount(item: DashboardSummaryItem) {
  return arrayOfRecord(summarySnapshot(item).hms_errors).filter((event) => event.active !== false && event.actionable !== false).length;
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
  if (overviewControls.sort === "printing") {
    return Number(summaryDerived(right).printing === true || summaryDerived(right).actual_printing === true)
      - Number(summaryDerived(left).printing === true || summaryDerived(left).actual_printing === true)
      || left.printer.name.localeCompare(right.printer.name, locale.value);
  }
  if (overviewControls.sort === "name") {
    return left.printer.name.localeCompare(right.printer.name, locale.value);
  }
  if (overviewControls.sort === "last_sync") {
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
    return displayCell(item.printer.connection_status);
  }
  if (summaryHasAttention(item)) return t("overview.needsAttention");
  if (derivedValue.user_state) return displayCell(derivedValue.user_state);
  if (derivedValue.preparing === true) return t("values.preparing");
  if (derivedValue.actual_printing === true) return t("values.actual_printing");
  if (derivedValue.printing === true) return t("values.printing");
  if (derivedValue.paused === true) return t("values.paused");
  if (derivedValue.idle === true) return t("values.idle");
  return displayCell(stateValue.gcode_state || item.printer.connection_status);
}

function summaryTaskName(item: DashboardSummaryItem) {
  const stateValue = summaryState(item);
  return formatCell(stateValue.subtask_name || stateValue.gcode_file || t("dashboard.noActiveTask"));
}

function summaryProgress(item: DashboardSummaryItem) {
  return Math.round(percent(summaryState(item).mc_percent));
}

function summaryLayerFraction(item: DashboardSummaryItem) {
  const printStatus = record(summarySnapshot(item).print_status);
  const current = printStatus.layer_num ?? summaryState(item).layer_current ?? summaryState(item).layer_num;
  const total = printStatus.total_layer_num ?? summaryState(item).layer_total ?? summaryState(item).total_layer_num;
  if (current === undefined && total === undefined) return "--";
  return `${softCell(current)} / ${softCell(total)}`;
}

function summaryStage(item: DashboardSummaryItem) {
  const printStatus = record(summarySnapshot(item).print_status);
  return displayCell(printStatus.stg_cur_name || printStatus.sub_stage_name || printStatus.stage_name || summaryState(item).gcode_state || item.printer.connection_status);
}

function summaryTemperature(item: DashboardSummaryItem, key: string) {
  return formatCell(summaryTemperatures(item)[key]);
}

function summaryWifi(item: DashboardSummaryItem) {
  return formatCell(summaryNetwork(item).wifi_signal);
}

function fieldLabel(key: string) {
  const normalized = key.split(".").pop() || key;
  return t(`fields.${key}`) !== `fields.${key}`
    ? t(`fields.${key}`)
    : t(`fields.${normalized}`) !== `fields.${normalized}`
      ? t(`fields.${normalized}`)
      : key;
}

function valueLabel(value: unknown) {
  if (typeof value !== "string") return formatCell(value);
  return t(`values.${value}`) !== `values.${value}` ? t(`values.${value}`) : value;
}

function displayCell(value: unknown): string {
  if (typeof value === "boolean") return boolLabel(value);
  if (typeof value === "string") return valueLabel(value);
  return formatCell(value);
}

function fanDisplayPercent(item: unknown): number | null {
  const value = record(item);
  const parsed = numeric(value.percent);
  if (parsed === null) return null;
  return Math.max(0, Math.min(100, Math.round(parsed)));
}

function dashboardFanRows(fanValue: Record<string, any>, hardwareValue: Record<string, any>) {
  const rows = entries(fanValue)
    .filter(([key, item]) => key !== "fan_gear" && fanDisplayPercent(item) !== null) as [string, unknown][];
  const present = new Set(rows.map(([key]) => key));
  const parts = arrayOfRecord(record(hardwareValue.airduct).parts);
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

function softCell(value: unknown): string {
  const text = formatCell(value);
  return text === "—" ? "--" : text;
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

function maskSerial(value: unknown) {
  const text = String(value || "");
  if (!text) return "--";
  if (text.length <= 6) return "****";
  return `${text.slice(0, 3)}****${text.slice(-3)}`;
}

function amsTone(unit: Record<string, any>) {
  if (unit.ams_type_name === "AMS HT") return "ht";
  if (unit.ams_type_name === "AMS 2 Pro") return "pro";
  if (unit.ams_type_name === "unknown") return "unknown";
  return "standard";
}

function eventTone(event: UnifiedEvent | Record<string, any>) {
  if (event.severity === "error" || event.severity === "fatal") return "bad";
  if (event.severity === "warning") return "warn";
  return "good";
}

function derivedStatusTone(key: string) {
  if (key === "has_error") return "bad";
  if (key === "paused" || key === "ams_filament_change" || key === "ams_rfid_identifying") return "warn";
  return "good";
}

function slotKey(slot: Record<string, any>) {
  return `${slot.ams_id}-${slot.tray_id}-${slot.id || "slot"}`;
}

function amsSectionKey(unit: Record<string, any>) {
  return `ams.unit.${unit.ams_id}`;
}

function boolLabel(value: unknown): string {
  if (value === true) return t("common.on");
  if (value === false) return t("common.off");
  if (typeof value === "string") return valueLabel(value);
  return formatCell(value);
}

function statusTone(value: unknown) {
  if (value === true) return "on";
  if (value === false) return "off";
  const text = String(value ?? "").trim().toLowerCase();
  if (!text) return "";
  if (["enable", "enabled", "on", "open", "opened", "true", "yes", "received", "开启", "打开", "已收到"].includes(text)) return "on";
  if (["disable", "disabled", "off", "closed", "close", "false", "no", "missing", "关闭", "缺失"].includes(text)) return "off";
  return "";
}

function metricLabel(metric: string) {
  const [group, ...rest] = metric.split(".");
  if (group === "ams" && rest.length > 1) {
    const field = rest.slice(1).join(".");
    return `${fieldLabel("ams")} ${rest[0]} · ${fieldLabel(field === "humidity" ? "humidity_raw" : field)}`;
  }
  if (group === "fan") {
    return fanMetricLabel(rest[0] || rest.join("."));
  }
  const field = rest.join(".");
  const groupLabel = fieldLabel(group);
  const fieldName = fieldLabel(field);
  return field ? `${groupLabel} · ${fieldName}` : groupLabel;
}

function fanMetricLabel(source: string) {
  const mapping: Record<string, string> = {
    cooling_fan_speed: "toolhead_fan",
    big_fan1_speed: "right_aux_fan",
    big_fan2_speed: "exhaust_fan",
    heatbreak_fan_speed: "heatbreak_fan",
    chamber_fan_speed: "chamber_fan",
    aux_part_fan_speed: "aux_part_fan",
    fan_gear: "fan_gear",
  };
  return fieldLabel(mapping[source] || source);
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
    .map((key) => [key, value[key]] as [string, unknown]);
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
    .map((item) => `${fieldLabel(item)}: ${displayCell(source[item])}`);
  if (parts.length) rows.push([key, parts.join(" · ")]);
}

function displayPlateName(value: unknown) {
  const text = String(value ?? "").trim();
  if (!text) return "";
  if (/cool\s*\(?super\s*tack\)?/i.test(text) || text === "P0301") return t("values.cool_supertack_plate");
  return displayCell(value);
}

function percent(value: unknown, fallback = 0) {
  const parsed = numeric(value);
  if (parsed === null) return fallback;
  return Math.max(0, Math.min(100, parsed));
}

function temperaturePercent(current: unknown, target: unknown) {
  const currentValue = numeric(current) || 0;
  const targetValue = numeric(target) || 280;
  return percent((currentValue / Math.max(targetValue, 1)) * 100);
}

function formatBytes(value: number) {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function storageUsageCard(kind: "internal" | "external", usage: Record<string, any> | undefined) {
  const label = kind === "internal" ? t("storage.internalStorage") : t("storage.externalStorage");
  if (!usage || !usage.total_bytes) return { label, value: "--", foot: t("storage.usageUnknown") };
  const used = numeric(usage.used_bytes) || 0;
  const total = numeric(usage.total_bytes) || 0;
  return {
    label,
    value: `${formatBytes(used)} / ${formatBytes(total)}`,
    foot: t("storage.freeSpace", { value: formatBytes(numeric(usage.free_bytes) || 0), percent: usage.used_percent ?? "--" }),
  };
}

function storageTargetLabel(value: unknown) {
  const key = String(value || "");
  if (key === "internal") return t("storage.internalStorage");
  if (key === "external") return t("storage.externalStorage");
  return displayCell(value);
}

function storageFileUrl(file: StorageFile, inline = false) {
  if (!selectedPrinterId.value) return "#";
  const params = new URLSearchParams({ path: file.path });
  if (inline) params.set("inline", "true");
  return `${API_BASE}/printers/${selectedPrinterId.value}/storage/files/download?${params.toString()}`;
}

function timelapseNote(file: StorageFile) {
  return timelapseNotes.value[file.path] || null;
}

function timelapseNoteText(file: StorageFile) {
  return timelapseNoteDrafts[file.path] ?? timelapseNote(file)?.note ?? "";
}

function setTimelapseDraft(path: string, value: string) {
  timelapseNoteDrafts[path] = value;
}

async function toggleTimelapseFavorite(file: StorageFile) {
  if (!selectedPrinterId.value) return;
  const current = timelapseNote(file);
  await withLoading(async () => {
    const note = await apiRequest<TimelapseNote>(`/printers/${selectedPrinterId.value}/timelapse/notes`, {
      method: "PATCH",
      body: JSON.stringify({
        path: file.path,
        favorite: !(current?.favorite === true),
        cached_metadata: timelapseMetadata(file),
      }),
    });
    timelapseNotes.value = { ...timelapseNotes.value, [file.path]: note };
  });
}

async function saveTimelapseNote(file: StorageFile) {
  if (!selectedPrinterId.value) return;
  await withLoading(async () => {
    const note = await apiRequest<TimelapseNote>(`/printers/${selectedPrinterId.value}/timelapse/notes`, {
      method: "PATCH",
      body: JSON.stringify({
        path: file.path,
        note: timelapseNoteText(file),
        cached_metadata: timelapseMetadata(file),
      }),
    });
    timelapseNotes.value = { ...timelapseNotes.value, [file.path]: note };
    timelapseNoteDrafts[file.path] = note.note || "";
  });
}

function timelapseMetadata(file: StorageFile) {
  return {
    name: file.name,
    size: file.size,
    modified_at: file.modified_at,
    type: file.type,
    cover_cache: "browser-metadata",
  };
}

function isTimelapseStorageFile(file: StorageFile) {
  const type = String(file.type || "").toLowerCase();
  const name = String(file.name || file.path || "").toLowerCase();
  return type === "timelapse" || file.path.includes("/timelapse/") || /\.(mp4|mov|avi|mkv)$/i.test(name);
}

function compareStorageFiles(a: StorageFile, b: StorageFile, sortKey: string) {
  const nameCompare = (a.name || a.path).localeCompare(b.name || b.path, locale.value);
  if (sortKey === "modified_asc") return storageTime(a) - storageTime(b) || nameCompare;
  if (sortKey === "size_desc") return (b.size || 0) - (a.size || 0) || nameCompare;
  if (sortKey === "size_asc") return (a.size || 0) - (b.size || 0) || nameCompare;
  if (sortKey === "name_desc") return -nameCompare;
  if (sortKey === "name_asc") return nameCompare;
  return storageTime(b) - storageTime(a) || nameCompare;
}

function storageTime(file: StorageFile) {
  const value = Date.parse(String(file.modified_at || ""));
  return Number.isFinite(value) ? value : 0;
}

function changeStoragePage(delta: number) {
  storagePage.value = Math.max(1, Math.min(storageTotalPages.value, storagePage.value + delta));
}

function seekVideoPreviewToEnd(event: Event) {
  const video = event.currentTarget as HTMLVideoElement | null;
  if (!video || !Number.isFinite(video.duration) || video.duration <= 0) return;
  try {
    video.currentTime = Math.max(0, video.duration - 0.08);
  } catch {
    // Some browsers defer seeking until enough metadata has loaded.
  }
}

function resetVideoPlayback(event: Event) {
  const video = event.currentTarget as HTMLVideoElement | null;
  if (!video || !Number.isFinite(video.duration)) return;
  if (video.currentTime >= Math.max(0, video.duration - 0.12)) {
    video.currentTime = 0;
  }
}

function formatDurationMinutes(value: unknown) {
  const minutes = numeric(value);
  if (minutes === null || minutes < 0) return "";
  const rounded = Math.round(minutes);
  const hours = Math.floor(rounded / 60);
  const rest = rounded % 60;
  if (locale.value === "zh-CN") {
    if (hours > 0 && rest > 0) return `${hours}小时 ${rest}分钟`;
    if (hours > 0) return `${hours}小时`;
    return `${rest}分钟`;
  }
  if (hours > 0 && rest > 0) return `${hours}h ${rest}m`;
  if (hours > 0) return `${hours}h`;
  return `${rest}m`;
}

function formatDurationSeconds(value: unknown) {
  const seconds = numeric(value);
  if (seconds === null) return "--";
  const rounded = Math.max(0, Math.round(seconds));
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  if (locale.value === "zh-CN") {
    if (hours) return `${hours}小时 ${minutes}分钟`;
    return `${minutes}分钟`;
  }
  if (hours) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function printLogTone(statusValue: string) {
  if (statusValue === "succeeded") return "good";
  if (statusValue === "failed") return "bad";
  if (statusValue === "cancelled" || statusValue === "paused") return "warn";
  return "muted";
}

function maintenanceTone(statusValue: string) {
  if (statusValue === "due") return "bad";
  if (statusValue === "soon") return "warn";
  if (statusValue === "disabled") return "muted";
  return "good";
}

function maintenanceProgress(item: PrinterMaintenance) {
  const interval = numeric(item.interval) || 1;
  const used = numeric(item.hours_since_last) || 0;
  return Math.max(0, Math.min(100, Math.round((used / interval) * 100)));
}

function maintenanceRemainingLabel(item: PrinterMaintenance) {
  const value = numeric(item.hours_until_due);
  if (value === null) return "--";
  if (value < 0) return t("maintenance.overdueBy", { hours: Math.abs(Math.round(value)) });
  return t("maintenance.remainingHours", { hours: Math.round(value) });
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
  return softCell(slot.tray_id);
}

function activeSlotDisplayLabel(slot: Record<string, any> | null | undefined) {
  if (!slot) return "--";
  return `AMS #${softCell(slot.ams_id)} / ${slotDisplayLabel(slot)}`;
}

function dashboardActiveAmsSlot(slots: Record<string, any>[], status: Record<string, any>) {
  const marked = slots.find((slot) => slot.is_active);
  if (marked) return marked;
  const trayNow = numeric(status.tray_now);
  if (trayNow === null || trayNow < 0 || trayNow >= 255) return undefined;
  return slots.find((slot) => {
    const globalTray = numeric(slot.global_tray_id);
    const tray = numeric(slot.tray_id);
    return globalTray === trayNow || tray === trayNow;
  });
}

function dashboardAmsActiveSlotLabel(slot: Record<string, any> | null | undefined, status: Record<string, any>) {
  if (slot) return activeSlotDisplayLabel(slot);
  const trayNow = numeric(status.tray_now);
  if (trayNow !== null && trayNow >= 0 && trayNow < 255) return `${t("table.tray")} ${Math.round(trayNow) + 1}`;
  return "--";
}

function dashboardActiveMaterialLabel(slot: Record<string, any> | null | undefined) {
  if (!slot) return "--";
  const parts = [slot.material || slot.tray_type, slot.series || slot.tray_sub_brands].filter(Boolean).map(String);
  const remain = numeric(slot.remain);
  if (remain !== null && remain >= 0) parts.push(`${Math.round(remain)}%`);
  return parts.length ? parts.join(" · ") : "--";
}

function dashboardAmsStatusLabel(status: Record<string, any>) {
  const main = status.ams_status_main_name ?? status.ams_status_main;
  const sub = status.ams_status_sub_name ?? status.ams_status_sub;
  const labels = [main, sub]
    .filter((item) => item !== null && item !== undefined && item !== "")
    .map((item) => displayCell(item));
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

function amsHumidity(unit: Record<string, any>) {
  return unit.humidity_raw ?? unit.humidity;
}

function amsHumidityLabel(unit: Record<string, any>) {
  const text = softCell(amsHumidity(unit));
  return text === "--" ? "--" : `${text}%`;
}

function dashboardAmsUnitVisual(unit: Record<string, any>, slots: Record<string, any>[], index: number) {
  const unitSlots = slots
    .filter((slot) => String(slot.ams_id) === String(unit.ams_id))
    .sort((left, right) => dashboardAmsSlotSortValue(left) - dashboardAmsSlotSortValue(right));
  return {
    key: String(unit.ams_id),
    title: amsTitle(unit),
    code: `#${unit.ams_id}`,
    meta: dashboardAmsUnitMeta(unit),
    slots: unitSlots.map((slot, slotIndex) => ({
      key: slotKey(slot),
      label: dashboardAmsSlotShortLabel(slot, unit, index, slotIndex),
      material: dashboardAmsSlotMaterial(slot),
      remain: dashboardAmsSlotRemain(slot),
      active: slot.is_active === true,
      loaded: isDashboardAmsLoaded(slot),
      style: { "--filament-color": filamentColor(slot.color || slot.tray_color) },
    })),
  };
}

function amsPageUnitVisual(unit: Record<string, any>, index: number) {
  return dashboardAmsUnitVisual(unit, arrayOfRecord(unit.slots), index);
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
  return softCell(slot.material || slot.tray_type);
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
    unit.dry_status_name || unit.dry_status ? `${t("ams.dryStatus")} ${displayCell(unit.dry_status_name || unit.dry_status)}` : "",
  ].filter(Boolean).map(String);
  return parts.length ? parts.join(" · ") : "--";
}

function dashboardAmsEnvironmentLabel(unit: Record<string, any>) {
  const parts = [];
  const temperature = numeric(unit.temperature);
  const humidity = amsHumidity(unit);
  if (temperature !== null) parts.push(`${Math.round(temperature)}°C`);
  if (humidity !== null && humidity !== undefined && humidity !== "") parts.push(`${softCell(humidity)}%`);
  return parts.join(" / ");
}

function remainPercent(value: unknown) {
  const parsed = numeric(value);
  if (parsed === null || parsed < 0) return 0;
  return percent(parsed);
}

function remainLabel(value: unknown) {
  const parsed = numeric(value);
  if (parsed === null || parsed < 0) return "--";
  return `${Math.round(parsed)}%`;
}

function unitLabel(value: unknown) {
  if (value === null || value === undefined || value === "") return "";
  return formatUnit(value);
}

function splitCsv(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function inputValue(event: Event) {
  return event.target instanceof HTMLInputElement ? event.target.value : "";
}

function checkboxChecked(event: Event) {
  return event.target instanceof HTMLInputElement ? event.target.checked : false;
}

function percentageLabel(value: unknown) {
  const parsed = numeric(value);
  if (parsed === null) return "--";
  return `${Math.round(parsed * 100)}%`;
}

function toggleExportSection(key: string, enabled: boolean) {
  if (enabled && !exportOptions.sections.includes(key)) exportOptions.sections.push(key);
  if (!enabled) exportOptions.sections = exportOptions.sections.filter((item) => item !== key);
}

function dashboardTaskTitle() {
  const terminalLog = dashboardTerminalLog();
  if (terminalLog) return formatCell(terminalLog.print_name || terminalLog.gcode_file || t("dashboard.noActiveTask"));
  if (!dashboardHasActiveTask()) return t("dashboard.noActiveTask");
  const printStatus = record(snapshot.value.print_status);
  return formatCell(state.value.subtask_name || printStatus.subtask_name || state.value.gcode_file || printStatus.gcode_file || t("dashboard.noActiveTask"));
}

function dashboardProgress() {
  const terminalLog = dashboardTerminalLog();
  const userState = dashboardUserStateValue();
  if (terminalLog?.status === "succeeded" || userState === "finished") return 100;
  if (!dashboardHasActiveTask()) return 0;
  const printStatus = record(snapshot.value.print_status);
  return Math.round(percent(printStatus.mc_percent ?? state.value.mc_percent));
}

function dashboardPrintStateLabel() {
  const terminalLog = dashboardTerminalLog();
  if (terminalLog?.status === "succeeded") return t("values.finished");
  if (terminalLog?.status === "failed") return t("values.failed_or_cancelled");
  if (terminalLog?.status === "cancelled") return t("values.cancelled");
  return displayCell(dashboardUserStateValue());
}

function dashboardPrintStageLabel() {
  if (!dashboardHasActiveTask()) return dashboardPrintStateLabel();
  const printStatus = record(snapshot.value.print_status);
  return displayCell(printStatus.stg_cur_name || printStatus.sub_stage_name || printStatus.stage_name);
}

function dashboardRemainingTimeMetric() {
  if (!dashboardHasActiveTask()) return "--";
  return remainingTimeLabel.value || formatCell(state.value.mc_remaining_time);
}

function dashboardUserStateValue() {
  return derived.value.user_state || record(snapshot.value.print_status).user_state || state.value.gcode_state;
}

function dashboardHasActiveTask() {
  if (dashboardTerminalLog()) return false;
  const userState = String(dashboardUserStateValue() || "").toUpperCase();
  if (isTerminalPrintState(userState)) return false;
  if (derived.value.preparing === true || derived.value.actual_printing === true || derived.value.paused === true) return true;
  return ["RUNNING", "PREPARE", "SLICING", "PAUSE", "PAUSED"].includes(userState);
}

function dashboardTerminalLog() {
  const printStatus = record(snapshot.value.print_status);
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
  const deviceSnapshot = record(value?.device_snapshot);
  const rawRefs = record(deviceSnapshot.raw_refs);
  return String(rawRefs.push_status_raw_id || rawRefs.push_status_received_at || deviceSnapshot.updated_at || record(value?.state).updated_at || "");
}

async function waitForDashboardRefresh(previousMarker: string) {
  for (let attempt = 0; attempt < 12; attempt += 1) {
    await delay(700);
    const next = await fetchDashboard();
    if (!next) return false;
    dashboard.value = next;
    if (dashboardRefreshMarker(next) && dashboardRefreshMarker(next) !== previousMarker) return true;
  }
  return false;
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function eventTypeLabel(item: UnifiedEvent | Record<string, any>) {
  const type = String(item.type || item.event_type || "");
  const directKey = `eventTypes.${type}`;
  const direct = t(directKey);
  if (direct !== directKey) return direct;
  if (type.startsWith("printer.command.")) {
    const command = record(item.data).command || type.replace("printer.command.", "");
    return `${t("events.printerCommand")} · ${displayCell(command)}`;
  }
  return type;
}

function eventMessage(item: UnifiedEvent | Record<string, any>) {
  const data = record(item.data);
  if (data.command) {
    return t("events.commandReceived", { command: displayCell(data.command) });
  }
  if (String(item.type || item.event_type || "") === "spool.location_changed") {
    return t("events.spoolLocationUpdated");
  }
  return String(item.message || "");
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
  if (kind === "material") return `${softCell(sample.material)} / ${softCell(sample.color)}`;
  if (kind === "remain") return softCell(sample.remain);
  if (kind === "rfid") return softCell(sample.rfid_status);
  return `K ${softCell(sample.k)} / ${softCell(sample.cali_idx)}`;
}

function filamentColor(value: unknown) {
  const text = String(value || "").replace("#", "");
  return /^[0-9a-fA-F]{6,8}$/.test(text) ? `#${text.slice(0, 6)}` : "#d7dce2";
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">FM</div>
        <div>
          <div class="brand-name">{{ t("app.name") }}</div>
          <div class="brand-sub">{{ t("app.subtitle") }}</div>
        </div>
      </div>
      <nav class="nav-list">
        <div v-for="group in navGroups" :key="group.key" class="nav-group">
          <div class="nav-group-label">{{ t(group.labelKey) }}</div>
          <button
            v-for="item in navItemsByGroup(group.key)"
            :key="item.key"
            class="nav-item"
            :class="{ active: activeView === item.key }"
            type="button"
            @click="switchView(item.key)"
          >
            <component :is="item.icon" :size="18" />
            <span>{{ t(item.labelKey) }}</span>
          </button>
        </div>
      </nav>
      <div class="sidebar-footer">
        <div class="mini-label">{{ t("app.api") }}</div>
        <div class="mono">/api</div>
      </div>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div class="topbar-main">
          <h1>{{ navLabel(activeView) }}</h1>
        </div>
        <div class="topbar-actions">
          <AppSelect v-model="selectedPrinterId" class="printer-select" :options="printerSelectOptions" @change="handlePrinterSelectionChanged" />
          <AppSelect v-model="locale" class="language-select" :options="localeOptions" />
          <span class="status-pill" :class="printerStatusTone">
            <span class="dot"></span>
            {{ selectedPrinter ? displayCell(selectedPrinter.connection_status) : t("common.noPrinter") }}
          </span>
          <button class="icon-button" type="button" :title="t('common.refresh')" @click="refreshCurrentView">
            <RefreshCw :size="17" />
          </button>
        </div>
      </header>

      <div v-if="message" class="toast ok">{{ message }}</div>
      <div v-if="error" class="toast bad">{{ error }}</div>
      <div v-if="realtimeDisconnected" class="toast warn">{{ t("events.realtimeDisconnected") }}</div>

      <section v-if="activeView === 'overview'" class="view">
        <div class="toolbar filters overview-toolbar">
          <label class="search-field">
            <Search :size="16" />
            <input v-model="overviewControls.search" :placeholder="t('overview.search')" />
          </label>
          <AppSelect v-model="overviewControls.filter" :options="overviewFilterOptions" />
          <AppSelect v-model="overviewControls.sort" :options="overviewSortOptions" />
          <AppSelect v-model="overviewControls.density" :options="overviewDensityOptions" />
        </div>
        <div class="metric-grid overview-metrics">
          <div v-for="item in overviewStats" :key="item.label" class="metric-card">
            <div class="metric-label">{{ item.label }}</div>
            <div class="metric-value">{{ item.value }}</div>
            <div class="metric-foot">{{ item.foot }}</div>
          </div>
        </div>

        <section v-if="!overviewItems.length" class="panel empty-overview">
          <h3>{{ t("overview.noPrinters") }}</h3>
          <p>{{ t("overview.noPrintersHint") }}</p>
          <button class="primary" type="button" @click="switchView('printers')">
            <Settings :size="17" />
            {{ t("overview.configurePrinter") }}
          </button>
        </section>

        <div v-else class="fleet-grid" :class="`density-${overviewControls.density}`">
          <article
            v-for="item in overviewItems"
            :key="item.printer.id"
            class="fleet-card"
            :class="summaryTone(item)"
          >
            <div class="fleet-card-header">
              <div>
                <div class="fleet-name">{{ item.printer.name }}</div>
                <div class="fleet-host">{{ item.printer.host }}</div>
              </div>
              <span class="status-pill" :class="summaryTone(item)">
                <span class="dot"></span>
                {{ summaryStatusLabel(item) }}
              </span>
            </div>

            <div class="fleet-task">
              <div class="mini-label">{{ t("overview.currentTask") }}</div>
              <strong>{{ summaryTaskName(item) }}</strong>
              <span>{{ summaryStage(item) }}</span>
            </div>

            <div class="fleet-progress">
              <div>
                <span>{{ t("overview.progress") }}</span>
                <strong>{{ summaryProgress(item) }}%</strong>
              </div>
              <div class="progress-track">
                <span :style="{ width: `${summaryProgress(item)}%` }"></span>
              </div>
            </div>

            <div v-if="overviewControls.density !== 'compact'" class="fleet-metrics">
              <div>
                <span>{{ t("dashboard.nozzle") }}</span>
                <strong>{{ summaryTemperature(item, "nozzle") }}℃</strong>
              </div>
              <div>
                <span>{{ t("dashboard.bed") }}</span>
                <strong>{{ summaryTemperature(item, "bed") }}℃</strong>
              </div>
              <div>
                <span>WiFi</span>
                <strong>{{ summaryWifi(item) }}</strong>
              </div>
              <div>
                <span>{{ t("dashboard.dataCoverage") }}</span>
                <strong>{{ summaryCoveragePercent(item) }}%</strong>
              </div>
            </div>

            <div v-if="overviewControls.density === 'detailed'" class="fleet-detail-row">
              <span>{{ t("dashboard.layers") }} {{ summaryLayerFraction(item) }}</span>
              <span>HMS {{ summaryActiveHmsCount(item) }}</span>
              <span>{{ t("maintenance.due") }} {{ item.maintenance_due_count || 0 }}</span>
            </div>

            <div class="fleet-card-footer">
              <span>{{ t("overview.lastSync") }} {{ formatCell(item.printer.last_sync_at) }}</span>
              <div class="row-actions">
                <button class="secondary" type="button" @click="openPrinterDashboard(item.printer.id)">
                  <Gauge :size="17" />
                  {{ t("overview.openDashboard") }}
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section v-else-if="activeView === 'dashboard'" class="view">
        <div class="hero-strip">
          <div>
            <div class="mini-label">{{ t("dashboard.currentTask") }}</div>
            <h2>{{ dashboardTaskTitle() }}</h2>
            <div v-if="activeDerivedStatuses.length" class="task-status-chips">
              <span
                v-for="[key] in activeDerivedStatuses"
                :key="key"
                class="status-chip"
                :class="derivedStatusTone(key)"
              >
                {{ fieldLabel(key) }}
              </span>
            </div>
          </div>
          <div class="progress-block">
            <div class="progress-value">
              <span>{{ dashboardProgress() }}%</span>
              <div class="progress-meta">
                <small v-if="remainingTimeLabel">{{ t("dashboard.remainingTime") }} {{ remainingTimeLabel }}</small>
                <small v-if="layerFraction">{{ t("dashboard.layers") }} {{ layerFraction }}</small>
              </div>
            </div>
            <div class="progress-track">
              <span :style="{ width: `${dashboardProgress()}%` }"></span>
            </div>
          </div>
          <div v-if="!canRequestFullRefresh" class="strip-actions">
            <button class="secondary" type="button" @click="connectPrinter">
              <PlugZap :size="17" />
              {{ t("common.connectPrinter") }}
            </button>
          </div>
        </div>

        <div class="metric-grid">
          <div class="metric-card">
            <div class="metric-label">{{ t("dashboard.printState") }}</div>
            <div class="metric-value">{{ dashboardPrintStateLabel() }}</div>
            <div class="metric-foot">{{ dashboardPrintStageLabel() }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ t("dashboard.remainingTime") }}</div>
            <div class="metric-value compact-value">{{ dashboardRemainingTimeMetric() }}</div>
            <div class="metric-foot">{{ t("dashboard.minutes") }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ t("dashboard.nozzle") }}</div>
            <div class="metric-value">{{ formatCell(temperatures.nozzle) }}℃</div>
            <div class="metric-foot">{{ t("dashboard.target") }} {{ formatCell(temperatures.nozzle_target) }}℃</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ t("dashboard.bed") }}</div>
            <div class="metric-value">{{ formatCell(temperatures.bed) }}℃</div>
            <div class="metric-foot">{{ t("dashboard.target") }} {{ formatCell(temperatures.bed_target) }}℃</div>
          </div>
          <div v-if="shouldShowChamberTemperature" class="metric-card">
            <div class="metric-label">{{ fieldLabel("chamber") }}</div>
            <div class="metric-value">{{ formatCell(temperatures.chamber) }}℃</div>
            <div class="metric-foot">{{ t("dashboard.target") }} {{ formatCell(temperatures.chamber_target) }}℃</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">WiFi</div>
            <div class="metric-value">{{ formatCell(network.wifi_signal) }}</div>
            <div class="metric-foot">dBm</div>
          </div>
        </div>

        <div class="dashboard-card-flow">
          <section v-if="shouldShowDashboardCamera" class="panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.thermalFans") }}</h3>
              <div class="widget-tools">
                <Thermometer :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.thermal')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.thermal')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.thermal')" class="bar-list">
              <div class="bar-row">
                <span>{{ fieldLabel("nozzle") }}</span>
                <div class="bar"><i :style="{ width: `${temperaturePercent(temperatures.nozzle, temperatures.nozzle_target)}%` }"></i></div>
                <strong>{{ formatCell(temperatures.nozzle) }}℃</strong>
              </div>
              <div class="bar-row">
                <span>{{ fieldLabel("bed") }}</span>
                <div class="bar"><i :style="{ width: `${temperaturePercent(temperatures.bed, temperatures.bed_target)}%` }"></i></div>
                <strong>{{ formatCell(temperatures.bed) }}℃</strong>
              </div>
              <div v-for="[key, item] in fanRows" :key="key" class="bar-row">
                <span>{{ fieldLabel(key) }}</span>
                <div class="bar"><i :style="{ width: `${fanDisplayPercent(item)}%` }"></i></div>
                <strong>{{ formatCell(fanDisplayPercent(item)) }}%</strong>
              </div>
            </div>
          </section>

          <section v-if="shouldShowDashboardAms" class="panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.networkHardware") }}</h3>
              <div class="widget-tools">
                <Network :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.network')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.network')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.network')" class="network-info-grid">
              <div v-for="[key, value] in readableNetworkHardware" :key="key" class="network-info-item">
                <span>{{ fieldLabel(key) }}</span>
                <strong>{{ displayCell(value) }}</strong>
              </div>
              <div v-if="!readableNetworkHardware.length" class="empty">{{ t("common.empty") }}</div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.cameraStatus") }}</h3>
              <div class="widget-tools">
                <Camera :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.camera')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.camera')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.camera')" class="camera-info-grid">
              <div v-for="[key, value] in cameraStatusRows" :key="key" class="camera-info-item">
                <span>{{ fieldLabel(key) }}</span>
                <strong :class="statusTone(value)">{{ displayCell(value) }}</strong>
              </div>
              <div v-if="!cameraStatusRows.length" class="empty">{{ t("common.empty") }}</div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.detectionAndCoverage") }}</h3>
              <div class="widget-tools">
                <Eye :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.detectionCoverage')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.detectionCoverage')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.detectionCoverage')" class="combined-status-sections">
              <div>
                <div class="section-label">{{ t("dashboard.detectionCapabilities") }}</div>
                <div class="capability-grid">
                  <div v-for="[key, value] in detectionRows" :key="key" class="capability-row">
                    <span>{{ fieldLabel(key) }}</span>
                    <strong :class="statusTone(value)">{{ boolLabel(value) }}</strong>
                  </div>
                  <div v-if="!detectionRows.length" class="empty">{{ t("common.empty") }}</div>
                </div>
              </div>
              <div>
                <div class="section-label">{{ t("dashboard.dataCoverage") }}</div>
                <div class="coverage-list">
                  <div v-for="item in coverageStatusRows" :key="item.key" class="coverage-row">
                    <span>{{ fieldLabel(item.key) }}</span>
                    <strong :class="{ on: item.received, off: !item.received }">
                      {{ item.received ? t("common.received") : t("common.missing") }}
                    </strong>
                  </div>
                  <div v-if="!coverageStatusRows.length" class="empty">{{ t("common.empty") }}</div>
                </div>
              </div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.amsSummary") }}</h3>
              <div class="widget-tools">
                <Boxes :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.ams')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.ams')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.ams')" class="ams-status-grid">
              <div v-for="[label, value] in dashboardAmsSummaryRows" :key="label" class="ams-status-item">
                <span>{{ label }}</span>
                <strong>{{ displayCell(value) }}</strong>
              </div>
              <div v-if="!dashboardAmsSummaryRows.length" class="empty">{{ t("common.empty") }}</div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.ams')" class="ams-visual-list">
              <article v-for="unit in dashboardAmsUnitRows" :key="unit.key" class="ams-visual-unit">
                <div class="ams-visual-head">
                  <div>
                    <strong>{{ unit.title }}</strong>
                    <span>{{ unit.code }}</span>
                  </div>
                  <small>{{ unit.meta }}</small>
                </div>
                <div class="ams-visual-slots">
                  <div
                    v-for="slot in unit.slots"
                    :key="slot.key"
                    class="ams-visual-slot"
                    :class="{ active: slot.active, empty: !slot.loaded }"
                  >
                    <span class="ams-slot-material">{{ slot.material }}</span>
                    <div class="ams-spool" :style="slot.style"><i></i></div>
                    <strong>{{ slot.label }}</strong>
                    <small>{{ slot.remain }}</small>
                  </div>
                  <div v-if="!unit.slots.length" class="empty">{{ t("ams.noSlots") }}</div>
                </div>
              </article>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.hmsErrors") }}</h3>
              <div class="widget-tools">
                <ShieldAlert :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.hms')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.hms')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.hms')" class="table-wrap">
              <table>
                <thead>
                  <tr><th>{{ t("table.code") }}</th><th>{{ t("table.severity") }}</th><th>{{ t("table.module") }}</th><th>{{ t("table.current") }}</th><th>{{ t("table.description") }}</th></tr>
                </thead>
                <tbody>
                  <tr v-if="!hmsErrors.length"><td colspan="5" class="empty">{{ t("dashboard.noHmsErrors") }}</td></tr>
                  <tr v-for="item in hmsErrors" :key="`${item.short_code}-${item.active}`" @click="openHmsDetails(item)">
                    <td class="mono">{{ formatCell(item.short_code || item.code) }}</td>
                    <td>{{ displayCell(item.severity_name) }}</td>
                    <td>{{ formatCell(item.module_name) }}</td>
                    <td>{{ item.active ? t("common.unresolved") : t("common.resolved") }}</td>
                    <td>{{ hmsMessage(item) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </section>

      <section v-else-if="activeView === 'events'" class="view">
        <div class="toolbar filters">
          <input v-model="eventFilters.type" :placeholder="t('events.typeFilter')" />
          <AppSelect v-model="eventFilters.severity" :options="eventSeverityOptions" />
          <AppSelect v-model="eventFilters.active" :options="eventActiveOptions" />
        </div>
        <section class="panel">
          <div class="panel-header"><h3>{{ t("events.title") }}</h3><Bell :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>{{ t("table.time") }}</th><th>{{ t("table.type") }}</th><th>{{ t("table.severity") }}</th><th>{{ t("table.current") }}</th><th>{{ t("table.message") }}</th></tr></thead>
              <tbody>
                <tr v-if="!filteredEvents.length"><td colspan="5" class="empty">{{ t("common.empty") }}</td></tr>
                <tr v-for="item in filteredEvents" :key="`${item.source}-${item.id}`">
                  <td>{{ formatCell(item.created_at) }}</td>
                  <td>{{ eventTypeLabel(item) }}</td>
                  <td><span class="status-pill" :class="eventTone(item)"><span class="dot"></span>{{ displayCell(item.severity) }}</span></td>
                  <td>{{ item.active === null || item.active === undefined ? "--" : item.active ? t("common.unresolved") : t("common.resolved") }}</td>
                  <td>{{ eventMessage(item) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </section>

      <section v-else-if="activeView === 'printLog'" class="view">
        <div class="toolbar filters">
          <AppSelect v-model="printLogFilters.printer_id" :options="printLogPrinterOptions" />
          <AppSelect v-model="printLogFilters.status" :options="printLogStatusOptions" />
          <input v-model="printLogFilters.search" :placeholder="t('printLog.search')" />
          <input v-model="printLogFilters.date_from" type="date" />
          <input v-model="printLogFilters.date_to" type="date" />
          <button class="primary" type="button" @click="applyPrintLogFilters">
            <Search :size="17" />
            {{ t("printLog.applyFilters") }}
          </button>
        </div>

        <div class="metric-grid overview-metrics">
          <div class="metric-card">
            <div class="metric-label">{{ t("printLog.total") }}</div>
            <div class="metric-value">{{ printLogSummary?.total || 0 }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ t("values.succeeded") }}</div>
            <div class="metric-value">{{ printLogSummary?.succeeded || 0 }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ t("values.failed") }}</div>
            <div class="metric-value">{{ printLogSummary?.failed || 0 }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ t("printLog.totalDuration") }}</div>
            <div class="metric-value compact-value">{{ formatDurationSeconds(printLogSummary?.total_duration_seconds) }}</div>
          </div>
        </div>

        <div class="grid two wide">
          <section class="panel">
            <div class="panel-header"><h3>{{ t("printLog.analytics") }}</h3><LineChart :size="18" /></div>
            <div class="analytics-strip">
              <div><span>{{ t("printLog.successRate") }}</span><strong>{{ percentageLabel(printLogAnalytics?.success_rate) }}</strong></div>
              <div><span>{{ t("printLog.failureRate") }}</span><strong>{{ percentageLabel(printLogAnalytics?.failure_rate) }}</strong></div>
              <div><span>{{ t("printLog.averageDuration") }}</span><strong>{{ formatDurationSeconds(printLogAnalytics?.average_duration_seconds) }}</strong></div>
              <div><span>{{ t("printLog.longestDuration") }}</span><strong>{{ formatDurationSeconds(printLogAnalytics?.longest_duration_seconds) }}</strong></div>
            </div>
            <div class="trend-bars">
              <div v-for="bucket in printLogAnalytics?.by_date || []" :key="bucket.bucket" class="trend-row">
                <span>{{ bucket.bucket }}</span>
                <div class="bar"><i :style="{ width: `${percent(bucket.total, 0)}%` }"></i></div>
                <strong>{{ bucket.total }}</strong>
              </div>
              <div v-if="!printLogAnalytics?.by_date?.length" class="empty">{{ t("common.empty") }}</div>
            </div>
          </section>
          <section class="panel">
            <div class="panel-header"><h3>{{ t("printLog.failureRanking") }}</h3><ShieldAlert :size="18" /></div>
            <div class="table-wrap compact-table">
              <table>
                <thead><tr><th>{{ t("printLog.failureReason") }}</th><th>{{ t("table.value") }}</th></tr></thead>
                <tbody>
                  <tr v-if="!printLogAnalytics?.by_failure_reason?.length"><td colspan="2" class="empty">{{ t("common.empty") }}</td></tr>
                  <tr v-for="item in printLogAnalytics?.by_failure_reason || []" :key="item.reason">
                    <td>{{ item.reason }}</td>
                    <td>{{ item.count }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <section class="panel">
          <div class="panel-header">
            <h3>{{ t("nav.printLog") }}</h3>
            <ClipboardList :size="18" />
          </div>
          <div class="table-wrap tall-table">
            <table>
              <thead><tr><th>{{ t("table.name") }}</th><th>{{ t("table.printer") }}</th><th>{{ t("table.status") }}</th><th>{{ t("printLog.startedAt") }}</th><th>{{ t("printLog.duration") }}</th><th>{{ t("overview.progress") }}</th><th>{{ t("dashboard.layers") }}</th><th>{{ t("printLog.failureReason") }}</th></tr></thead>
              <tbody>
                <tr v-if="!printLogs.length"><td colspan="8" class="empty">{{ t("common.empty") }}</td></tr>
                <tr v-for="log in printLogs" :key="log.id">
                  <td>{{ formatCell(log.print_name || log.gcode_file) }}</td>
                  <td>{{ formatCell(log.printer_name_snapshot || log.printer_id) }}</td>
                  <td><span class="status-pill" :class="printLogTone(log.status)"><span class="dot"></span>{{ displayCell(log.status) }}</span></td>
                  <td>{{ formatCell(log.started_at) }}</td>
                  <td>{{ formatDurationSeconds(log.duration_seconds) }}</td>
                  <td>{{ formatCell(log.max_progress ?? log.final_progress) }}%</td>
                  <td>{{ softCell(log.layer_current) }} / {{ softCell(log.layer_total) }}</td>
                  <td>{{ softCell(log.failure_reason) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="pager">
            <button class="secondary" type="button" :disabled="printLogFilters.offset <= 0" @click="changePrintLogPage(-1)">{{ t("printLog.prev") }}</button>
            <span>{{ printLogPage }} / {{ printLogTotalPages }} · {{ printLogTotal }}</span>
            <button class="secondary" type="button" :disabled="printLogPage >= printLogTotalPages" @click="changePrintLogPage(1)">{{ t("printLog.next") }}</button>
          </div>
        </section>
      </section>

      <section v-else-if="activeView === 'metrics'" class="view">
        <div class="toolbar filters">
          <AppSelect v-model="metricRange" :options="metricRangeOptions" @change="withLoading(loadMetrics)" />
        </div>
        <div class="metrics-chart-grid">
          <MetricChart
            :title="t('metrics.temperatureHistory')"
            :subtitle="t('metrics.temperatureSubtitle')"
            :items="metricGroups.temperatures"
            :metric-label="metricLabel"
            :empty-label="t('common.empty')"
            :tooltip-labels="metricTooltipLabels"
          />
          <MetricChart
            :title="t('metrics.fanHistory')"
            :subtitle="t('metrics.fanSubtitle')"
            :items="metricGroups.fans"
            :metric-label="metricLabel"
            :empty-label="t('common.empty')"
            :tooltip-labels="metricTooltipLabels"
          />
          <MetricChart
            :title="t('metrics.wifiHistory')"
            :subtitle="t('metrics.wifiSubtitle')"
            :items="metricGroups.wifi"
            :metric-label="metricLabel"
            :empty-label="t('common.empty')"
            :tooltip-labels="metricTooltipLabels"
          />
          <MetricChart
            :title="t('metrics.amsHistory')"
            :subtitle="t('metrics.amsSubtitle')"
            :items="metricGroups.ams"
            :metric-label="metricLabel"
            :empty-label="t('common.empty')"
            :tooltip-labels="metricTooltipLabels"
          />
        </div>
      </section>

      <section v-else-if="activeView === 'storage'" class="view">
        <div class="toolbar storage-toolbar">
          <div class="toolbar filters storage-filters">
            <label class="search-field">
              <Search :size="16" />
              <input v-model="storageSearch" :placeholder="t('storage.search')" />
            </label>
            <AppSelect v-model="storageSort" :options="storageSortOptions" />
          </div>
        </div>
        <div class="metric-grid small">
          <div v-for="item in storageStats" :key="item.label" class="metric-card">
            <div class="metric-label">{{ item.label }}</div>
            <div class="metric-value">{{ item.value }}</div>
            <div v-if="item.foot" class="metric-foot">{{ item.foot }}</div>
          </div>
        </div>
        <section class="panel">
          <div class="panel-header">
            <div>
              <h3>{{ t("storage.preview") }}</h3>
              <p class="panel-subtitle">{{ t("storage.previewSubtitle", { count: filteredTimelapseFiles.length }) }}</p>
            </div>
            <Camera :size="18" />
          </div>
          <div v-if="storageResult?.error" class="inline-error">{{ storageResult.error }}</div>
          <div class="storage-preview-grid">
            <article v-for="file in storagePreviewFiles" :key="file.path" class="storage-preview-card">
              <video
                :src="storageFileUrl(file, true)"
                muted
                controls
                preload="metadata"
                playsinline
                @loadedmetadata="seekVideoPreviewToEnd"
                @play="resetVideoPlayback"
              ></video>
              <div class="storage-preview-meta">
                <div class="storage-title-row">
                  <strong>{{ file.name }}</strong>
                  <button class="icon-button compact" type="button" :title="t('storage.favorite')" @click="toggleTimelapseFavorite(file)">
                    <Star :size="15" :fill="timelapseNote(file)?.favorite ? 'currentColor' : 'none'" />
                  </button>
                </div>
                <span>{{ formatBytes(file.size || 0) }} · {{ formatCell(file.modified_at) }}</span>
                <span>{{ t("fields.resolution") }} {{ softCell(timelapseNote(file)?.cached_metadata?.resolution) }} · {{ t("storage.coverCache") }} {{ softCell(timelapseNote(file)?.cached_metadata?.cover_cache) }}</span>
              </div>
              <div class="timelapse-note-row">
                <input
                  :value="timelapseNoteText(file)"
                  :placeholder="t('storage.note')"
                  @input="setTimelapseDraft(file.path, inputValue($event))"
                />
                <button class="secondary" type="button" @click="saveTimelapseNote(file)">{{ t("common.save") }}</button>
              </div>
              <a class="secondary storage-download-link" :href="storageFileUrl(file)" :download="file.name">
                <Download :size="15" />
                {{ t("storage.download") }}
              </a>
            </article>
            <div v-if="!storagePreviewFiles.length" class="empty">{{ t("storage.noPreview") }}</div>
          </div>
          <div v-if="filteredTimelapseFiles.length" class="pager">
            <button class="secondary" type="button" :disabled="storagePage <= 1" @click="changeStoragePage(-1)">{{ t("printLog.prev") }}</button>
            <span>{{ t("storage.pageInfo", { page: storagePage, total: storageTotalPages, count: filteredTimelapseFiles.length }) }}</span>
            <button class="secondary" type="button" :disabled="storagePage >= storageTotalPages" @click="changeStoragePage(1)">{{ t("printLog.next") }}</button>
          </div>
        </section>
        <section class="panel">
          <div class="panel-header"><h3>{{ t("storage.groupByDate") }}</h3><Camera :size="18" /></div>
          <div class="date-group-list">
            <div v-for="group in groupedTimelapseFiles" :key="group.date" class="date-group-row">
              <strong>{{ group.date }}</strong>
              <span>{{ group.files.length }}</span>
            </div>
            <div v-if="!groupedTimelapseFiles.length" class="empty">{{ t("common.empty") }}</div>
          </div>
        </section>
      </section>

      <section v-else-if="activeView === 'ams'" class="view">
        <div class="toolbar">
          <AppSelect v-model="amsSensorRange" :options="amsSensorRangeOptions" @change="withLoading(loadAmsSensorHistories)" />
        </div>
        <div class="metric-grid overview-metrics">
          <div v-for="item in amsStats" :key="item.label" class="metric-card">
            <div class="metric-label">{{ item.label }}</div>
            <div class="metric-value">{{ item.value }}</div>
          </div>
        </div>
        <div class="ams-unit-grid">
        <section
          v-for="(unit, unitIndex) in amsOverview?.units || []"
          :key="unit.ams_id"
          class="panel ams-unit-card"
          :class="[amsTone(unit), { collapsed: isSectionCollapsed(amsSectionKey(unit)) }]"
        >
          <div class="ams-unit-header" :class="{ collapsed: isSectionCollapsed(amsSectionKey(unit)) }">
            <div class="ams-unit-title">
              <div class="badge-row">
                <span class="ams-badge">{{ unit.ams_type_name === "unknown" ? t("ams.unknownType") : unit.ams_type_name }}</span>
                <span class="ams-code mono">#{{ unit.ams_id }}</span>
              </div>
              <h3>{{ amsTitle(unit) }}</h3>
            </div>
            <div class="ams-unit-actions">
              <span v-if="isSectionCollapsed(amsSectionKey(unit))" class="ams-compact-sensor">{{ softCell(unit.temperature) }}℃ / {{ amsHumidityLabel(unit) }}</span>
              <button
                v-if="!isSectionCollapsed(amsSectionKey(unit))"
                class="icon-button compact subtle"
                type="button"
                :title="t('ams.editLabel')"
                @click="toggleAmsLabelEditor(unit)"
              >
                <PencilLine :size="14" />
              </button>
              <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed(amsSectionKey(unit))">
                <ChevronDown v-if="isSectionCollapsed(amsSectionKey(unit))" :size="15" />
                <ChevronUp v-else :size="15" />
              </button>
            </div>
            <div v-if="amsLabelEditing[unit.ams_id] && !isSectionCollapsed(amsSectionKey(unit))" class="ams-label-row">
              <input v-model="amsLabelDrafts[unit.ams_id]" :placeholder="t('ams.labelPlaceholder')" />
              <button class="secondary" type="button" @click="saveAmsLabel(unit)"><Save :size="15" />{{ t("common.save") }}</button>
              <button class="icon-button compact" type="button" :title="t('ams.clearLabel')" @click="clearAmsLabel(unit)"><X :size="15" /></button>
            </div>
            <div v-if="!isSectionCollapsed(amsSectionKey(unit))" class="ams-unit-meta">
              <span>{{ t("fields.temperature") }} {{ softCell(unit.temperature) }}℃</span>
              <span>{{ t("fields.humidity_raw") }} {{ amsHumidityLabel(unit) }}</span>
              <span>{{ t("ams.activeSlot") }} {{ activeSlotDisplayLabel(unit.active_slot) }}</span>
              <span>{{ t("ams.dryStatus") }} {{ displayCell(unit.dry_status_name || unit.dry_status) }}</span>
              <span class="quiet-meta">{{ t("fields.firmware") }} {{ softCell(unit.sw_ver) }}</span>
              <span>{{ t("overview.lastSync") }} {{ formatCell(unit.updated_at) }}</span>
            </div>
          </div>
          <div class="ams-fold-stack">
            <Transition name="ams-fold">
              <div v-if="isSectionCollapsed(amsSectionKey(unit))" :key="`${unit.ams_id}-collapsed`" class="ams-fold-region">
                <div class="ams-collapsed-preview">
                  <div
                    class="ams-visual-slots ams-page-preview-slots"
                    :class="{ 'single-slot': amsPageUnitVisual(unit, unitIndex).slots.length <= 1 }"
                  >
                    <div
                      v-for="slot in amsPageUnitVisual(unit, unitIndex).slots"
                      :key="slot.key"
                      class="ams-visual-slot"
                      :class="{ active: slot.active, empty: !slot.loaded }"
                    >
                      <span class="ams-slot-material">{{ slot.material }}</span>
                      <div class="ams-spool" :style="slot.style"><i></i></div>
                      <strong>{{ slot.label }}</strong>
                      <small>{{ slot.remain }}</small>
                    </div>
                    <div v-if="!amsPageUnitVisual(unit, unitIndex).slots.length" class="empty">{{ t("ams.noSlots") }}</div>
                  </div>
                </div>
              </div>
              <div v-else :key="`${unit.ams_id}-expanded`" class="ams-fold-region">
                <div class="ams-sensor-row">
                  <MetricChart
                    :title="t('ams.sensorHistory')"
                    :subtitle="`${t('fields.temperature')} / ${t('fields.humidity_raw')}`"
                    :items="amsSensorChartItems(unit.ams_id)"
                    :metric-label="metricLabel"
                    :empty-label="t('common.empty')"
                    :tooltip-labels="metricTooltipLabels"
                  />
                </div>
                <div class="ams-slot-grid">
                  <div v-if="!unit.slots.length" class="empty">{{ t("ams.noSlots") }}</div>
                  <article v-for="slot in unit.slots" :key="slotKey(slot)" class="ams-slot-card" :class="{ active: slot.is_active }">
                    <div class="ams-slot-topline">
                      <div>
                        <span class="mini-label">{{ slotDisplayLabel(slot) }}</span>
                        <strong><span class="swatch" :style="{ background: filamentColor(slot.color) }"></span>{{ softCell(slot.material) }}</strong>
                      </div>
                      <button class="icon-button compact" type="button" :title="t('table.details')" @click="openSlotDetails(slot)">
                        <Eye :size="15" />
                      </button>
                    </div>
                    <div class="ams-slot-remain">
                      <div class="progress-track">
                        <span :style="{ width: `${remainPercent(slot.remain)}%` }"></span>
                      </div>
                      <strong>{{ remainLabel(slot.remain) }}</strong>
                    </div>
                    <div class="ams-slot-facts">
                      <div><span>{{ t("table.state") }}</span><strong>{{ displayCell(slot.state_name || slot.slot_state) }}</strong></div>
                      <div><span>K</span><strong>{{ softCell(slot.k) }}</strong></div>
                      <div><span>{{ t("ams.caliIdx") }}</span><strong>{{ softCell(slot.cali_idx) }}</strong></div>
                      <div><span>{{ t("table.spool") }}</span><strong>{{ softCell(slot.spool_id) }}</strong></div>
                    </div>
                    <span v-if="slot.is_active" class="ams-active-ribbon">{{ t("common.currentInUse") }}</span>
                  </article>
                </div>
              </div>
            </Transition>
          </div>
        </section>
        </div>
      </section>

      <section v-else-if="activeView === 'inventory'" class="view">
        <section v-if="isSectionVisible('inventory.spools')" class="panel">
          <div class="panel-header">
            <h3>{{ t("inventory.spools") }}</h3>
            <div class="widget-tools">
              <Archive :size="18" />
              <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('inventory.spools')">
                <ChevronDown v-if="isSectionCollapsed('inventory.spools')" :size="15" />
                <ChevronUp v-else :size="15" />
              </button>
              <button class="icon-button compact" type="button" :title="t('layout.hide')" @click="toggleSectionHidden('inventory.spools')"><X :size="15" /></button>
            </div>
          </div>
          <div v-show="!isSectionCollapsed('inventory.spools')" class="form-grid compact-form">
            <input v-model="spoolForm.display_name" :placeholder="t('form.name')" />
            <input v-model="spoolForm.material" :placeholder="t('form.material')" />
            <input v-model="spoolForm.series" :placeholder="t('form.series')" />
            <input v-model="spoolForm.color" :placeholder="t('form.color')" />
            <input v-model.number="spoolForm.sealed_quantity" type="number" min="0" :placeholder="t('form.sealedQty')" />
            <AppSelect v-model="spoolForm.status" :options="spoolStatusOptions" />
            <button class="primary" type="button" @click="createSpool"><Save :size="17" />{{ t("common.create") }}</button>
          </div>
          <div v-show="!isSectionCollapsed('inventory.spools')" class="bind-row">
            <input v-model="bindForm.slot_id" :placeholder="t('form.slotId')" />
            <input v-model="bindForm.spool_id" :placeholder="t('form.spoolId')" />
            <button class="secondary" type="button" @click="bindSlot"><Wrench :size="17" />{{ t("common.bind") }}</button>
          </div>
          <div v-show="!isSectionCollapsed('inventory.spools')" class="table-wrap">
            <table>
              <thead><tr><th>{{ t("table.id") }}</th><th>{{ t("table.name") }}</th><th>{{ t("table.material") }}</th><th>{{ t("table.status") }}</th><th>{{ t("table.location") }}</th></tr></thead>
              <tbody>
                <tr v-if="!spools.length"><td colspan="5" class="empty">{{ t("inventory.noSpools") }}</td></tr>
                <tr v-for="spool in spools" :key="spool.id">
                  <td>{{ spool.id }}</td>
                  <td>{{ spool.display_name }}</td>
                  <td>{{ formatCell(spool.material) }}</td>
                  <td>{{ displayCell(spool.status) }}</td>
                  <td>{{ formatCell(spool.current_ams_id) }} / {{ formatCell(spool.current_tray_id) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </section>

      <section v-else-if="activeView === 'maintenance'" class="view">
        <section class="maintenance-hero">
          <div>
            <div class="mini-label">{{ t("maintenance.titleKicker") }}</div>
            <h2>{{ selectedPrinter ? selectedPrinter.name : t("nav.maintenance") }}</h2>
            <p>{{ t("maintenance.subtitle") }}</p>
          </div>
          <div class="maintenance-hero-stats">
            <div>
              <span>{{ t("maintenance.currentHours") }}</span>
              <strong>{{ selectedPrinterPrintHours }}h</strong>
            </div>
            <div>
              <span>{{ t("maintenance.health") }}</span>
              <strong>{{ maintenanceHealthPercent }}%</strong>
            </div>
          </div>
        </section>

        <div class="maintenance-summary-grid">
          <div v-for="item in maintenanceStats" :key="item.label" class="maintenance-summary-card" :class="item.tone">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
          <div class="maintenance-summary-card neutral">
            <span>{{ t("maintenance.totalItems") }}</span>
            <strong>{{ maintenanceOverview?.total_items || 0 }}</strong>
          </div>
        </div>

        <div class="maintenance-layout">
          <section class="panel maintenance-fleet-panel">
            <div class="panel-header">
              <h3>{{ t("maintenance.fleet") }}</h3>
              <Wrench :size="18" />
            </div>
            <div class="maintenance-printer-list">
              <button
                v-for="printer in maintenanceOverview?.printers || []"
                :key="printer.printer_id"
                type="button"
                class="maintenance-printer-row"
                :class="{ selected: printer.printer_id === selectedPrinterId }"
                @click="selectedPrinterId = Number(printer.printer_id); loadMaintenance()"
              >
                <span>{{ printer.printer_name }}</span>
                <strong>{{ printer.due_count }} / {{ printer.soon_count }} / {{ printer.ok_count }}</strong>
              </button>
              <div v-if="!maintenanceOverview?.printers?.length" class="empty">{{ t("common.empty") }}</div>
            </div>
          </section>

          <section class="panel maintenance-worklist-panel">
            <div class="panel-header">
              <div>
                <h3>{{ t("maintenance.worklist") }}</h3>
                <p class="panel-subtitle">{{ t("maintenance.worklistSubtitle") }}</p>
              </div>
              <span class="status-pill" :class="maintenanceOverview?.due_count ? 'bad' : maintenanceOverview?.soon_count ? 'warn' : 'good'">
                <span class="dot"></span>
                {{ maintenanceOverview?.due_count ? t("maintenance.due") : maintenanceOverview?.soon_count ? t("maintenance.soon") : t("maintenance.ok") }}
              </span>
            </div>

            <div v-if="!maintenanceItems.length" class="maintenance-empty">
              <Wrench :size="24" />
              <strong>{{ t("common.empty") }}</strong>
            </div>

            <div v-else class="maintenance-group-list">
              <section v-for="group in maintenanceStatusGroups" :key="group.key" class="maintenance-group">
                <div class="maintenance-group-header">
                  <span class="status-pill" :class="group.tone"><span class="dot"></span>{{ group.label }}</span>
                  <small>{{ group.items.length }}</small>
                </div>

                <article
                  v-for="item in group.items"
                  :key="item.id"
                  class="maintenance-card"
                  :class="maintenanceTone(item.due_status)"
                >
                  <div class="maintenance-card-main">
                    <div class="maintenance-title-row">
                      <div class="maintenance-icon" :class="{ ams: item.target_type === 'ams' }">
                        <Boxes v-if="item.target_type === 'ams'" :size="16" />
                        <Wrench v-else :size="16" />
                      </div>
                      <div>
                        <h4>{{ item.maintenance_type.name }}</h4>
                        <div v-if="item.target_label" class="maintenance-target">{{ item.target_label }}</div>
                        <p>{{ item.maintenance_type.description }}</p>
                      </div>
                    </div>

                    <div class="maintenance-progress-row">
                      <div class="maintenance-progress-label">
                        <span>{{ t("maintenance.sinceLast") }} {{ item.hours_since_last }}h</span>
                        <strong>{{ maintenanceRemainingLabel(item) }}</strong>
                      </div>
                      <div class="maintenance-progress-track">
                        <i :style="{ width: `${maintenanceProgress(item)}%` }"></i>
                      </div>
                    </div>

                    <div class="maintenance-facts">
                      <div><span>{{ t("maintenance.interval") }}</span><strong>{{ item.interval }}h</strong></div>
                      <div><span>{{ t("maintenance.currentHours") }}</span><strong>{{ item.current_print_hours }}h</strong></div>
                      <div><span>{{ t("maintenance.lastDone") }}</span><strong>{{ formatCell(item.last_performed_at) }}</strong></div>
                    </div>
                  </div>

                  <div class="maintenance-actions">
                    <input v-model="maintenanceNotes[item.id]" :placeholder="t('maintenance.note')" />
                    <button class="primary" type="button" @click="performMaintenance(item)">
                      <CheckCircle2 :size="17" />
                      {{ t("maintenance.perform") }}
                    </button>
                  </div>
                </article>
              </section>
            </div>
          </section>
        </div>
      </section>

      <section v-else-if="activeView === 'notifications'" class="view">
        <div class="grid two wide">
          <section class="panel">
            <div class="panel-header"><h3>{{ t("notifications.targets") }}</h3><Send :size="18" /></div>
            <div class="form-grid compact-form">
              <AppSelect v-model="notificationTargetForm.channel" :options="notificationChannelOptions" />
              <input v-model="notificationTargetForm.name" :placeholder="t('form.name')" />
              <input v-model="notificationTargetForm.url" :placeholder="t('notifications.url')" />
              <input v-model="notificationTargetForm.token" :placeholder="t('notifications.token')" type="password" />
              <label class="checkbox"><input v-model="notificationTargetForm.enabled" type="checkbox" /> {{ t("common.active") }}</label>
              <button class="primary" type="button" @click="saveNotificationTarget"><Save :size="17" />{{ t("common.save") }}</button>
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>{{ t("table.name") }}</th><th>{{ t("table.type") }}</th><th>{{ t("table.status") }}</th><th>{{ t("table.details") }}</th><th>{{ t("table.actions") }}</th></tr></thead>
                <tbody>
                  <tr v-if="!notificationTargets.length"><td colspan="5" class="empty">{{ t("common.empty") }}</td></tr>
                  <tr v-for="target in notificationTargets" :key="target.id">
                    <td>{{ target.name }}</td>
                    <td>{{ target.channel }}</td>
                    <td>{{ target.enabled ? t("common.active") : t("common.inactive") }}</td>
                    <td>{{ formatCell(target.display_config) }}</td>
                    <td>
                      <button class="icon-button compact" type="button" :title="t('table.actions')" @click="editNotificationTarget(target)"><PencilLine :size="14" /></button>
                      <button class="icon-button compact" type="button" :title="t('notifications.test')" @click="testNotificationTarget(target)"><Send :size="14" /></button>
                      <button class="icon-button compact danger" type="button" :title="t('common.delete')" @click="deleteNotificationTarget(target)"><Trash2 :size="14" /></button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header"><h3>{{ t("notifications.rules") }}</h3><Bell :size="18" /></div>
            <div class="form-grid compact-form">
              <input v-model="notificationRuleForm.name" :placeholder="t('form.name')" />
              <input v-model="notificationRuleForm.event_types" :placeholder="t('notifications.eventTypes')" />
              <input v-model="notificationRuleForm.printer_ids" :placeholder="t('notifications.printerIds')" />
              <input v-model="notificationRuleForm.severities" :placeholder="t('notifications.severities')" />
              <input v-model="notificationRuleForm.quiet_start" type="time" />
              <input v-model="notificationRuleForm.quiet_end" type="time" />
              <input v-model.number="notificationRuleForm.repeat_suppression_minutes" type="number" min="0" />
              <label class="checkbox"><input v-model="notificationRuleForm.enabled" type="checkbox" /> {{ t("common.active") }}</label>
              <button class="primary" type="button" @click="saveNotificationRule"><Save :size="17" />{{ t("common.save") }}</button>
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>{{ t("table.name") }}</th><th>{{ t("notifications.eventTypes") }}</th><th>{{ t("table.status") }}</th><th>{{ t("table.actions") }}</th></tr></thead>
                <tbody>
                  <tr v-if="!notificationRules.length"><td colspan="4" class="empty">{{ t("common.empty") }}</td></tr>
                  <tr v-for="rule in notificationRules" :key="rule.id">
                    <td>{{ rule.name }}</td>
                    <td>{{ (rule.event_types || []).join(', ') || t("common.none") }}</td>
                    <td>{{ rule.enabled ? t("common.active") : t("common.inactive") }}</td>
                    <td>
                      <button class="icon-button compact" type="button" @click="editNotificationRule(rule)"><PencilLine :size="14" /></button>
                      <button class="icon-button compact danger" type="button" @click="deleteNotificationRule(rule)"><Trash2 :size="14" /></button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>
        <section class="panel">
          <div class="panel-header"><h3>{{ t("notifications.deliveries") }}</h3><Database :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>{{ t("table.time") }}</th><th>{{ t("table.type") }}</th><th>{{ t("table.status") }}</th><th>{{ t("table.message") }}</th></tr></thead>
              <tbody>
                <tr v-if="!notificationDeliveries.length"><td colspan="4" class="empty">{{ t("common.empty") }}</td></tr>
                <tr v-for="delivery in notificationDeliveries" :key="delivery.id">
                  <td>{{ formatCell(delivery.created_at) }}</td>
                  <td>{{ delivery.event_type }}</td>
                  <td>{{ displayCell(delivery.status) }}</td>
                  <td>{{ softCell(delivery.error_summary) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </section>

      <section v-else-if="activeView === 'printers'" class="view">
        <div class="grid two wide">
          <section class="panel">
            <div class="panel-header"><h3>{{ t("printers.config") }}</h3><Settings :size="18" /></div>
            <div class="form-grid">
              <label>{{ t("form.name") }}<input v-model="printerForm.name" /></label>
              <label>{{ t("form.host") }}<input v-model="printerForm.host" /></label>
              <label>{{ t("form.port") }}<input v-model.number="printerForm.port" type="number" /></label>
              <label>{{ t("form.serial") }}<input v-model="printerForm.serial" /></label>
              <label class="access-code-field">
                {{ t("form.accessCode") }}
                <div class="input-with-action">
                  <input v-model="printerForm.access_code" :type="accessCodeVisible ? 'text' : 'password'" autocomplete="off" />
                  <button
                    class="icon-button compact"
                    type="button"
                    :disabled="accessCodeRevealLoading"
                    :title="accessCodeVisible ? t('form.hideAccessCode') : t('form.showAccessCode')"
                    @click="toggleAccessCodeVisibility"
                  >
                    <Loader2 v-if="accessCodeRevealLoading" class="spin" :size="15" />
                    <EyeOff v-else-if="accessCodeVisible" :size="15" />
                    <Eye v-else :size="15" />
                  </button>
                </div>
              </label>
              <div class="printer-security-options">
                <label class="checkbox"><input v-model="printerForm.tls_enabled" type="checkbox" /> TLS</label>
                <label class="checkbox"><input v-model="printerForm.certificate_verify" type="checkbox" /> {{ t("form.verifyCert") }}</label>
              </div>
            </div>
            <div class="toolbar printer-config-actions">
              <button class="primary" type="button" @click="savePrinter"><Save :size="17" />{{ t("common.save") }}</button>
              <button class="secondary" type="button" @click="connectPrinter"><PlugZap :size="17" />{{ t("common.connect") }}</button>
              <button class="secondary" type="button" @click="disconnectPrinter"><Unplug :size="17" />{{ t("common.disconnect") }}</button>
              <button class="secondary" type="button" :disabled="scanning" @click="scanDevices">
                <Loader2 v-if="scanning" class="spin" :size="17" />
                <Search v-else :size="17" />
                {{ scanning ? t("common.scanning") : t("common.scanLan") }}
              </button>
            </div>
            <div v-if="scanning || scanPhase" class="scan-progress">
              <div class="scan-progress-header">
                <span>{{ scanPhase }}</span>
                <strong>{{ scanProgressLabel }}%</strong>
              </div>
              <div class="progress-track">
                <span :style="{ width: `${scanProgressWidth}%` }"></span>
              </div>
            </div>
          </section>
          <section class="panel">
            <div class="panel-header"><h3>{{ t("printers.list") }}</h3><Network :size="18" /></div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>{{ t("table.id") }}</th><th>{{ t("table.name") }}</th><th>{{ t("table.host") }}</th><th>{{ t("table.status") }}</th><th>{{ t("table.lastSync") }}</th><th>{{ t("table.actions") }}</th></tr></thead>
                <tbody>
                  <tr v-for="printer in printers" :key="printer.id" :class="{ selected: printer.id === selectedPrinterId }" @click="selectedPrinterId = printer.id">
                    <td>{{ printer.id }}</td>
                    <td>{{ printer.name }}</td>
                    <td>{{ printer.host }}</td>
                    <td>{{ displayCell(printer.connection_status) }}</td>
                    <td>{{ formatCell(printer.last_sync_at) }}</td>
                    <td>
                      <button class="icon-button danger" type="button" :title="t('printers.delete')" @click.stop="deletePrinterConfig(printer)">
                        <Trash2 :size="16" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>
        <section class="panel">
          <div class="panel-header"><h3>{{ t("printers.discovery") }}</h3><Search :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>{{ t("table.host") }}</th><th>{{ t("table.model") }}</th><th>{{ t("table.deviceName") }}</th><th>{{ t("table.serial") }}</th><th>{{ t("table.confidence") }}</th><th>{{ t("table.reason") }}</th></tr></thead>
              <tbody>
                <tr v-if="!discovery.length"><td colspan="6" class="empty">{{ t("printers.noDiscovery") }}</td></tr>
                <tr v-for="item in discovery" :key="item.host">
                  <td>{{ item.host }}</td>
                  <td>{{ formatCell(item.model) }}</td>
                  <td>{{ formatCell(item.device_name) }}</td>
                  <td>{{ formatCell(item.serial) }}</td>
                  <td>{{ item.confidence }}</td>
                  <td>{{ item.reason }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </section>

      <section v-else class="view">
        <section class="panel">
          <div class="panel-header">
            <h3>{{ t("debug.systemInfo") }}</h3>
            <div class="widget-tools">
              <button v-if="experimentalFeatures.notifications" class="secondary" type="button" @click="switchView('notifications')">
                <Bell :size="17" />
                {{ t("nav.notifications") }}
              </button>
              <button class="secondary" type="button" @click="downloadSupportBundle">
                <Download :size="17" />
                {{ t("debug.supportBundle") }}
              </button>
              <Database :size="18" />
            </div>
          </div>
          <div class="network-info-grid">
            <div class="network-info-item"><span>{{ t("debug.appVersion") }}</span><strong>{{ systemInfo?.app_version || "--" }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.uptime") }}</span><strong>{{ formatDurationSeconds(systemInfo?.uptime_seconds) }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.databaseSize") }}</span><strong>{{ formatBytes(systemInfo?.database_size_bytes || 0) }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.storageSize") }}</span><strong>{{ formatBytes(systemInfo?.storage_size_bytes || 0) }}</strong></div>
            <div class="network-info-item"><span>CPU</span><strong>{{ formatCell(systemInfo?.cpu_percent) }}%</strong></div>
            <div class="network-info-item"><span>{{ t("debug.memory") }}</span><strong>{{ formatBytes(Number(systemInfo?.memory?.rss_bytes || 0)) }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.configuredPrinters") }}</span><strong>{{ systemInfo?.configured_printers || 0 }}</strong></div>
            <div class="network-info-item"><span>{{ t("debug.onlinePrinters") }}</span><strong>{{ systemInfo?.online_printers || 0 }}</strong></div>
          </div>
        </section>
        <section class="panel experimental-panel">
          <div class="panel-header"><h3>{{ t("debug.experimentalFeatures") }}</h3><ShieldAlert :size="18" /></div>
          <p class="panel-subtitle experimental-note">{{ t("debug.experimentalHint") }}</p>
          <div class="experimental-feature-grid">
            <label v-for="item in experimentalFeatureItems" :key="item.key" class="experimental-toggle-row">
              <span class="experimental-toggle-copy">
                <strong>{{ item.label }}</strong>
                <span>{{ item.description }}</span>
              </span>
              <input v-model="experimentalFeatures[item.key]" type="checkbox" />
              <span class="app-switch" :class="{ on: experimentalFeatures[item.key] }" aria-hidden="true"><i></i></span>
              <em>{{ experimentalFeatures[item.key] ? t("common.on") : t("common.off") }}</em>
            </label>
          </div>
        </section>
        <section class="panel export-panel">
          <div class="panel-header"><h3>{{ t("export.title") }}</h3><FileDown :size="18" /></div>
          <div class="export-controls">
            <AppSelect v-model="exportOptions.type" :options="[{ label: 'JSON', value: 'json' }, { label: 'CSV ZIP', value: 'csv' }]" />
            <button class="primary" type="button" @click="downloadExport"><Download :size="17" />{{ t("export.download") }}</button>
          </div>
          <div class="export-section-grid">
            <label v-for="section in exportSectionItems" :key="section.key" class="checkbox export-section">
              <input
                type="checkbox"
                :checked="exportOptions.sections.includes(section.key)"
                @change="toggleExportSection(section.key, checkboxChecked($event))"
              />
              {{ section.label }}
            </label>
          </div>
        </section>
        <div class="grid two wide debug-grid">
          <section class="panel debug-card">
            <div class="panel-header"><h3>{{ t("debug.events") }}</h3><Activity :size="18" /></div>
            <div class="table-wrap debug-scroll">
              <table>
                <thead><tr><th>{{ t("table.time") }}</th><th>{{ t("table.type") }}</th><th>{{ t("table.severity") }}</th><th>{{ t("table.message") }}</th></tr></thead>
                <tbody>
                  <tr v-for="item in recentEvents" :key="item.id">
                    <td>{{ formatCell(item.created_at) }}</td>
                    <td>{{ eventTypeLabel(item) }}</td>
                    <td>{{ displayCell(item.severity) }}</td>
                    <td>{{ eventMessage(item) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
          <section class="panel debug-card">
            <div class="panel-header"><h3>{{ t("debug.rawMqtt") }}</h3><Database :size="18" /></div>
            <pre class="json-block debug-scroll">{{ JSON.stringify(rawMqtt, null, 2) }}</pre>
          </section>
        </div>
      </section>
    </main>

    <div v-if="selectedHms" class="modal-backdrop" @click.self="selectedHms = null">
      <section class="modal-panel">
        <div class="modal-header">
          <h3>{{ t("hms.details") }} · {{ formatCell(selectedHms.short_code || selectedHms.code) }}</h3>
          <button class="icon-button" type="button" :title="t('common.close')" @click="selectedHms = null"><X :size="17" /></button>
        </div>
        <dl class="kv">
          <dt>{{ t("table.description") }}</dt><dd>{{ hmsMessage(selectedHms) }}</dd>
          <dt>{{ t("hms.suggestion") }}</dt><dd>{{ hmsSuggestion(selectedHms) || "--" }}</dd>
          <dt>{{ t("table.current") }}</dt><dd>{{ selectedHms.active ? t("common.unresolved") : t("common.resolved") }}</dd>
          <dt>{{ t("table.module") }}</dt><dd>{{ formatCell(selectedHms.module_name) }}</dd>
          <dt>{{ t("hms.known") }}</dt><dd>{{ selectedHms.known === false ? t("common.off") : t("common.on") }}</dd>
          <dt>{{ t("hms.actionable") }}</dt><dd>{{ selectedHms.actionable === false ? t("common.off") : t("common.on") }}</dd>
          <dt>{{ t("hms.recentCount") }}</dt><dd>{{ selectedHmsStats?.recent_count ?? "--" }}</dd>
          <dt>{{ t("hms.lastRecovered") }}</dt><dd>{{ formatCell(selectedHmsStats?.last_recovered_at) }}</dd>
          <dt>{{ t("hms.highFrequency") }}</dt><dd>{{ selectedHmsStats?.high_frequency ? t("common.on") : t("common.off") }}</dd>
          <dt>attr / code / source</dt><dd class="mono">{{ formatCell(selectedHms.attr) }} / {{ formatCell(selectedHms.code) }} / {{ formatCell(selectedHms.source) }}</dd>
          <dt>Wiki</dt><dd><a v-if="selectedHms.wiki_url" :href="selectedHms.wiki_url" target="_blank" rel="noreferrer">{{ selectedHms.wiki_url }}</a><span v-else>--</span></dd>
        </dl>
      </section>
    </div>

    <div v-if="selectedSlot" class="modal-backdrop" @click.self="selectedSlot = null">
      <section class="modal-panel wide-modal slot-detail-modal">
        <div class="modal-header">
          <div class="modal-title-stack">
            <h3>{{ t("ams.slotDetails") }}</h3>
            <p>AMS {{ selectedSlot.ams_id }} / {{ slotDisplayLabel(selectedSlot) }}</p>
          </div>
          <button class="icon-button" type="button" :title="t('common.close')" @click="selectedSlot = null"><X :size="17" /></button>
        </div>

        <div class="slot-detail-hero">
          <div class="slot-detail-spool">
            <div class="ams-spool" :style="{ '--filament-color': filamentColor(selectedSlot.color || selectedSlot.tray_color) }"><i></i></div>
            <div>
              <span>{{ t("table.material") }}</span>
              <strong>{{ softCell(selectedSlot.material) }}</strong>
              <small>{{ softCell(selectedSlot.color || selectedSlot.tray_color) }}</small>
            </div>
          </div>
          <div class="slot-detail-facts">
            <div><span>{{ t("table.state") }}</span><strong>{{ displayCell(selectedSlot.state_name || selectedSlot.slot_state) }}</strong></div>
            <div><span>{{ t("table.remain") }}</span><strong>{{ remainLabel(selectedSlot.remain) }}</strong></div>
            <div><span>K</span><strong>{{ softCell(selectedSlot.k) }}</strong></div>
            <div><span>{{ t("ams.caliIdx") }}</span><strong>{{ softCell(selectedSlot.cali_idx) }}</strong></div>
            <div><span>RFID</span><strong>{{ softCell(selectedSlot.rfid_status_name || selectedSlot.rfid_status || selectedSlot.tray_info_idx) }}</strong></div>
            <div><span>{{ t("table.spool") }}</span><strong>{{ softCell(selectedSlot.spool_id) }}</strong></div>
          </div>
        </div>

        <section class="slot-detail-section">
          <div class="slot-section-title">
            <h4>{{ t("ams.changeSummary") }}</h4>
            <span>{{ t("ams.historySamples") }} {{ selectedSlotHistory.length }}</span>
          </div>
          <div class="slot-change-grid">
            <section v-for="kind in slotChangeKinds" :key="kind" class="slot-change-card">
              <div class="slot-change-card-head">
                <h4>{{ t(`ams.change.${kind}`) }}</h4>
                <span>{{ slotHistoryChanges(kind).length }}</span>
              </div>
              <div v-if="!slotHistoryChanges(kind).length" class="slot-empty-state">{{ t("ams.noChanges") }}</div>
              <div v-for="change in slotHistoryChanges(kind)" :key="`${kind}-${change.time}`" class="slot-change-row">
                <time>{{ formatCell(change.time) }}</time>
                <div class="slot-change-flow">
                  <span>{{ change.before }}</span>
                  <i>→</i>
                  <strong>{{ change.after }}</strong>
                </div>
              </div>
            </section>
          </div>
        </section>

        <section class="slot-detail-section">
          <div class="slot-section-title">
            <h4>{{ t("ams.historySamples") }}</h4>
            <span>{{ selectedSlotHistory.length }}</span>
          </div>
          <div class="table-wrap slot-history-table">
          <table>
            <thead><tr><th>{{ t("table.time") }}</th><th>{{ t("table.state") }}</th><th>{{ t("table.material") }}</th><th>{{ t("form.color") }}</th><th>{{ t("table.remain") }}</th><th>K</th><th>{{ t("ams.caliIdx") }}</th><th>RFID</th></tr></thead>
            <tbody>
              <tr v-if="!selectedSlotHistory.length"><td colspan="8" class="empty">{{ t("common.empty") }}</td></tr>
              <tr v-for="sample in selectedSlotHistory" :key="sample.id">
                <td>{{ formatCell(sample.sampled_at) }}</td>
                <td>{{ displayCell(sample.state_name) }}</td>
                <td>{{ softCell(sample.material) }}</td>
                <td><span class="swatch" :style="{ background: filamentColor(sample.color) }"></span>{{ softCell(sample.color) }}</td>
                <td>{{ softCell(sample.remain) }}</td>
                <td>{{ softCell(sample.k) }}</td>
                <td>{{ softCell(sample.cali_idx) }}</td>
                <td>{{ softCell(sample.rfid_status) }}</td>
              </tr>
            </tbody>
          </table>
          </div>
        </section>
      </section>
    </div>

    <div v-if="loading" class="loading-mask" :title="displayCell('loading')">
      <Loader2 class="spin" :size="24" />
    </div>
  </div>
</template>
