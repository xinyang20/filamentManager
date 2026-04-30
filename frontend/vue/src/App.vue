<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import {
  Activity,
  AlertCircle,
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
  Plus,
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
  Upload,
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
  FilamentBrand,
  FilamentColorMappingGap,
  FilamentColorMapping,
  FilamentInventorySummary,
  FilamentSku,
  FilamentSpool,
  FilamentSpoolEvents,
  FilamentTypeSeries,
  HmsCodeInfo,
  HmsCodeStats,
  MaintenanceOverview,
  MetricSample,
  NotificationDelivery,
  NotificationRule,
  NotificationTarget,
  Printer,
  PrinterCameraCapabilities,
  PrinterMaintenance,
  PrintLogAnalytics,
  PrintLogEntry,
  PrintLogList,
  PrintLogSummary,
  StorageFile,
  StorageSummary,
  SystemInfo,
  TimelapseNote,
  UnifiedEvent,
} from "./types";

const viewKeys = [
  "overview",
  "dashboard",
  "events",
  "metrics",
  "printLog",
  "storage",
  "ams",
  "inventory",
  "maintenance",
  "notifications",
  "printers",
  "debug",
] as const;
type ViewKey = (typeof viewKeys)[number];
type InventoryPageKey = "stock" | "history" | "brands" | "types" | "skus" | "colors";
type Locale = keyof typeof translations;
type NavGroupKey = "monitoring" | "assets" | "system";
type SortDirection = "asc" | "desc";
type InventoryDialogKey =
  | "brand"
  | "typeSeries"
  | "sku"
  | "colorMapping"
  | "spoolCreate"
  | "spoolDetail"
  | "stockAdjust"
  | "skuConfirm";

const storedView = window.localStorage.getItem("filamentManager.activeView");

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
const inventoryPage = ref<InventoryPageKey>(resolveInitialInventoryPage(storedView));
const printers = ref<Printer[]>([]);
const selectedPrinterId = ref<number | null>(null);
const dashboardSummary = ref<DashboardSummaryItem[]>([]);
const dashboard = ref<Dashboard | null>(null);
const deviceCapabilities = ref<DeviceCapabilities | null>(null);
const cameraCapabilities = ref<PrinterCameraCapabilities | null>(null);
const cameraStreamError = ref(false);
const cameraStreamToken = ref(Date.now());
const cameraLightboxOpen = ref(false);
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
const inventoryAmsOverviews = ref<Record<string, AmsOverview>>({});
const inventoryPrinterStates = ref<Record<string, Record<string, any> | null>>({});
const amsLabelDrafts = reactive<Record<string, string>>({});
const amsLabelEditing = reactive<Record<string, boolean>>({});
const amsSensorRange = ref("24");
const amsSensorHistories = ref<Record<string, AmsSensorHistory>>({});
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
const selectedEvent = ref<UnifiedEvent | null>(null);
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
const pinyinCollator = new Intl.Collator("zh-Hans-CN-u-co-pinyin", {
  numeric: true,
  sensitivity: "base",
});
const inventoryChartColors = ["#00ae42", "#0086d6", "#f4a925", "#c12e1f", "#5e43b7", "#8e9089", "#ff6a13", "#2842ad"];

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
  sections: [
    "config",
    "filament_catalog",
    "filament_color_mappings",
    "ams_current",
    "print_logs",
    "ams_history",
    "maintenance_history",
    "events",
    "notifications",
    "storage",
    "telemetry",
  ] as string[],
});
const importOptions = reactive({
  mode: "merge",
});
const importFileInput = ref<HTMLInputElement | null>(null);
const importResult = ref<Record<string, any> | null>(null);

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

const selectedPrinter = computed(() => printers.value.find((item) => item.id === selectedPrinterId.value) || null);
const printerSelectOptions = computed(() =>
  printers.value.length
    ? printers.value.map((printer) => ({ label: `${printer.name} · ${printer.host}`, value: printer.id }))
    : [{ label: t("common.noPrinter"), value: null, disabled: true }],
);
const locationPrinterOptions = computed(() => [
  { label: t("common.noPrinter"), value: null },
  ...printers.value.map((printer) => ({ label: `${printer.name} · ${printer.host}`, value: printer.id })),
]);
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
  { key: "filament_catalog", label: t("export.sectionFilamentCatalog") },
  { key: "filament_color_mappings", label: t("export.sectionFilamentColorMappings") },
  { key: "ams_current", label: t("export.sectionAmsCurrent") },
  { key: "print_logs", label: t("export.sectionPrintLogs") },
  { key: "ams_history", label: t("export.sectionAmsHistory") },
  { key: "maintenance_history", label: t("export.sectionMaintenance") },
  { key: "events", label: t("export.sectionEvents") },
  { key: "notifications", label: t("export.sectionNotifications") },
  { key: "storage", label: t("export.sectionStorage") },
  { key: "telemetry", label: t("export.sectionTelemetry") },
]);
const importModeOptions = computed(() => [
  { label: t("export.importModeMerge"), value: "merge" },
  { label: t("export.importModeReplace"), value: "replace" },
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
  { label: t("metrics.range6h"), value: "6" },
  { label: t("metrics.range24h"), value: "24" },
  { label: t("metrics.range7d"), value: "168" },
  { label: t("metrics.range30d"), value: "720" },
]);
const spoolStatusOptions = computed(() => [
  { label: displayCell("sealed"), value: "sealed" },
  { label: displayCell("opened"), value: "opened" },
  { label: displayCell("active"), value: "active" },
  { label: displayCell("archived"), value: "archived" },
]);
const filamentInventoryTabOptions = computed(() => [
  { label: t("inventory.skuStock"), value: "skus" },
  { label: t("inventory.realSpools"), value: "spools" },
  { label: t("inventory.amsCurrent"), value: "ams" },
  { label: t("inventory.spoolDetail"), value: "detail" },
]);
const filamentSpoolStatusOptions = computed(() => [
  { label: displayCell("opened_in_storage"), value: "opened_in_storage" },
  { label: displayCell("loaded_in_ams"), value: "loaded_in_ams" },
  { label: displayCell("needs_location"), value: "needs_location" },
  { label: t("inventory.status.empty"), value: "empty" },
  { label: t("inventory.status.archived"), value: "archived" },
  { label: displayCell("unknown"), value: "unknown" },
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
  amsSlots.value.map((slot) => ({
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
  for (const slot of amsSlots.value) {
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
const shouldShowDashboardCamera = computed(() => cameraStatusRows.value.length > 0 || capabilityVisibleFields.value.has("camera"));
const shouldShowDashboardLiveCamera = computed(() => Boolean(selectedPrinterId.value && (cameraCapabilities.value?.available || shouldShowDashboardCamera.value)));
const cameraStreamSrc = computed(() => {
  if (!selectedPrinterId.value || !cameraCapabilities.value?.available) return "";
  return `${API_BASE}/printers/${selectedPrinterId.value}/camera/mjpeg?t=${cameraStreamToken.value}`;
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
const dashboardHmsRows = computed(() => {
  const unresolved = hmsErrors.value.filter((item) => item.active !== false && item.actionable !== false);
  const resolvedOrMuted = hmsErrors.value.filter((item) => item.active === false || item.actionable === false).slice(0, 3);
  return [...unresolved, ...resolvedOrMuted];
});
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
  cameraCapabilities.value = null;
  cameraLightboxOpen.value = false;
  restartCameraStream();
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

watch(inventoryPage, (page) => {
  window.localStorage.setItem("filamentManager.inventoryPage", page);
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
  if (isFilamentManagementView(activeView.value)) {
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
  const [result, capabilities, cameraCapabilityResult, colorMappingResult] = await Promise.all([
    fetchDashboard(),
    apiRequest<DeviceCapabilities>(`/printers/${selectedPrinterId.value}/capabilities`),
    apiRequest<PrinterCameraCapabilities>(`/printers/${selectedPrinterId.value}/camera/capabilities`).catch((error) => ({
      available: false,
      detail: error instanceof Error ? error.message : String(error),
    })),
    apiRequest<FilamentColorMapping[]>("/filament/color-mappings"),
  ]);
  if (result) dashboard.value = result;
  deviceCapabilities.value = capabilities;
  cameraCapabilities.value = cameraCapabilityResult;
  cameraStreamError.value = false;
  filamentColorMappings.value = colorMappingResult;
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
  const [stateResult, overviewResult, slotResult, eventResult, colorMappingResult] = await Promise.all([
    apiRequest<Record<string, any> | null>(`/printers/${selectedPrinterId.value}/state`),
    apiRequest<AmsOverview>(`/printers/${selectedPrinterId.value}/ams/overview`),
    apiRequest<Record<string, any>[]>(`/printers/${selectedPrinterId.value}/ams/slots`),
    apiRequest<UnifiedEvent[]>(`/events?printer_id=${selectedPrinterId.value}&limit=50`),
    apiRequest<FilamentColorMapping[]>("/filament/color-mappings"),
  ]);
  stateSnapshot.value = stateResult;
  amsOverview.value = overviewResult;
  amsSlots.value = slotResult;
  events.value = eventResult;
  filamentColorMappings.value = colorMappingResult;
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
  amsSlots.value = inventoryAmsResult.slots;
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
  if (!printers.value.length) return { slots: [], overviews: {}, states: {} };
  const rows = await Promise.all(
    printers.value.map(async (printer) => {
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
        empty_spool_weight_g: optionalNumber(filamentTypeSeriesForm.empty_spool_weight_g),
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
  inventoryPage.value = "colors";
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
  const nominalWeight = optionalNumber(filamentSkuForm.nominal_weight_g);
  return {
    type_series_id: filamentSkuForm.type_series_id,
    color_name: filamentSkuForm.color_name || null,
    color_hex: filamentSkuForm.color_value || null,
    nominal_weight_g: nominalWeight ?? 1000,
    filament_diameter_mm: optionalNumber(filamentSkuForm.filament_diameter_mm) ?? 1.75,
    tray_info_idx: filamentSkuForm.tray_info_idx || null,
    sealed_quantity: editingFilamentSkuId.value ? undefined : optionalNumber(filamentSkuForm.sealed_quantity) ?? 0,
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
    const targetSealedQuantity = Math.max(0, Math.round(optionalNumber(filamentSkuForm.sealed_quantity) ?? 0));
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
  const target = Math.max(0, Math.round(optionalNumber(sealedStockAdjustForm.target_quantity) ?? 0));
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
  inventoryPage.value = "skus";
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
  const raw = record(record(spool?.config).ams_raw);
  const firstTypeSeries = arrayOfRecord(spool?.type_series)[0] || null;
  const firstBrand = arrayOfRecord(spool?.brands)[0] || null;
  const material = firstText(spool?.material, raw.tray_type, raw.filament_type, firstTypeSeries?.material_type, "PLA");
  const series = firstText(spool?.series, raw.tray_sub_brands, raw.tray_info_idx, raw.filament_name, firstTypeSeries?.series_name);
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
    color_name: firstText(
      spool?.color_name,
      raw.tray_color_name,
      raw.color_name,
      raw.filament_color_name,
      raw.color_display_name,
    ),
    color_value: normalizeFilamentHex(firstText(spool?.color_hex, spool?.color_value, raw.tray_color, raw.color)) || "",
    nominal_weight_g: nominalWeight ?? 1000,
    empty_spool_weight_g: numeric(spool?.empty_spool_weight_g ?? firstTypeSeries?.empty_spool_weight_g),
    filament_diameter_mm: 1.75,
    tray_info_idx: firstText(raw.tray_info_idx),
    sealed_quantity: 0,
    note: firstText(spool?.note),
  });
}

function firstText(...values: unknown[]): string {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    const text = String(value).trim();
    if (text) return text;
  }
  return "";
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
        actual_weight_g: optionalNumber(filamentSpoolForm.current_remaining_g),
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
  let actualWeight = optionalNumber(quantityAdjustForm.current_remaining_g);
  if (actualWeight === null) {
    const percent = optionalNumber(quantityAdjustForm.remain_percent);
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
        printer_id: optionalNumber(locationAdjustForm.printer_id),
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
  if (exportOptions.type === "json") params.set("mode", "backup");
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

async function importBackupFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  try {
    const text = await file.text();
    const payload = JSON.parse(text) as Record<string, any>;
    const confirmed = importOptions.mode !== "replace" || window.confirm(t("export.importReplaceConfirm"));
    if (!confirmed) return;
    await withLoading(async () => {
      importResult.value = await apiRequest<Record<string, any>>("/import", {
        method: "POST",
        body: JSON.stringify({ mode: importOptions.mode, payload }),
      });
      await refreshPrinters();
      await loadCurrent();
      message.value = t("export.importComplete");
    });
  } catch (error) {
    message.value = error instanceof Error ? error.message : String(error);
  } finally {
    input.value = "";
  }
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

function resolveInitialView(view: string | null) {
  if (view === "filamentBrands" || view === "filamentSkus" || view === "filamentSpools") return "inventory";
  if (!viewKeys.includes(view as ViewKey)) return "overview";
  const next = view as ViewKey;
  return isViewEnabled(next) ? next : "overview";
}

function resolveInitialInventoryPage(view: string | null): InventoryPageKey {
  if (view === "filamentBrands") return "brands";
  if (view === "filamentSkus") return "skus";
  if (view === "filamentSpools") return "stock";
  const stored = window.localStorage.getItem("filamentManager.inventoryPage");
  if (stored === "stock" || stored === "brands" || stored === "types" || stored === "skus" || stored === "colors") return stored;
  return "stock";
}

function isFilamentManagementView(view: ViewKey) {
  return view === "inventory";
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

function normalizeFilamentHex(value: unknown): string | null {
  const text = String(value || "")
    .trim()
    .replace(/^#/, "")
    .replace(/[\s_-]/g, "")
    .toUpperCase();
  const compact = text.length === 8 ? text.slice(0, 6) : text;
  return /^[0-9A-F]{6}$/.test(compact) ? compact : null;
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
  const printer = printers.value.find((item) => item.id === id);
  return printer?.name || formatCell(printerId);
}

function amsUnitForSlot(slot: Record<string, any> | null | undefined): Record<string, any> | null {
  if (!slot) return null;
  const overview = activeView.value === "ams"
    ? amsOverview.value
    : inventoryAmsOverviews.value[String(slot.printer_id)] || amsOverview.value;
  if (overview) return overview.units.find((unit) => String(unit.ams_id) === String(slot.ams_id)) || null;
  return null;
}

function filamentAmsSlotLocationLabel(slot: Record<string, any> | null | undefined): string {
  if (!slot) return "—";
  const unit = amsUnitForSlot(slot);
  if (unit) return `${amsTitle(unit)} / ${slotDisplayLabel(slot)}`;
  return slot.location_label || `AMS ${formatCell(slot.ams_id)} / ${slotDisplayLabel(slot)}`;
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
  const last = record(spool.last_location || spool.config?.last_location);
  if (last.ams_id || last.tray_id) {
    return `AMS ${formatCell(last.ams_id)} / ${t("form.slotId")} ${formatCell(last.tray_id)}`;
  }
  return firstText(last.storage_location, spool.storage_location, spool.manual_location) || "—";
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
  return displayCell(status);
}

function filamentSpoolNeedsUidConflictResolution(spool: FilamentSpool | Record<string, any> | null | undefined): boolean {
  return Boolean(spool?.config?.review_reason === "archived_uid_reappeared");
}

function filamentSkuReviewDescription(spool: FilamentSpool | Record<string, any> | null | undefined): string {
  if (filamentSpoolNeedsUidConflictResolution(spool)) return t("inventory.uidConflictDescription");
  if (spool?.config?.sku_review_reason === "ams_filament_change") return t("inventory.confirmSkuReplacementDescription");
  return t("inventory.confirmSkuDescription");
}

function filamentWeight(value: unknown): string {
  const parsed = numeric(value);
  return parsed === null ? "—" : `${Math.round(parsed)} g`;
}

function filamentKg(value: unknown): string {
  const parsed = numeric(value);
  if (parsed === null) return "—";
  return `${(parsed / 1000).toFixed(parsed >= 10000 ? 1 : 2)} kg`;
}

function filamentInventoryKg(value: unknown): string {
  const parsed = numeric(value);
  if (parsed === null) return "—";
  return `${(parsed / 1000).toFixed(2)} kg`;
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

function optionalNumber(value: unknown): number | null {
  return numeric(value);
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

function filamentRemainPercent(spool: FilamentSpool | Record<string, any> | null | undefined): string {
  if (!spool) return "—";
  if (spool.last_ams_remain_percent !== null && spool.last_ams_remain_percent !== undefined) {
    return `${spool.last_ams_remain_percent}%`;
  }
  const remaining = numeric(spool.actual_weight_g ?? spool.current_remaining_g);
  const initial = numeric(spool.nominal_weight_g ?? spool.initial_net_weight_g);
  if (remaining === null || initial === null || initial <= 0) return "—";
  return `${Math.round((remaining / initial) * 100)}%`;
}

function filamentSpoolRemainingWeight(spool: FilamentSpool | Record<string, any> | null | undefined): number | null {
  if (!spool) return null;
  const measured = numeric(spool.actual_weight_g ?? spool.current_remaining_g);
  if (measured !== null && measured >= 0) return measured;
  const remain = numeric(spool.last_ams_remain_percent);
  const nominal = numeric(spool.nominal_weight_g ?? spool.initial_net_weight_g);
  if (remain === null || remain < 0 || nominal === null || nominal <= 0) return null;
  return (nominal * remain) / 100;
}

function filamentSpoolRemainingLabel(spool: FilamentSpool | Record<string, any> | null | undefined): string {
  const percent = filamentRemainPercent(spool);
  const weight = filamentSpoolRemainingWeight(spool);
  if (weight === null) return percent;
  return `${percent} / ${Math.round(weight)} g`;
}

function filamentAmsRemainingWeight(slot: Record<string, any>, spool: FilamentSpool | Record<string, any> | null | undefined): number | null {
  const reported = [
    slot.remaining_weight_g,
    slot.remain_weight_g,
    slot.remain_g,
    slot.tray_remaining_weight_g,
    slot.raw?.remaining_weight_g,
    slot.raw?.remain_weight_g,
    slot.raw?.remain_g,
    slot.raw?.tray_remaining_weight_g,
    slot.raw?.remaining_weight,
    slot.raw?.remain_weight,
    slot.raw?.tray_remaining_weight,
  ].map((value) => numeric(value)).find((value) => value !== null && value >= 0);
  if (reported !== undefined) return reported;
  const remain = numeric(slot.remain);
  const nominal = numeric(spool?.nominal_weight_g ?? spool?.initial_net_weight_g);
  if (remain === null || remain < 0 || nominal === null || nominal <= 0) return null;
  return (nominal * remain) / 100;
}

function filamentAmsRemainingLabel(slot: Record<string, any>, spool: FilamentSpool | Record<string, any> | null | undefined): string {
  const remain = numeric(slot.remain);
  const percent = remain !== null && remain >= 0 ? `${Math.round(remain)}%` : "—";
  const weight = filamentAmsRemainingWeight(slot, spool);
  if (weight === null) return percent;
  return `${percent} / ${Math.round(weight)} g`;
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
    amsSlots.value.find((slot) => Number(slot.filament_spool_id) === Number(spool.id)) ||
    amsSlots.value.find(
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
  const raw = record(slot.raw);
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
  const raw = record(slot.raw);
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
  const gcodeState = String(state.gcode_state || record(state.payload).gcode_state || record(record(state.payload).print).gcode_state || "")
    .trim()
    .toUpperCase();
  return ["RUNNING", "PAUSE", "PAUSED", "PREPARE", "SLICING", "M400_PAUSE"].includes(gcodeState);
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
  if (slot) return activeSlotDisplayLabel(slot);
  const trayNow = numeric(status.tray_now);
  if (trayNow !== null && trayNow >= 0 && trayNow < 255) return `${t("table.tray")} ${Math.round(trayNow) + 1}`;
  return "--";
}

function dashboardActiveMaterialLabel(slot: Record<string, any> | null | undefined) {
  if (!slot) return "--";
  const parts = [slot.material || slot.tray_type, slot.series || slot.tray_sub_brands, slotColorLabel(slot)].filter(Boolean).map(String);
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
    title: amsTitle(unit),
    code: `#${unit.ams_id}`,
    meta: dashboardAmsUnitMeta(unit),
    slots: unitSlots.map((slot, slotIndex) => ({
      key: slotKey(slot),
      label: dashboardAmsSlotShortLabel(slot, unit, index, slotIndex),
      material: dashboardAmsSlotMaterial(slot),
      remain: dashboardAmsSlotRemain(slot),
      active: slot.is_active === true || isSameDashboardAmsSlot(slot, activeSlot),
      loaded: isDashboardAmsLoaded(slot),
      style: { "--filament-color": filamentColor(slot.color || slot.tray_color) },
    })),
  };
}

function amsPageUnitVisual(unit: Record<string, any>, index: number) {
  return dashboardAmsUnitVisual(unit, arrayOfRecord(unit.slots), index, record(unit.active_slot));
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
  const type = String(item.type || item.event_type || "");
  if (type.startsWith("hms.")) return hmsEventMessage(item, data);
  if (data.command || type.startsWith("printer.command.")) {
    return t("events.commandReceived", { command: displayCell(data.command || type.replace("printer.command.", "")) });
  }
  if (type === "print.started") return t("events.printStarted", { file: eventPrintName(data) });
  if (type === "print.paused") return t("events.printPaused", { file: eventPrintName(data) });
  if (type === "print.resumed") return t("events.printResumed", { file: eventPrintName(data) });
  if (type === "print.finished") return t("events.printFinished", { file: eventPrintName(data) });
  if (type === "print.failed") return t("events.printFailed", { file: eventPrintName(data) });
  if (type === "print.cancelled") return t("events.printCancelled", { file: eventPrintName(data) });
  if (type === "printer.connection.restored") return t("events.connectionRestored");
  if (type === "printer.connection.disconnected") return t("events.connectionDisconnected", { reason: displayCell(data.error) });
  if (type === "ams.unit.updated") return t("events.amsUnitUpdated", { ams: displayCell(data.ams_id), type: displayCell(data.ams_type_name || data.module_type) });
  if (type === "ams.slot.updated") {
    return t("events.amsSlotUpdated", {
      slot: eventAmsSlotLabel(data),
      state: eventAmsSlotStateLabel(data.state),
      material: displayCell(data.material),
      remain: data.remain === null || data.remain === undefined ? "—" : `${data.remain}%`,
    });
  }
  if (type === "filament.spool.pending_confirmation") return t("events.filamentSkuReviewPending", { spool: displayCell(data.filament_spool_id), slot: eventAmsSlotLabel(data) });
  if (type === "spool.discovered") return t("events.spoolDiscovered", { spool: displayCell(data.filament_spool_id), slot: eventAmsSlotLabel(data) });
  if (type === "spool.unidentified") return t("events.spoolUnidentified", { slot: eventAmsSlotLabel(data) });
  if (type === "slot.identity_fallback") return t("events.slotIdentityFallback", { slot: eventAmsSlotLabel(data) });
  if (type === "spool.location_changed") return t("events.spoolLocationUpdated");
  if (type === "loaded_to_ams") return t("events.inventoryLoadedToAms", { spool: displayCell(item.spool_id), slot: eventAmsSlotLabel(data) });
  if (type === "unloaded_from_ams") return t("events.inventoryUnloadedFromAms", { spool: displayCell(item.spool_id), slot: eventAmsSlotLabel(data) });
  if (type === "opened_from_stock") return t("events.inventoryOpenedFromStock", { spool: displayCell(item.spool_id) });
  if (type === "sealed_stock_adjusted") return t("events.inventorySealedAdjusted");
  if (type === "location_updated") return t("events.inventoryLocationUpdated", { spool: displayCell(item.spool_id) });
  if (type === "weight_updated") return t("events.inventoryWeightUpdated", { spool: displayCell(item.spool_id) });
  if (type === "needs_location") return t("events.inventoryNeedsLocation", { spool: displayCell(item.spool_id) });
  if (type === "sku_confirmed") return t("events.inventorySkuConfirmed", { spool: displayCell(item.spool_id) });
  if (type === "storage.scan" || type === "storage.scan.finished") return t("events.storageScanFinished");
  if (type === "storage.scan_failed" || type === "storage.scan.failed") return t("events.storageScanFailed", { reason: displayCell(data.error || item.message) });
  return String(item.message || "");
}

function hmsEventMessage(item: UnifiedEvent | Record<string, any>, data: Record<string, any>) {
  const shortCode = displayCell(data.short_code || data.code);
  const detail = locale.value === "zh-CN" ? data.message_zh || data.message : data.message_en || data.message;
  const active = item.active === false || String(item.type || item.event_type || "") === "hms.recovered" ? t("common.resolved") : t("common.unresolved");
  return t("events.hmsSemantic", { code: shortCode, state: active, detail: displayCell(detail) });
}

function eventPrintName(data: Record<string, any>): string {
  return displayCell(data.gcode_file || data.task_id || data.subtask_name);
}

function eventAmsSlotLabel(data: Record<string, any>): string {
  const ams = displayCell(data.ams_id);
  const tray = numeric(data.tray_id);
  const slot = tray === null ? displayCell(data.tray_id) : `${Math.round(tray) + 1}`;
  return `AMS ${ams} / ${t("table.tray")} ${slot}`;
}

function eventAmsSlotStateLabel(value: unknown): string {
  const key = String(value ?? "").trim().toLowerCase();
  if (!key) return "—";
  const mapped = t(`amsSlotStates.${key}`);
  if (mapped !== `amsSlotStates.${key}`) return mapped;
  return displayCell(value);
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
  if (kind === "material") return `${softCell(sample.material)} / ${filamentColorDisplay(sample.color)}`;
  if (kind === "remain") return softCell(sample.remain);
  if (kind === "rfid") return softCell(sample.rfid_status);
  return `K ${softCell(sample.k)} / ${softCell(sample.cali_idx)}`;
}

function filamentColor(value: unknown) {
  const hex = normalizeFilamentHex(value);
  return hex ? `#${hex}` : "#d7dce2";
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
          <section class="panel">
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

          <section class="panel dashboard-live-panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.liveCamera") }}</h3>
              <div class="widget-tools">
                <Camera :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.liveCamera')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.liveCamera')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.liveCamera')" class="camera-live-card">
              <button class="camera-live-frame camera-live-trigger" type="button" :title="t('dashboard.openLiveCamera')" @click="openCameraLightbox">
                <img
                  v-if="cameraStreamSrc && !cameraStreamError && !cameraLightboxOpen"
                  :src="cameraStreamSrc"
                  :alt="t('dashboard.liveCamera')"
                  @error="handleCameraStreamError"
                  @load="handleCameraStreamLoaded"
                />
                <div v-else class="camera-live-placeholder">
                  <Camera :size="28" />
                  <strong>{{ cameraLivePlaceholder }}</strong>
                  <span>{{ t("dashboard.cameraStreamForwarding") }}</span>
                </div>
              </button>
              <div class="camera-live-footer">
                <span>{{ t("dashboard.cameraStreamForwarding") }}</span>
                <div class="camera-live-actions">
                  <button class="icon-button compact" type="button" :title="t('dashboard.openLiveCamera')" @click="openCameraLightbox">
                    <Eye :size="15" />
                  </button>
                  <button class="icon-button compact" type="button" :title="t('dashboard.restartCameraStream')" @click="restartCameraStream">
                    <RefreshCw :size="15" />
                  </button>
                </div>
              </div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <h3>{{ t("dashboard.deviceDiagnostics") }}</h3>
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
              <h3>{{ t("dashboard.networkHardware") }}</h3>
              <div class="widget-tools">
                <Network :size="18" />
                <button class="icon-button compact" type="button" :title="t('layout.collapse')" @click="toggleSectionCollapsed('dashboard.network')">
                  <ChevronDown v-if="isSectionCollapsed('dashboard.network')" :size="15" />
                  <ChevronUp v-else :size="15" />
                </button>
              </div>
            </div>
            <div v-show="!isSectionCollapsed('dashboard.network')" class="combined-status-sections">
              <div class="network-info-grid">
                <div v-for="[key, value] in readableNetworkHardware" :key="key" class="network-info-item">
                  <span>{{ fieldLabel(key) }}</span>
                  <strong>{{ displayCell(value) }}</strong>
                </div>
                <div v-if="!readableNetworkHardware.length" class="empty">{{ t("common.empty") }}</div>
              </div>
              <div>
                <div class="section-label">{{ t("dashboard.hmsErrors") }}</div>
                <div class="dashboard-hms-list" :class="{ scrollable: dashboardHmsRows.length > 5 }">
                  <button v-if="!dashboardHmsRows.length" class="dashboard-hms-empty" type="button" disabled>
                    {{ t("dashboard.noHmsErrors") }}
                  </button>
                  <button
                    v-for="(item, index) in dashboardHmsRows"
                    :key="`${item.short_code || item.code}-${item.active}-${index}`"
                    class="dashboard-hms-row"
                    type="button"
                    @click="openHmsDetails(item)"
                  >
                    <span class="mono">{{ formatCell(item.short_code || item.code) }}</span>
                    <strong>{{ displayCell(item.severity_name) }}</strong>
                    <em>{{ item.active !== false && item.actionable !== false ? t("common.unresolved") : t("common.resolved") }}</em>
                  </button>
                </div>
              </div>
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
            <div v-show="!isSectionCollapsed('dashboard.camera')" class="camera-info-grid camera-status-grid">
              <div v-for="[key, value] in cameraStatusRows" :key="key" class="camera-info-item">
                <span>{{ fieldLabel(key) }}</span>
                <strong :class="statusTone(value)">{{ displayCell(value) }}</strong>
              </div>
              <div v-if="!cameraStatusRows.length" class="empty">{{ t("common.empty") }}</div>
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
              <thead><tr><th>{{ t("table.time") }}</th><th>{{ t("table.type") }}</th><th>{{ t("table.severity") }}</th><th>{{ t("table.current") }}</th><th>{{ t("table.message") }}</th><th>{{ t("table.actions") }}</th></tr></thead>
              <tbody>
                <tr v-if="!filteredEvents.length"><td colspan="6" class="empty">{{ t("common.empty") }}</td></tr>
                <tr v-for="item in filteredEvents" :key="`${item.source}-${item.id}`">
                  <td>{{ formatCell(item.created_at) }}</td>
                  <td>{{ eventTypeLabel(item) }}</td>
                  <td><span class="status-pill" :class="eventTone(item)"><span class="dot"></span>{{ displayCell(item.severity) }}</span></td>
                  <td>{{ eventCurrentLabel(item) }}</td>
                  <td>{{ eventMessage(item) }}</td>
                  <td><button class="text-action compact" type="button" @click="openEventDetails(item)">{{ t("table.details") }}</button></td>
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
        <div class="metric-grid small spool-detail-summary">
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
        <div class="toolbar ams-toolbar">
          <span class="toolbar-field-label">{{ t("ams.historyRange") }}</span>
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
                        <strong><span class="swatch" :style="{ background: filamentColor(slot.color) }"></span>{{ slotMaterialColorLabel(slot) }}</strong>
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
        <div class="inventory-tabs" role="tablist">
          <button
            v-for="item in inventoryPageOptions"
            :key="item.key"
            type="button"
            :class="{ active: inventoryPage === item.key }"
            @click="inventoryPage = item.key"
          >
            {{ item.label }}
          </button>
        </div>

        <template v-if="inventoryPage === 'stock'">
        <div class="metric-grid small">
          <div class="metric-card"><div class="metric-label">{{ t("inventory.totalStock") }}</div><div class="metric-value">{{ filamentInventoryKg(inventoryTotalWeightG) }}</div><div class="metric-foot">{{ inventoryTotalRolls }} {{ t("inventory.rolls") }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("inventory.skus") }}</div><div class="metric-value">{{ filamentInventorySummary?.totals.sku_count || 0 }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("inventory.sealedStock") }}</div><div class="metric-value">{{ filamentInventoryKg(inventorySealedWeightG) }}</div><div class="metric-foot">{{ filamentInventorySummary?.totals.sealed_quantity || 0 }} {{ t("inventory.rolls") }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("inventory.openedStock") }}</div><div class="metric-value">{{ filamentInventoryKg(inventoryRealSpoolWeightG) }}</div><div class="metric-foot">{{ inventoryRealSpools.length }} {{ t("inventory.rolls") }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("inventory.amsLoaded") }}</div><div class="metric-value">{{ filamentInventorySummary?.totals.ams_spool_count || 0 }}</div></div>
          <button class="metric-card metric-button" type="button" @click="jumpToInventorySection('inventory-pending-confirm')"><div class="metric-label">{{ t("inventory.pendingConfirm") }}</div><div class="metric-value">{{ inventoryPendingConfirmCount }}</div><div class="metric-foot">{{ t("inventory.jumpToPending") }}</div></button>
        </div>
        <div class="inventory-split-grid inventory-main-grid">
        <section class="panel inventory-panel">
          <div class="panel-header">
            <h3>{{ t("inventory.stockAnalysis") }}</h3>
            <button class="icon-button compact" type="button" :title="t('inventory.addSpool')" @click="openCreateFilamentSpoolDialog"><Plus :size="16" /></button>
          </div>
          <div class="inventory-visual-grid">
            <div class="inventory-pie" :style="inventoryTypePieStyle"><span>{{ filamentInventoryKg(inventoryTotalWeightG) }}</span></div>
            <div class="inventory-breakdown">
              <div class="slot-section-title">
                <h4>{{ t("inventory.typeBreakdown") }}</h4>
                <span>{{ filamentInventoryKg(inventoryTotalWeightG) }}</span>
              </div>
              <div v-if="!inventoryTypeBreakdown.length" class="slot-empty-state">{{ t("inventory.noStockData") }}</div>
              <div v-for="(row, index) in inventoryTypeBreakdown" :key="row.key" class="inventory-breakdown-row">
                <div class="inventory-breakdown-label"><strong>{{ row.label }}</strong><span>{{ filamentInventoryKg(row.grams) }} / {{ row.rolls }} {{ t("inventory.rolls") }}</span></div>
                <div class="inventory-bar"><span :style="{ width: `${Math.max(4, Math.round((row.grams / inventoryMaxTypeWeightG) * 100))}%`, background: inventoryChartColors[index % inventoryChartColors.length] }"></span></div>
              </div>
            </div>
          </div>
        </section>
        <section id="inventory-ams-loaded" class="panel">
          <div class="panel-header"><h3>{{ t("inventory.amsLoaded") }}</h3><Boxes :size="18" /></div>
          <div class="table-wrap">
            <table class="inventory-ams-table">
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('amsLoaded', 'printer')">{{ t("table.printer") }} <span>{{ inventorySortIndicator("amsLoaded", "printer") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('amsLoaded', 'slot')">{{ t("ams.slots") }} <span>{{ inventorySortIndicator("amsLoaded", "slot") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('amsLoaded', 'filament')">{{ t("table.filament") }} <span>{{ inventorySortIndicator("amsLoaded", "filament") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('amsLoaded', 'remaining')">{{ t("inventory.remaining") }} <span>{{ inventorySortIndicator("amsLoaded", "remaining") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('amsLoaded', 'status')">{{ t("table.status") }} <span>{{ inventorySortIndicator("amsLoaded", "status") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentAmsRows.length"><td colspan="6" class="empty">{{ t("ams.noSlots") }}</td></tr>
                <tr v-for="row in sortedFilamentAmsRows" :key="row.slot.id" :class="{ 'pending-row': row.spool && isFilamentSpoolPendingConfirm(row.spool) && !isFilamentSpoolSkuReviewDeferred(row.spool) }">
                  <td>{{ row.slot.printer_name || printerDisplayName(row.slot.printer_id) }}</td>
                  <td>{{ filamentAmsSlotLocationLabel(row.slot) }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(row.spool?.color_hex || row.spool?.color_value || row.slot.color || row.slot.tray_color) }"></span>{{ filamentAmsFilamentLabel(row.slot, row.spool) }}</td>
                  <td>{{ filamentAmsRemainingLabel(row.slot, row.spool) }}</td>
                  <td class="inventory-inline-action">
                    <span>{{ filamentAmsState(row.slot, row.spool) }}</span>
                    <span v-if="row.spool && isFilamentSpoolSkuReviewDeferred(row.spool)" class="muted small-text">{{ t("inventory.waitingRfidReviewShort") }}</span>
                    <button
                      v-else-if="row.spool && isFilamentSpoolPendingConfirm(row.spool)"
                      class="text-action compact"
                      type="button"
                      :title="t('inventory.confirmSkuTitle')"
                      @click.stop="openConfirmFilamentSpoolSku(row.spool)"
                    >
                      {{ t("inventory.confirmSku") }}
                    </button>
                  </td>
                  <td class="inventory-inline-action">
                    <button v-if="row.spool" class="icon-button compact" type="button" :title="t('common.edit')" @click="openFilamentSpoolDialog(row.spool)"><PencilLine :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </div>
        <div class="inventory-split-grid">
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.sealedStock") }}</h3><Archive :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('sealedStock', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("sealedStock", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('sealedStock', 'filament')">{{ t("table.filament") }} <span>{{ inventorySortIndicator("sealedStock", "filament") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('sealedStock', 'sealed')">{{ t("form.sealedQty") }} <span>{{ inventorySortIndicator("sealedStock", "sealed") }}</span></button></th>
                <th>{{ t("inventory.sealedWeight") }}</th>
                <th>{{ t("inventory.openedWeight") }}</th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentStockSkus.length"><td colspan="6" class="empty">{{ t("inventory.noSealedStock") }}</td></tr>
                <tr v-for="sku in sortedFilamentStockSkus" :key="sku.id">
                  <td>{{ sku.id }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(sku.color_hex || sku.color_value) }"></span>{{ filamentSkuLabel(sku) }}</td>
                  <td>{{ sku.sealed_quantity }}</td>
                  <td>{{ filamentWeight(skuSealedWeight(sku)) }}</td>
                  <td>{{ filamentWeight(skuOpenedWeight(sku)) }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('inventory.adjustStock')" @click="openSealedStockAdjust(sku)"><PencilLine :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.openedUnused") }}</h3><Archive :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('openedUnused', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("openedUnused", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('openedUnused', 'spool')">{{ t("table.spool") }} <span>{{ inventorySortIndicator("openedUnused", "spool") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('openedUnused', 'status')">{{ t("table.status") }} <span>{{ inventorySortIndicator("openedUnused", "status") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('openedUnused', 'remaining')">{{ t("inventory.remaining") }} <span>{{ inventorySortIndicator("openedUnused", "remaining") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('openedUnused', 'location')">{{ t("table.location") }} <span>{{ inventorySortIndicator("openedUnused", "location") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentOpenedUnusedSpools.length"><td colspan="6" class="empty">{{ t("inventory.noOpenedUnused") }}</td></tr>
                <tr v-for="spool in sortedFilamentOpenedUnusedSpools" :key="spool.id" :class="{ selected: selectedFilamentSpoolId === spool.id }">
                  <td>{{ spool.id }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(spool.color_hex || spool.color_value) }"></span>{{ filamentSpoolLabel(spool) }}</td>
                  <td>{{ filamentSpoolStatusLabel(spool.status) }}</td>
                  <td>{{ filamentSpoolRemainingLabel(spool) }}</td>
                  <td>{{ filamentSpoolLocation(spool) }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="openFilamentSpoolDialog(spool)"><PencilLine :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </div>
        <section v-if="inventoryPendingConfirmCount" id="inventory-pending-confirm" class="panel">
          <div class="panel-header"><h3>{{ t("inventory.pendingConfirm") }}</h3><AlertCircle :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('pendingConfirm', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("pendingConfirm", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('pendingConfirm', 'spool')">{{ t("table.spool") }} <span>{{ inventorySortIndicator("pendingConfirm", "spool") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('pendingConfirm', 'remaining')">{{ t("inventory.remaining") }} <span>{{ inventorySortIndicator("pendingConfirm", "remaining") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('pendingConfirm', 'location')">{{ t("table.location") }} <span>{{ inventorySortIndicator("pendingConfirm", "location") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('pendingConfirm', 'status')">{{ t("table.status") }} <span>{{ inventorySortIndicator("pendingConfirm", "status") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedPendingConfirmSpools.length"><td colspan="6" class="empty">{{ t("inventory.noPendingConfirm") }}</td></tr>
                <tr v-for="spool in sortedPendingConfirmSpools" :key="spool.id" class="pending-row">
                  <td>{{ spool.id }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(spool.color_hex || spool.color_value) }"></span>{{ filamentSpoolLabel(spool) }}</td>
                  <td>{{ filamentSpoolRemainingLabel(spool) }}</td>
                  <td>{{ filamentSpoolCurrentPlace(spool) }}</td>
                  <td>{{ filamentSpoolStatusLabel(spool.status) }}</td>
                  <td class="inventory-inline-action">
                    <button class="text-action compact" type="button" :title="t('inventory.confirmSkuTitle')" @click="openConfirmFilamentSpoolSku(spool)">{{ t("inventory.confirmSku") }}</button>
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="openFilamentSpoolDialog(spool)"><PencilLine :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        <section v-if="sortedNeedsLocationSpools.length" class="panel">
          <div class="panel-header"><h3>{{ t("inventory.needsLocation") }}</h3><Archive :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('needsLocation', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("needsLocation", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('needsLocation', 'spool')">{{ t("table.spool") }} <span>{{ inventorySortIndicator("needsLocation", "spool") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('needsLocation', 'location')">{{ t("table.location") }} <span>{{ inventorySortIndicator("needsLocation", "location") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('needsLocation', 'identity')">{{ t("inventory.identity") }} <span>{{ inventorySortIndicator("needsLocation", "identity") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="spool in sortedNeedsLocationSpools" :key="spool.id">
                  <td>{{ spool.id }}</td>
                  <td>{{ filamentSpoolLabel(spool) }}</td>
                  <td>{{ filamentSpoolLocation(spool) }}</td>
                  <td class="mono">{{ formatCell(spool.official_spool_uid || spool.identity_key) }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="openFilamentSpoolDialog(spool)"><PencilLine :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </template>

        <template v-else-if="inventoryPage === 'history'">
        <section class="panel">
          <div class="panel-header">
            <div>
              <h3>{{ t("inventory.historySpools") }}</h3>
              <p class="panel-subtitle">{{ t("inventory.historySpoolsSubtitle") }}</p>
            </div>
            <Archive :size="18" />
          </div>
          <div class="toolbar filters sku-filter-toolbar">
            <label class="search-field">
              <Search :size="16" />
              <input v-model="inventoryHistorySearch" :placeholder="t('inventory.searchHistorySpools')" />
            </label>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("history", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'spool')">{{ t("table.filament") }} <span>{{ inventorySortIndicator("history", "spool") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'status')">{{ t("table.status") }} <span>{{ inventorySortIndicator("history", "status") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'location')">{{ t("inventory.lastLocation") }} <span>{{ inventorySortIndicator("history", "location") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'remaining')">{{ t("inventory.remaining") }} <span>{{ inventorySortIndicator("history", "remaining") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'time')">{{ t("inventory.historyTime") }} <span>{{ inventorySortIndicator("history", "time") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('history', 'note')">{{ t("form.note") }} <span>{{ inventorySortIndicator("history", "note") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedHistoricalFilamentSpools.length"><td colspan="8" class="empty">{{ t("inventory.noHistorySpools") }}</td></tr>
                <tr v-for="spool in sortedHistoricalFilamentSpools" :key="spool.id">
                  <td>{{ spool.id }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(spool.color_hex || spool.color_value) }"></span>{{ filamentSpoolLabel(spool) }}</td>
                  <td>{{ filamentSpoolStatusLabel(spool.status) }}</td>
                  <td>{{ filamentSpoolLastLocation(spool) }}</td>
                  <td>{{ filamentSpoolRemainingLabel(spool) }}</td>
                  <td>{{ filamentSpoolHistoryTime(spool) }}</td>
                  <td>{{ formatCell(spool.note) }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="openFilamentSpoolDialog(spool)"><PencilLine :size="15" /></button>
                    <button class="text-action compact" type="button" @click="updateFilamentSpoolStatus(spool, 'opened_in_storage')">{{ t("inventory.restoreOpened") }}</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </template>

        <template v-else-if="inventoryPage === 'brands'">
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.brands") }}</h3><button class="icon-button compact" type="button" :title="t('inventory.addBrand')" @click="openFilamentBrandCreate"><Plus :size="16" /></button></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("brands", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'brand')">{{ t("form.brand") }} <span>{{ inventorySortIndicator("brands", "brand") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'aliases')">{{ t("inventory.aliases") }} <span>{{ inventorySortIndicator("brands", "aliases") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'typeSeries')">{{ t("inventory.typeSeries") }} <span>{{ inventorySortIndicator("brands", "typeSeries") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'skus')">{{ t("inventory.skus") }} <span>{{ inventorySortIndicator("brands", "skus") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'spools')">{{ t("inventory.spools") }} <span>{{ inventorySortIndicator("brands", "spools") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('brands', 'note')">{{ t("form.note") }} <span>{{ inventorySortIndicator("brands", "note") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentBrands.length"><td colspan="8" class="empty">{{ t("inventory.noBrands") }}</td></tr>
                <tr v-for="brand in sortedFilamentBrands" :key="brand.id">
                  <td>{{ brand.id }}</td>
                  <td>{{ brand.name }}</td>
                  <td>{{ (brand.aliases || []).join(", ") || "—" }}</td>
                  <td>{{ brand.type_series_count || 0 }}</td>
                  <td>{{ brand.sku_count || 0 }}</td>
                  <td>{{ brand.spool_count || 0 }}</td>
                  <td>{{ formatCell(brand.note) }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="editFilamentBrand(brand)"><PencilLine :size="15" /></button>
                    <button class="icon-button compact danger" type="button" :title="t('common.delete')" @click="deleteFilamentBrand(brand)"><Trash2 :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </template>

        <template v-else-if="inventoryPage === 'types'">
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.typeSeries") }}</h3><button class="icon-button compact" type="button" :title="t('inventory.addTypeSeries')" @click="openFilamentTypeSeriesCreate"><Plus :size="16" /></button></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('typeSeries', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("typeSeries", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('typeSeries', 'brand')">{{ t("form.brand") }} <span>{{ inventorySortIndicator("typeSeries", "brand") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('typeSeries', 'material')">{{ t("table.material") }} <span>{{ inventorySortIndicator("typeSeries", "material") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('typeSeries', 'emptyWeight')">{{ t("inventory.emptySpoolWeight") }} <span>{{ inventorySortIndicator("typeSeries", "emptyWeight") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('typeSeries', 'skus')">{{ t("inventory.skus") }} <span>{{ inventorySortIndicator("typeSeries", "skus") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('typeSeries', 'spools')">{{ t("inventory.spools") }} <span>{{ inventorySortIndicator("typeSeries", "spools") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentTypeSeries.length"><td colspan="7" class="empty">{{ t("inventory.noTypeSeries") }}</td></tr>
                <tr v-for="row in sortedFilamentTypeSeries" :key="row.id">
                  <td>{{ row.id }}</td>
                  <td>{{ filamentBrandDisplay(row.brands) }}</td>
                  <td>{{ filamentTypeSeriesLabel(row) }}</td>
                  <td>{{ filamentWeight(row.empty_spool_weight_g) }}</td>
                  <td>{{ row.sku_count }}</td>
                  <td>{{ row.spool_count }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="editFilamentTypeSeries(row)"><PencilLine :size="15" /></button>
                    <button class="icon-button compact danger" type="button" :title="t('common.delete')" @click="deleteFilamentTypeSeries(row)"><Trash2 :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </template>

        <template v-else-if="inventoryPage === 'skus'">
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.skus") }}</h3><button class="icon-button compact" type="button" :title="t('inventory.addSku')" @click="openFilamentSkuCreate"><Plus :size="16" /></button></div>
          <div class="toolbar filters sku-filter-toolbar">
            <label class="search-field">
              <Search :size="16" />
              <input v-model="filamentSkuFilters.search" :placeholder="t('inventory.searchSku')" />
            </label>
            <AppSelect v-model="filamentSkuFilters.brand_id" :options="filamentSkuFilterBrandOptions" />
            <AppSelect v-model="filamentSkuFilters.type_series_id" :options="filamentSkuFilterTypeSeriesOptions" />
            <AppSelect v-model="filamentSkuFilters.nominal_weight_g" :options="filamentSkuWeightOptions" />
            <AppSelect v-model="filamentSkuFilters.color_state" :options="filamentSkuColorStateOptions" />
            <button class="secondary" type="button" @click="resetFilamentSkuFilters">{{ t("common.clear") }}</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('skus', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("skus", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('skus', 'brand')">{{ t("form.brand") }} <span>{{ inventorySortIndicator("skus", "brand") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('skus', 'material')">{{ t("table.material") }} <span>{{ inventorySortIndicator("skus", "material") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('skus', 'color')">{{ t("inventory.officialColorName") }} <span>{{ inventorySortIndicator("skus", "color") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('skus', 'weight')">{{ t("inventory.nominalWeight") }} <span>{{ inventorySortIndicator("skus", "weight") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('skus', 'sealed')">{{ t("form.sealedQty") }} <span>{{ inventorySortIndicator("skus", "sealed") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilteredFilamentSkus.length"><td colspan="7" class="empty">{{ t("inventory.noSkuMatches") }}</td></tr>
                <tr v-for="sku in sortedFilteredFilamentSkus" :key="sku.id">
                  <td>{{ sku.id }}</td>
                  <td>{{ filamentBrandDisplay(sku.brands) }}</td>
                  <td>{{ filamentTypeSeriesDisplay(sku.type_series) }}</td>
                  <td>
                    <span class="swatch" :style="{ background: filamentColor(sku.color_hex || sku.color_value) }"></span>{{ filamentColorDisplay(sku.color_hex || sku.color_value, sku.color_name, sku) }}
                    <button v-if="colorNeedsMapping(sku.color_hex || sku.color_value, sku)" class="text-action compact" type="button" @click="startFilamentColorMapping(sku.color_hex || sku.color_value, sku)">{{ t("inventory.addOfficialName") }}</button>
                  </td>
                  <td>{{ filamentWeight(sku.nominal_weight_g) }}</td>
                  <td>{{ sku.sealed_quantity }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="editFilamentSku(sku)"><PencilLine :size="15" /></button>
                    <button class="icon-button compact danger" type="button" :title="t('common.delete')" @click="deleteFilamentSku(sku)"><Trash2 :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </template>

        <template v-else-if="inventoryPage === 'colors'">
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.colorMappings") }}</h3><button class="icon-button compact" type="button" :title="t('inventory.addColorMapping')" @click="openFilamentColorMappingCreate"><Plus :size="16" /></button></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorMappings', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("colorMappings", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorMappings', 'brand')">{{ t("form.brand") }} <span>{{ inventorySortIndicator("colorMappings", "brand") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorMappings', 'material')">{{ t("table.material") }} <span>{{ inventorySortIndicator("colorMappings", "material") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorMappings', 'hex')">{{ t("inventory.hexValue") }} <span>{{ inventorySortIndicator("colorMappings", "hex") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorMappings', 'color')">{{ t("inventory.officialColorName") }} <span>{{ inventorySortIndicator("colorMappings", "color") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorMappings', 'note')">{{ t("form.note") }} <span>{{ inventorySortIndicator("colorMappings", "note") }}</span></button></th>
                <th>{{ t("table.actions") }}</th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentColorMappings.length"><td colspan="7" class="empty">{{ t("inventory.noColorMappings") }}</td></tr>
                <tr v-for="mapping in sortedFilamentColorMappings" :key="mapping.id">
                  <td>{{ mapping.id }}</td>
                  <td>{{ formatCell(mapping.brand_name) }}</td>
                  <td>{{ formatCell(mapping.material_type || mapping.material) }} / {{ formatCell(mapping.series_name || mapping.series) }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(mapping.color_hex || mapping.hex_value) }"></span><span class="mono">{{ mapping.color_hex || mapping.hex_value }}</span></td>
                  <td>{{ mapping.color_name || mapping.official_name }}</td>
                  <td>{{ formatCell(mapping.note) }}</td>
                  <td class="inventory-inline-action">
                    <button class="icon-button compact" type="button" :title="t('common.edit')" @click="editFilamentColorMapping(mapping)"><PencilLine :size="15" /></button>
                    <button class="icon-button compact danger" type="button" :title="t('common.delete')" @click="deleteFilamentColorMapping(mapping)"><Trash2 :size="15" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="panel">
          <div class="panel-header"><h3>{{ t("inventory.incompleteSkuColors") }}</h3><Archive :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorGaps', 'id')">{{ t("table.id") }} <span>{{ inventorySortIndicator("colorGaps", "id") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorGaps', 'brand')">{{ t("form.brand") }} <span>{{ inventorySortIndicator("colorGaps", "brand") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorGaps', 'material')">{{ t("table.material") }} <span>{{ inventorySortIndicator("colorGaps", "material") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorGaps', 'color')">{{ t("inventory.officialColorName") }} <span>{{ inventorySortIndicator("colorGaps", "color") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorGaps', 'hex')">{{ t("inventory.hexValue") }} <span>{{ inventorySortIndicator("colorGaps", "hex") }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleInventorySort('colorGaps', 'source')">{{ t("inventory.source") }} <span>{{ inventorySortIndicator("colorGaps", "source") }}</span></button></th>
              </tr></thead>
              <tbody>
                <tr v-if="!sortedFilamentColorMappingGaps.length"><td colspan="6" class="empty">{{ t("inventory.noColorGaps") }}</td></tr>
                <tr v-for="row in sortedFilamentColorMappingGaps" :key="row.sku_id">
                  <td>{{ row.sku_id }}</td>
                  <td>{{ filamentBrandDisplay(row.brands) }}</td>
                  <td>{{ filamentTypeSeriesDisplay(row.type_series) }}</td>
                  <td>{{ formatCell(row.color_name) }}</td>
                  <td><span class="swatch" :style="{ background: filamentColor(row.color_hex) }"></span><span class="mono">{{ formatCell(row.color_hex) }}</span></td>
                  <td>{{ row.missing.join(", ") }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        </template>

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
            <div class="network-info-item"><span>{{ t("debug.memory") }}</span><strong>{{ formatBytes(Number(systemInfo?.memory?.project_rss_bytes || systemInfo?.memory?.rss_bytes || 0)) }}</strong></div>
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
          <p class="panel-subtitle">{{ t("export.backupHint") }}</p>
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
        <section class="panel export-panel">
          <div class="panel-header"><h3>{{ t("export.importTitle") }}</h3><Upload :size="18" /></div>
          <p class="panel-subtitle">{{ t("export.importHint") }}</p>
          <div class="export-controls">
            <AppSelect v-model="importOptions.mode" :options="importModeOptions" />
            <button class="primary" type="button" @click="importFileInput?.click()"><Upload :size="17" />{{ t("export.importJson") }}</button>
            <input ref="importFileInput" class="hidden-file-input" type="file" accept="application/json,.json" @change="importBackupFile" />
          </div>
          <pre v-if="importResult" class="json-block import-result">{{ JSON.stringify(importResult.counts || importResult, null, 2) }}</pre>
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

    <div v-if="cameraLightboxOpen" class="modal-backdrop camera-lightbox-backdrop" @click.self="closeCameraLightbox">
      <section class="modal-panel camera-lightbox-modal">
        <div class="modal-header">
          <div class="modal-title-stack">
            <h3>{{ t("dashboard.liveCamera") }}</h3>
            <p>{{ selectedPrinter?.name || t("dashboard.cameraStreamForwarding") }}</p>
          </div>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeCameraLightbox"><X :size="17" /></button>
        </div>
        <div class="camera-lightbox-frame">
          <img
            v-if="cameraStreamSrc && !cameraStreamError"
            :src="cameraStreamSrc"
            :alt="t('dashboard.liveCamera')"
            @error="handleCameraStreamError"
            @load="handleCameraStreamLoaded"
          />
          <div v-else class="camera-live-placeholder">
            <Camera :size="34" />
            <strong>{{ cameraLivePlaceholder }}</strong>
            <span>{{ t("dashboard.cameraStreamForwarding") }}</span>
          </div>
        </div>
        <div class="camera-lightbox-footer">
          <span>{{ t("dashboard.cameraStreamForwarding") }}</span>
          <div class="camera-live-actions">
            <button class="secondary" type="button" @click="restartCameraStream"><RefreshCw :size="16" />{{ t("dashboard.restartCameraStream") }}</button>
            <button class="primary" type="button" @click="closeCameraLightbox">{{ t("common.close") }}</button>
          </div>
        </div>
      </section>
    </div>

    <div v-if="inventoryDialog.key" class="modal-backdrop" @click.self="closeInventoryDialog">
      <section v-if="inventoryDialog.key === 'brand'" class="modal-panel">
        <div class="modal-header">
          <h3>{{ editingFilamentBrandId ? t("inventory.editBrand") : t("inventory.addBrand") }}</h3>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <form class="form-grid compact-form modal-form" @submit.prevent="saveFilamentBrand">
          <label class="field-label"><span>{{ t("form.brand") }}</span><input v-model="filamentBrandForm.name" :placeholder="t('form.brand')" /></label>
          <label class="field-label"><span>{{ t("inventory.aliases") }}</span><input v-model="filamentBrandForm.aliases" :placeholder="t('inventory.aliases')" /></label>
          <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="filamentBrandForm.note" :placeholder="t('form.note')" /></label>
          <div class="modal-actions">
            <button class="secondary" type="button" @click="closeInventoryDialog">{{ t("common.cancel") }}</button>
            <button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button>
          </div>
        </form>
      </section>

      <section v-else-if="inventoryDialog.key === 'typeSeries'" class="modal-panel">
        <div class="modal-header">
          <h3>{{ editingFilamentTypeSeriesId ? t("inventory.editTypeSeries") : t("inventory.addTypeSeries") }}</h3>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <form class="form-grid compact-form modal-form" @submit.prevent="saveFilamentTypeSeries">
          <label class="field-label"><span>{{ t("form.brand") }}</span><AppSelect v-model="filamentTypeSeriesForm.brand_id" :options="filamentRequiredBrandOptions" :placeholder="t('form.brand')" /></label>
          <label class="field-label"><span>{{ t("form.material") }}</span><input v-model="filamentTypeSeriesForm.material_type" :placeholder="t('form.material')" /></label>
          <label class="field-label"><span>{{ t("form.series") }}</span><input v-model="filamentTypeSeriesForm.series_name" :placeholder="t('form.series')" /></label>
          <label class="field-label"><span>{{ t("inventory.emptySpoolWeight") }}</span><input v-model.number="filamentTypeSeriesForm.empty_spool_weight_g" type="number" min="0" :placeholder="t('inventory.emptySpoolWeight')" /></label>
          <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="filamentTypeSeriesForm.note" :placeholder="t('form.note')" /></label>
          <div class="modal-actions">
            <button class="secondary" type="button" @click="closeInventoryDialog">{{ t("common.cancel") }}</button>
            <button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button>
          </div>
        </form>
      </section>

      <section v-else-if="inventoryDialog.key === 'sku'" class="modal-panel">
        <div class="modal-header">
          <h3>{{ editingFilamentSkuId ? t("inventory.editSku") : t("inventory.addSku") }}</h3>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <form class="form-grid compact-form modal-form" @submit.prevent="saveFilamentSku">
          <label class="field-label"><span>{{ t("inventory.typeSeries") }}</span><AppSelect v-model="filamentSkuForm.type_series_id" :options="filamentTypeSeriesOptions" :placeholder="t('inventory.typeSeries')" /></label>
          <label class="field-label"><span>{{ t("inventory.officialColorName") }}</span><input v-model="filamentSkuForm.color_name" :placeholder="t('inventory.officialColorName')" /></label>
          <label class="field-label"><span>{{ t("inventory.hexValue") }}</span><input v-model="filamentSkuForm.color_value" :placeholder="t('inventory.hexValue')" /></label>
          <label class="field-label"><span>{{ t("inventory.nominalWeight") }}</span><input v-model.number="filamentSkuForm.nominal_weight_g" type="number" min="0" :placeholder="t('inventory.nominalWeight')" /></label>
          <label class="field-label"><span>{{ t("inventory.diameter") }}</span><input v-model.number="filamentSkuForm.filament_diameter_mm" type="number" min="0.1" step="0.01" :placeholder="t('inventory.diameter')" /></label>
          <label class="field-label"><span>{{ t("inventory.trayInfoIdx") }}</span><input v-model="filamentSkuForm.tray_info_idx" :placeholder="t('inventory.trayInfoIdx')" /></label>
          <label class="field-label"><span>{{ t("form.sealedQty") }}</span><input v-model.number="filamentSkuForm.sealed_quantity" type="number" min="0" :placeholder="t('form.sealedQty')" /></label>
          <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="filamentSkuForm.note" :placeholder="t('form.note')" /></label>
          <div class="modal-actions">
            <button class="secondary" type="button" @click="cancelFilamentSkuEdit">{{ t("common.cancel") }}</button>
            <button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button>
          </div>
        </form>
      </section>

      <section v-else-if="inventoryDialog.key === 'colorMapping'" class="modal-panel">
        <div class="modal-header">
          <h3>{{ editingFilamentColorMappingId ? t("inventory.editColorMapping") : t("inventory.addColorMapping") }}</h3>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <form class="form-grid compact-form modal-form" @submit.prevent="saveFilamentColorMapping">
          <label class="field-label"><span>{{ t("form.brand") }}</span><AppSelect v-model="filamentColorMappingForm.brand_id" :options="filamentRequiredBrandOptions" /></label>
          <label class="field-label"><span>{{ t("inventory.typeSeries") }}</span><AppSelect v-model="filamentColorMappingForm.type_series_id" :options="filamentColorMappingTypeSeriesOptions" /></label>
          <label class="field-label"><span>{{ t("inventory.hexValue") }}</span><input v-model="filamentColorMappingForm.hex_value" :placeholder="t('inventory.hexValue')" /></label>
          <label class="field-label"><span>{{ t("inventory.officialColorName") }}</span><input v-model="filamentColorMappingForm.official_name" :placeholder="t('inventory.officialColorName')" /></label>
          <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="filamentColorMappingForm.note" :placeholder="t('form.note')" /></label>
          <div class="modal-actions">
            <button class="secondary" type="button" @click="closeInventoryDialog">{{ t("common.cancel") }}</button>
            <button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button>
          </div>
        </form>
      </section>

      <section v-else-if="inventoryDialog.key === 'stockAdjust'" class="modal-panel">
        <div class="modal-header">
          <div class="modal-title-stack">
            <h3>{{ t("inventory.adjustStock") }}</h3>
            <p>{{ inventoryDialogSkuLabel() }}</p>
          </div>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <form class="form-grid compact-form modal-form" @submit.prevent="saveSealedStockAdjust">
          <label class="field-label"><span>{{ t("inventory.currentSealedQty") }}</span><input :value="sealedStockAdjustForm.current_quantity" disabled :placeholder="t('inventory.currentSealedQty')" /></label>
          <label class="field-label"><span>{{ t("inventory.targetSealedQty") }}</span><input v-model.number="sealedStockAdjustForm.target_quantity" type="number" min="0" :placeholder="t('inventory.targetSealedQty')" /></label>
          <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="sealedStockAdjustForm.note" :placeholder="t('form.note')" /></label>
          <div class="modal-actions">
            <button class="secondary" type="button" @click="closeInventoryDialog">{{ t("common.cancel") }}</button>
            <button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button>
          </div>
        </form>
      </section>

      <section v-else-if="inventoryDialog.key === 'spoolCreate'" class="modal-panel wide-modal">
        <div class="modal-header">
          <h3>{{ t("inventory.addSpool") }}</h3>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <form class="form-grid compact-form modal-form" @submit.prevent="createFilamentSpool">
          <label class="field-label"><span>{{ t("form.brand") }}</span><AppSelect v-model="filamentSpoolForm.brand_id" :options="filamentSpoolBrandOptions" :placeholder="t('form.brand')" /></label>
          <label class="field-label"><span>{{ t("inventory.typeSeries") }}</span><AppSelect v-model="filamentSpoolForm.type_series_id" :options="filamentSpoolTypeSeriesOptions" :placeholder="t('inventory.typeSeries')" /></label>
          <label class="field-label"><span>{{ t("inventory.skus") }}</span><AppSelect v-model="filamentSpoolForm.sku_id" :options="filamentSpoolSkuOptions" :placeholder="t('inventory.skus')" /></label>
          <label class="field-label"><span>{{ t("table.status") }}</span><AppSelect v-model="filamentSpoolForm.status" :options="filamentSpoolStatusOptions" /></label>
          <label class="field-label"><span>{{ t("fields.tray_uuid") }}</span><input v-model="filamentSpoolForm.tray_uuid" :placeholder="t('fields.tray_uuid')" /></label>
          <label class="field-label"><span>{{ t("fields.tag_uid") }}</span><input v-model="filamentSpoolForm.tag_uid" :placeholder="t('fields.tag_uid')" /></label>
          <label class="field-label"><span>{{ t("inventory.remainingWeight") }}</span><input v-model.number="filamentSpoolForm.current_remaining_g" type="number" min="0" :placeholder="t('inventory.remainingWeight')" /></label>
          <label class="field-label"><span>{{ t("inventory.manualLocation") }}</span><input v-model="filamentSpoolForm.manual_location" :placeholder="t('inventory.manualLocation')" /></label>
          <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="filamentSpoolForm.note" :placeholder="t('form.note')" /></label>
          <div class="modal-actions">
            <button class="secondary" type="button" @click="closeInventoryDialog">{{ t("common.cancel") }}</button>
            <button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button>
          </div>
        </form>
      </section>

      <section v-else-if="inventoryDialog.key === 'spoolDetail' && selectedFilamentSpool" class="modal-panel wide-modal">
        <div class="modal-header">
          <div class="modal-title-stack">
            <h3>{{ t("inventory.spoolDetail") }}</h3>
            <p>{{ inventoryDialogSpoolLabel() }}</p>
          </div>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <div class="metric-grid small">
          <div class="metric-card"><div class="metric-label">{{ t("table.spool") }}</div><div class="metric-value compact-value">{{ filamentSpoolLabel(selectedFilamentSpool) }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("inventory.remaining") }}</div><div class="metric-value compact-value">{{ filamentWeight(filamentSpoolRemainingWeight(selectedFilamentSpool)) }}</div><div class="metric-foot">{{ filamentRemainPercent(selectedFilamentSpool) }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("table.location") }}</div><div class="metric-value compact-value">{{ filamentSpoolLocation(selectedFilamentSpool) }}</div></div>
          <div class="metric-card"><div class="metric-label">{{ t("table.status") }}</div><div class="metric-value compact-value">{{ filamentSpoolStatusLabel(selectedFilamentSpool.status) }}</div></div>
        </div>
        <div v-if="isFilamentSpoolPendingConfirm(selectedFilamentSpool)" class="modal-note">
          <span>{{ t("inventory.confirmSkuTitle") }}</span>
          <button class="secondary" type="button" @click="openConfirmFilamentSpoolSku(selectedFilamentSpool)">{{ t("inventory.confirmSku") }}</button>
        </div>
        <div class="spool-status-actions">
          <button
            v-if="selectedFilamentSpool.status !== 'empty' && selectedFilamentSpool.status !== 'archived'"
            class="secondary"
            type="button"
            @click="updateFilamentSpoolStatus(selectedFilamentSpool, 'empty')"
          >
            {{ t("inventory.markEmpty") }}
          </button>
          <button
            v-if="selectedFilamentSpool.status !== 'archived'"
            class="secondary"
            type="button"
            @click="updateFilamentSpoolStatus(selectedFilamentSpool, 'archived')"
          >
            {{ t("inventory.archiveSpool") }}
          </button>
          <button
            v-if="selectedFilamentSpool.status === 'empty' || selectedFilamentSpool.status === 'archived'"
            class="primary"
            type="button"
            @click="updateFilamentSpoolStatus(selectedFilamentSpool, 'opened_in_storage')"
          >
            <CheckCircle2 :size="17" />{{ t("inventory.restoreOpened") }}
          </button>
        </div>
        <div class="spool-dialog-forms">
          <form class="modal-subform" @submit.prevent="adjustSelectedFilamentQuantity">
            <h4>{{ t("inventory.quantityAdjust") }}</h4>
            <div class="spool-adjust-grid">
              <label class="field-label"><span>{{ t("inventory.remainingWeight") }}</span><input v-model.number="quantityAdjustForm.current_remaining_g" type="number" min="0" :placeholder="t('inventory.remainingWeight')" /></label>
              <label class="field-label"><span>{{ t("inventory.remainPercent") }}</span><input v-model.number="quantityAdjustForm.remain_percent" type="number" min="0" max="100" :placeholder="t('inventory.remainPercent')" /></label>
              <label class="field-label"><span>{{ t("inventory.source") }}</span><AppSelect v-model="quantityAdjustForm.source" :options="quantityAdjustSourceOptions" /></label>
              <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="quantityAdjustForm.note" :placeholder="t('form.note')" /></label>
            </div>
            <div class="modal-actions"><button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button></div>
          </form>
          <form class="modal-subform" @submit.prevent="updateSelectedFilamentLocation">
            <h4>{{ t("inventory.locationAdjust") }}</h4>
            <div class="spool-adjust-grid">
              <label class="field-label"><span>{{ t("table.printer") }}</span><AppSelect v-model="locationAdjustForm.printer_id" :options="locationPrinterOptions" :placeholder="t('table.printer')" /></label>
              <label class="field-label"><span>{{ t("fields.ams_id") }}</span><input v-model="locationAdjustForm.ams_id" :placeholder="t('fields.ams_id')" /></label>
              <label class="field-label"><span>{{ t("form.slotId") }}</span><input v-model="locationAdjustForm.tray_id" :placeholder="t('form.slotId')" /></label>
              <label class="field-label"><span>{{ t("inventory.manualLocation") }}</span><input v-model="locationAdjustForm.manual_location" :placeholder="t('inventory.manualLocation')" /></label>
              <label class="field-label"><span>{{ t("form.note") }}</span><input v-model="locationAdjustForm.note" :placeholder="t('form.note')" /></label>
            </div>
            <div class="modal-actions"><button class="primary" type="submit"><Save :size="17" />{{ t("common.save") }}</button></div>
          </form>
        </div>
      </section>

      <section v-else-if="inventoryDialog.key === 'skuConfirm'" class="modal-panel">
        <div class="modal-header">
          <div class="modal-title-stack">
            <h3>{{ t("inventory.confirmSku") }}</h3>
            <p>{{ inventoryDialogSpoolLabel() }}</p>
          </div>
          <button class="icon-button" type="button" :title="t('common.close')" @click="closeInventoryDialog"><X :size="17" /></button>
        </div>
        <dl class="kv compact">
          <dt>{{ t("table.spool") }}</dt><dd>{{ inventoryDialogSpoolLabel() }}</dd>
          <dt>{{ t("inventory.identity") }}</dt><dd class="mono">{{ formatCell(inventoryDialog.context?.official_spool_uid || inventoryDialog.context?.identity_key) }}</dd>
          <dt>{{ t("inventory.remaining") }}</dt><dd>{{ filamentSpoolRemainingLabel(inventoryDialog.context) }}</dd>
        </dl>
        <div class="modal-note">{{ filamentSkuReviewDescription(inventoryDialog.context) }}</div>
        <div v-if="inventoryDialog.context && filamentSpoolNeedsUidConflictResolution(inventoryDialog.context)" class="modal-actions">
          <button class="secondary" type="button" @click="resolveFilamentUidConflict(inventoryDialog.context, 'restore_old')">{{ t("inventory.restoreHistoricalSpool") }}</button>
          <button class="secondary" type="button" @click="resolveFilamentUidConflict(inventoryDialog.context, 'create_new')">{{ t("inventory.createNewSpool") }}</button>
          <button class="secondary" type="button" @click="resolveFilamentUidConflict(inventoryDialog.context, 'ignore')">{{ t("inventory.ignoreRecognition") }}</button>
        </div>
        <div v-else class="modal-actions">
          <button class="secondary" type="button" @click="editSkuFromConfirmDialog">{{ t("inventory.editSku") }}</button>
          <button class="primary" type="button" @click="inventoryDialog.context && confirmFilamentSpoolSku(inventoryDialog.context)"><CheckCircle2 :size="17" />{{ t("inventory.confirmSku") }}</button>
        </div>
      </section>
    </div>

    <div v-if="selectedEvent" class="modal-backdrop" @click.self="selectedEvent = null">
      <section class="modal-panel event-detail-modal">
        <div class="modal-header">
          <div class="modal-title-stack">
            <h3>{{ t("events.details") }} · {{ eventTypeLabel(selectedEvent) }}</h3>
            <p>{{ formatCell(selectedEvent.created_at) }}</p>
          </div>
          <button class="icon-button" type="button" :title="t('common.close')" @click="selectedEvent = null"><X :size="17" /></button>
        </div>
        <dl class="kv compact">
          <dt>{{ t("table.type") }}</dt><dd>{{ eventTypeLabel(selectedEvent) }}</dd>
          <dt>{{ t("table.severity") }}</dt><dd>{{ displayCell(selectedEvent.severity) }}</dd>
          <dt>{{ t("table.current") }}</dt><dd>{{ eventCurrentLabel(selectedEvent) }}</dd>
          <dt>{{ t("table.message") }}</dt><dd>{{ eventMessage(selectedEvent) }}</dd>
          <dt>{{ t("events.rawMessage") }}</dt><dd>{{ eventRawMessage(selectedEvent) }}</dd>
          <dt>{{ t("table.printer") }}</dt><dd>{{ printerDisplayName(selectedEvent.printer_id) }}</dd>
          <dt>{{ t("table.spool") }}</dt><dd>{{ formatCell(selectedEvent.spool_id) }}</dd>
          <dt>{{ t("events.source") }}</dt><dd>{{ displayCell(selectedEvent.source) }}</dd>
        </dl>
        <div class="event-raw-block">
          <h4>{{ t("events.rawData") }}</h4>
          <pre>{{ prettyJson(selectedEvent.data) }}</pre>
        </div>
      </section>
    </div>

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
              <small>{{ slotColorLabel(selectedSlot) }}</small>
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
                <td><span class="swatch" :style="{ background: filamentColor(sample.color) }"></span>{{ filamentColorDisplay(sample.color) }}</td>
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
