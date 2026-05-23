import { computed, reactive, ref } from "vue";
import { acceptHMRUpdate, defineStore, storeToRefs } from "pinia";
import { API_BASE, apiRequest } from "../api";
import type { DatabaseRetentionStatus, RawMqttArchive, RawMqttDbLimit, SystemInfo, UnifiedEvent } from "../types";
import { useEventsStore } from "./events";
import { useI18nStore } from "./i18n";
import { useNavigationStore } from "./navigation";
import { usePreferencesStore } from "./preferences";
import { usePresentationStore } from "./presentation";
import { usePrintersStore } from "./printers";
import { useUiStore } from "./ui";

export const useDebugStore = defineStore("debug", () => {
  const uiStore = useUiStore();
  const { message } = storeToRefs(uiStore);
  const { t } = useI18nStore();
  const { withLoading } = uiStore;
  const preferencesStore = () => usePreferencesStore();
  const navigationStore = () => useNavigationStore();
  const printersStore = () => usePrintersStore();
  const eventsStore = () => useEventsStore();
  const presentationStore = () => usePresentationStore();

  const rawMqtt = ref<Record<string, any>[]>([]);
  const rawMqttArchives = ref<RawMqttArchive[]>([]);

  const systemInfo = ref<SystemInfo | null>(null);
  const databaseRetention = ref<DatabaseRetentionStatus | null>(null);
  const pendingRawMqttDbLimit = ref<RawMqttDbLimit>("5gb");

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

  const rawMqttDbLimitOptions = computed(() => [
    { label: t("debug.retentionLimit1gb"), value: "1gb" },
    { label: t("debug.retentionLimit5gb"), value: "5gb" },
    { label: t("debug.retentionLimit10gb"), value: "10gb" },
    { label: t("debug.retentionLimit20gb"), value: "20gb" },
    { label: t("debug.retentionLimitUnlimited"), value: "unlimited" },
  ]);

  const databaseRetentionLastCleanupLabel = computed(() => {
    const cleanup = databaseRetention.value?.last_cleanup;
    if (!cleanup) return t("common.empty");
    if (cleanup.error) return t("debug.retentionCleanupError");
    if (cleanup.blocked_non_raw_size) return t("debug.retentionCleanupBlocked");
    if (cleanup.skipped_reason) return t("debug.retentionCleanupSkipped", { reason: cleanup.skipped_reason });
    return t("debug.retentionCleanupArchived", { count: cleanup.archived_rows ?? cleanup.deleted_rows });
  });


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

  async function loadDebug() {
    const [raw, archiveResult, eventResult, infoResult, retentionResult] = await Promise.all([
      apiRequest<Record<string, any>[]>("/debug/raw-mqtt?limit=20"),
      apiRequest<RawMqttArchive[]>("/debug/raw-mqtt-archives?limit=20"),
      apiRequest<UnifiedEvent[]>("/events?limit=80"),
      apiRequest<SystemInfo>("/system/info"),
      apiRequest<DatabaseRetentionStatus>("/debug/database-retention"),
    ]);
    rawMqtt.value = raw;
    rawMqttArchives.value = archiveResult;
    eventsStore().events = eventResult;
    systemInfo.value = infoResult;
    updateDatabaseRetention(retentionResult);
  }


  async function saveRawMqttDbLimit(value: string | number | null) {
    const next = String(value || "5gb") as RawMqttDbLimit;
    const previous = databaseRetention.value?.raw_mqtt_db_limit || "5gb";
    pendingRawMqttDbLimit.value = next;
    if (rawMqttLimitWouldCleanup(next)) {
      const confirmed = window.confirm(t("debug.retentionLimitConfirm"));
      if (!confirmed) {
        pendingRawMqttDbLimit.value = previous;
        return;
      }
    }
    await withLoading(async () => {
      const result = await apiRequest<DatabaseRetentionStatus>("/debug/database-retention", {
        method: "PATCH",
        body: JSON.stringify({ raw_mqtt_db_limit: next }),
      });
      updateDatabaseRetention(result);
    });
  }


  async function enforceDatabaseRetention() {
    await withLoading(async () => {
      const result = await apiRequest<DatabaseRetentionStatus>("/debug/database-retention/enforce", { method: "POST" });
      updateDatabaseRetention(result);
      rawMqttArchives.value = await apiRequest<RawMqttArchive[]>("/debug/raw-mqtt-archives?limit=20");
      rawMqtt.value = await apiRequest<Record<string, any>[]>("/debug/raw-mqtt?limit=20");
    });
  }


  async function downloadRawMqttArchive(archive: RawMqttArchive) {
    await withLoading(async () => {
      const response = await fetch(`${API_BASE}/debug/raw-mqtt-archives/${archive.id}/download`);
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = archive.file_path.split("/").pop() || `raw-mqtt-archive-${archive.id}.zip`;
      link.click();
      URL.revokeObjectURL(url);
    });
  }


  async function downloadSupportBundle() {
    await withLoading(async () => {
      const bundle = await apiRequest<Record<string, any>>("/support/bundle");
      bundle.frontend = {
        ...(presentationStore().record(bundle.frontend)),
        browser: window.navigator.userAgent,
        language: window.navigator.language,
        downloaded_at: new Date().toISOString(),
        experimental_features: { ...preferencesStore().experimentalFeatures },
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
        await printersStore().refreshPrinters();
        await navigationStore().loadCurrent();
        message.value = t("export.importComplete");
      });
    } catch (error) {
      message.value = error instanceof Error ? error.message : String(error);
    } finally {
      input.value = "";
    }
  }


  function toggleExportSection(key: string, enabled: boolean) {
    if (enabled && !exportOptions.sections.includes(key)) exportOptions.sections.push(key);
    if (!enabled) exportOptions.sections = exportOptions.sections.filter((item) => item !== key);
  }

  function updateDatabaseRetention(result: DatabaseRetentionStatus) {
    databaseRetention.value = result;
    pendingRawMqttDbLimit.value = result.raw_mqtt_db_limit;
  }


  function rawMqttLimitWouldCleanup(limit: RawMqttDbLimit) {
    if (limit === "unlimited") return false;
    const size = databaseRetention.value?.database_size_bytes || 0;
    const limitBytes = {
      "1gb": 1 * 1024 ** 3,
      "5gb": 5 * 1024 ** 3,
      "10gb": 10 * 1024 ** 3,
      "20gb": 20 * 1024 ** 3,
      unlimited: null,
    }[limit];
    return Boolean(limitBytes && size >= limitBytes * 1.05 && (databaseRetention.value?.raw_mqtt_row_count || 0) > 0);
  }


  return {
    rawMqtt,
    rawMqttArchives,
    systemInfo,
    databaseRetention,
    pendingRawMqttDbLimit,
    exportOptions,
    importOptions,
    importFileInput,
    importResult,
    rawMqttDbLimitOptions,
    databaseRetentionLastCleanupLabel,
    exportSectionItems,
    importModeOptions,
    loadDebug,
    saveRawMqttDbLimit,
    enforceDatabaseRetention,
    downloadRawMqttArchive,
    downloadSupportBundle,
    downloadExport,
    importBackupFile,
    toggleExportSection,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useDebugStore, import.meta.hot));
}
