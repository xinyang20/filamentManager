import { ref, watch } from "vue";
import { acceptHMRUpdate, defineStore, storeToRefs } from "pinia";
import { type InventoryPageKey, type ViewKey } from "../app/navigation";
import { isFilamentManagementView, resolveInitialInventoryPage, resolveInitialView as resolveStoredInitialView } from "../app/preferences";
import { useAmsStore } from "./ams";
import { useDashboardStore } from "./dashboard";
import { useDebugStore } from "./debug";
import { useEventsStore } from "./events";
import { useInventoryStore } from "./inventory";
import { useMaintenanceStore } from "./maintenance";
import { useMetricsStore } from "./metrics";
import { useNotificationsStore } from "./notifications";
import { usePreferencesStore } from "./preferences";
import { usePrintLogStore } from "./printLog";
import { usePrintersStore } from "./printers";
import { useStorageStore } from "./storage";
import { useUiStore } from "./ui";

export const useNavigationStore = defineStore("navigation", () => {
  const uiStore = useUiStore();
  const { realtimeDisconnected } = storeToRefs(uiStore);
  const { withLoading } = uiStore;
  const preferencesStore = () => usePreferencesStore();
  const printersStore = () => usePrintersStore();
  const dashboardStore = () => useDashboardStore();
  const metricsStore = () => useMetricsStore();
  const amsStore = () => useAmsStore();
  const eventsStore = () => useEventsStore();
  const printLogStore = () => usePrintLogStore();
  const storageStore = () => useStorageStore();
  const maintenanceStore = () => useMaintenanceStore();
  const notificationsStore = () => useNotificationsStore();
  const inventoryStore = () => useInventoryStore();
  const debugStore = () => useDebugStore();

  const storedView = window.localStorage.getItem("filamentManager.activeView");

  const activeView = ref<ViewKey>(resolveStoredInitialView(storedView, preferencesStore().isViewEnabled));

  const inventoryPage = ref<InventoryPageKey>(resolveInitialInventoryPage(storedView));

  let eventSource: EventSource | null = null;

  let pollingTimer: number | null = null;

  watch(inventoryPage, (page) => {
    window.localStorage.setItem("filamentManager.inventoryPage", page);
  });


  async function bootstrap() {
    await withLoading(async () => {
      await printersStore().refreshPrinters();
      await loadCurrent();
    });
  }


  async function loadCurrent() {
    if (!preferencesStore().isViewEnabled(activeView.value)) {
      activeView.value = "overview";
      window.localStorage.setItem("filamentManager.activeView", "overview");
    }
    if (activeView.value === "overview") {
      await dashboardStore().loadOverview();
      return;
    }
    if (activeView.value === "events") {
      await eventsStore().loadEvents();
      return;
    }
    if (activeView.value === "printLog") {
      await printLogStore().loadPrintLog();
      return;
    }
    if (activeView.value === "maintenance") {
      await maintenanceStore().loadMaintenance();
      return;
    }
    if (activeView.value === "notifications") {
      await notificationsStore().loadNotifications();
      return;
    }
    if (isFilamentManagementView(activeView.value)) {
      await inventoryStore().loadInventory();
      return;
    }
    if (activeView.value === "debug") {
      await debugStore().loadDebug();
      return;
    }
    if (!printersStore().selectedPrinterId) return;
    if (activeView.value === "dashboard") await dashboardStore().loadDashboard();
    if (activeView.value === "metrics") await metricsStore().loadMetrics();
    if (activeView.value === "storage") await storageStore().loadStorage();
    if (activeView.value === "ams") await amsStore().loadAms();
  }


  async function refreshCurrentView() {
    if (activeView.value === "dashboard") {
      await dashboardStore().requestRefreshFull();
      return;
    }
    if (activeView.value === "storage") {
      await storageStore().scanStorage();
      return;
    }
    await withLoading(async () => {
      if (activeView.value === "overview") {
        await printersStore().refreshPrinters();
        await dashboardStore().loadOverview();
        return;
      }
      if (activeView.value === "printers") {
        await printersStore().refreshPrinters();
        const printer = printersStore().selectedPrinter;
        if (printer) printersStore().populatePrinterForm(printer);
        return;
      }
      await loadCurrent();
    });
  }


  async function switchView(key: ViewKey) {
    if (!preferencesStore().isViewEnabled(key)) {
      await switchView("overview");
      return;
    }
    activeView.value = key;
    preferencesStore().resetTransientCollapsedSections(key);
    window.localStorage.setItem("filamentManager.activeView", key);
    await withLoading(loadCurrent);
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
      "device.dashboardStore().snapshot.updated",
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
      void eventsStore().loadEvents();
      return;
    }
    void loadCurrent();
  }


  function apiBaseForSse() {
    return (import.meta.env.VITE_FILAMENT_MANAGER_API_URL as string | undefined)?.replace(/\/$/, "") || "/api";
  }


  return {
    activeView,
    inventoryPage,
    bootstrap,
    loadCurrent,
    refreshCurrentView,
    switchView,
    connectEventStream,
    closeEventStream,
    startPollingFallback,
    stopPollingFallback,
    handleRealtimeEvent,
    apiBaseForSse,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useNavigationStore, import.meta.hot));
}
