import { computed, reactive, ref } from "vue";
import { acceptHMRUpdate, defineStore, storeToRefs } from "pinia";
import { apiRequest, numeric } from "../api";
import type { MaintenanceOverview, PrinterMaintenance } from "../types";
import { useI18nStore } from "./i18n";
import { usePrintersStore } from "./printers";
import { useUiStore } from "./ui";

export const useMaintenanceStore = defineStore("maintenance", () => {
  const uiStore = useUiStore();
  const { message } = storeToRefs(uiStore);
  const { t } = useI18nStore();
  const { withLoading } = uiStore;
  const printersStore = () => usePrintersStore();

  const maintenanceOverview = ref<MaintenanceOverview | null>(null);

  const maintenanceItems = ref<PrinterMaintenance[]>([]);

  const maintenanceNotes = reactive<Record<number, string>>({});

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

  async function loadMaintenance() {
    const [overviewResult, itemResult] = await Promise.all([
      apiRequest<MaintenanceOverview>("/maintenance/overview"),
      printersStore().selectedPrinterId
        ? apiRequest<PrinterMaintenance[]>(`/printers/${printersStore().selectedPrinterId}/maintenance`)
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


  return {
    maintenanceOverview,
    maintenanceItems,
    maintenanceNotes,
    maintenanceStats,
    maintenanceStatusGroups,
    maintenanceHealthPercent,
    selectedPrinterPrintHours,
    loadMaintenance,
    performMaintenance,
    maintenanceTone,
    maintenanceProgress,
    maintenanceRemainingLabel,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useMaintenanceStore, import.meta.hot));
}
