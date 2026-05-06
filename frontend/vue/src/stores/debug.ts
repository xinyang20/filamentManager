import { computed, reactive, ref } from "vue";
import { acceptHMRUpdate, defineStore, storeToRefs } from "pinia";
import { API_BASE, apiRequest } from "../api";
import type { SystemInfo, UnifiedEvent } from "../types";
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

  const systemInfo = ref<SystemInfo | null>(null);

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
    const [raw, eventResult, infoResult] = await Promise.all([
      apiRequest<Record<string, any>[]>("/debug/raw-mqtt?limit=20"),
      apiRequest<UnifiedEvent[]>("/events?limit=80"),
      apiRequest<SystemInfo>("/system/info"),
    ]);
    rawMqtt.value = raw;
    eventsStore().events = eventResult;
    systemInfo.value = infoResult;
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


  return {
    rawMqtt,
    systemInfo,
    exportOptions,
    importOptions,
    importFileInput,
    importResult,
    exportSectionItems,
    importModeOptions,
    loadDebug,
    downloadSupportBundle,
    downloadExport,
    importBackupFile,
    toggleExportSection,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useDebugStore, import.meta.hot));
}
