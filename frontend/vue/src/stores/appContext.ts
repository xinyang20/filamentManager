import { acceptHMRUpdate, defineStore, storeToRefs, type StoreGeneric } from "pinia";
import { composeViewContext } from "../app/viewContext";
import { useAmsStore } from "./ams";
import { useDashboardStore } from "./dashboard";
import { useDebugStore } from "./debug";
import { useEventsStore } from "./events";
import { useI18nStore } from "./i18n";
import { useInventoryStore } from "./inventory";
import { useMaintenanceStore } from "./maintenance";
import { useMetricsStore } from "./metrics";
import { useNavigationStore } from "./navigation";
import { useNotificationsStore } from "./notifications";
import { usePreferencesStore } from "./preferences";
import { usePresentationStore } from "./presentation";
import { usePrintersStore } from "./printers";
import { usePrintLogStore } from "./printLog";
import { useStorageStore } from "./storage";
import { useUiStore } from "./ui";

function viewFragment(store: StoreGeneric) {
  const refs = storeToRefs(store);
  const values = Object.fromEntries(
    Object.entries(store).filter(([key, value]) => typeof value !== "function" && !key.startsWith("$") && !key.startsWith("_")),
  );
  const actions = Object.fromEntries(
    Object.entries(store).filter(([key, value]) => typeof value === "function" && !key.startsWith("$") && !key.startsWith("_")),
  );
  return { ...values, ...refs, ...actions };
}

export const useAppContextStore = defineStore("appContext", () => {
  const i18nStore = useI18nStore();
  const uiStore = useUiStore();
  const presentationStore = usePresentationStore();
  const preferencesStore = usePreferencesStore();
  const navigationStore = useNavigationStore();
  const printersStore = usePrintersStore();
  const dashboardStore = useDashboardStore();
  const metricsStore = useMetricsStore();
  const amsStore = useAmsStore();
  const eventsStore = useEventsStore();
  const printLogStore = usePrintLogStore();
  const storageStore = useStorageStore();
  const maintenanceStore = useMaintenanceStore();
  const notificationsStore = useNotificationsStore();
  const inventoryStore = useInventoryStore();
  const debugStore = useDebugStore();

  const { locale } = storeToRefs(i18nStore);
  const { error, loading, message, realtimeDisconnected } = storeToRefs(uiStore);
  const { activeView } = storeToRefs(navigationStore);
  const { printerSelectOptions, printerStatusTone, selectedPrinter, selectedPrinterId } = storeToRefs(printersStore);
  const { localeOptions } = storeToRefs(presentationStore);
  const viewContext = composeViewContext(
    viewFragment(i18nStore),
    viewFragment(uiStore),
    viewFragment(presentationStore),
    viewFragment(preferencesStore),
    viewFragment(navigationStore),
    viewFragment(printersStore),
    viewFragment(dashboardStore),
    viewFragment(metricsStore),
    viewFragment(amsStore),
    viewFragment(eventsStore),
    viewFragment(printLogStore),
    viewFragment(storageStore),
    viewFragment(maintenanceStore),
    viewFragment(notificationsStore),
    viewFragment(inventoryStore),
    viewFragment(debugStore),
  );

  return {
    activeView,
    bootstrap: navigationStore.bootstrap,
    closeEventStream: navigationStore.closeEventStream,
    connectEventStream: navigationStore.connectEventStream,
    displayCell: presentationStore.displayCell,
    error,
    handlePrinterSelectionChanged: printersStore.handlePrinterSelectionChanged,
    isViewEnabled: preferencesStore.isViewEnabled,
    loading,
    locale,
    localeOptions,
    message,
    navLabel: i18nStore.navLabel,
    printerSelectOptions,
    printerStatusTone,
    realtimeDisconnected,
    refreshCurrentView: navigationStore.refreshCurrentView,
    selectedPrinter,
    selectedPrinterId,
    switchView: navigationStore.switchView,
    t: i18nStore.t,
    viewContext,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useAppContextStore, import.meta.hot));
}
