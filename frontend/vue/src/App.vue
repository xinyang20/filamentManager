<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";
import { storeToRefs } from "pinia";
import { RefreshCw } from "lucide-vue-next";
import AppSidebar from "./components/AppSidebar.vue";
import AppSelect from "./components/AppSelect.vue";
import OverviewPage from "./views/OverviewPage.vue";
import DashboardPage from "./views/DashboardPage.vue";
import EventsPage from "./views/EventsPage.vue";
import PrintLogPage from "./views/PrintLogPage.vue";
import MetricsPage from "./views/MetricsPage.vue";
import StoragePage from "./views/StoragePage.vue";
import AmsPage from "./views/AmsPage.vue";
import InventoryPage from "./views/InventoryPage.vue";
import MaintenancePage from "./views/MaintenancePage.vue";
import NotificationsPage from "./views/NotificationsPage.vue";
import PrintersPage from "./views/PrintersPage.vue";
import DebugPage from "./views/DebugPage.vue";
import AppModals from "./views/AppModals.vue";
import { useBootstrap } from "./composables/useBootstrap";
import { useEventStream } from "./composables/useEventStream";
import { useAppContextStore } from "./stores";

const appStore = useAppContextStore();
const {
  activeView,
  error,
  locale,
  localeOptions,
  message,
  printerSelectOptions,
  printerStatusTone,
  realtimeDisconnected,
  selectedPrinter,
  selectedPrinterId,
  viewContext,
} = storeToRefs(appStore);
const {
  displayCell,
  handlePrinterSelectionChanged,
  isViewEnabled,
  navLabel,
  refreshCurrentView,
  switchView,
  t,
} = appStore;
const { startBootstrap } = useBootstrap(appStore);
const { connectEventStream, closeEventStream } = useEventStream(appStore);

onMounted(async () => {
  await startBootstrap();
  connectEventStream();
});

onBeforeUnmount(() => {
  closeEventStream();
});
</script>

<template>
  <div class="app-shell">
    <AppSidebar
      :active-view="activeView"
      :is-view-enabled="isViewEnabled"
      :translate="t"
      @switch-view="switchView"
    />

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

      <OverviewPage v-if="activeView === 'overview'" :ctx="viewContext" />
      <DashboardPage v-else-if="activeView === 'dashboard'" :ctx="viewContext" />
      <EventsPage v-else-if="activeView === 'events'" :ctx="viewContext" />
      <PrintLogPage v-else-if="activeView === 'printLog'" :ctx="viewContext" />
      <MetricsPage v-else-if="activeView === 'metrics'" :ctx="viewContext" />
      <StoragePage v-else-if="activeView === 'storage'" :ctx="viewContext" />
      <AmsPage v-else-if="activeView === 'ams'" :ctx="viewContext" />
      <InventoryPage v-else-if="activeView === 'inventory'" :ctx="viewContext" />
      <MaintenancePage v-else-if="activeView === 'maintenance'" :ctx="viewContext" />
      <NotificationsPage v-else-if="activeView === 'notifications'" :ctx="viewContext" />
      <PrintersPage v-else-if="activeView === 'printers'" :ctx="viewContext" />
      <DebugPage v-else :ctx="viewContext" />
    </main>

    <AppModals :ctx="viewContext" />
  </div>
</template>
