import { computed, reactive, ref, watch } from "vue";
import { acceptHMRUpdate, defineStore } from "pinia";
import { type ExperimentalFeatureKey, type ViewKey } from "../app/navigation";
import {
  defaultSectionCollapsed as defaultSectionCollapsedForView,
  isTransientCollapsedSection as isTransientCollapsedSectionForView,
  isViewEnabled as isFeatureViewEnabled,
  loadExperimentalFeatureSettings,
  loadOverviewControls,
  loadSectionLayouts,
  saveExperimentalFeatureSettings as persistExperimentalFeatureSettings,
  saveSectionLayouts as persistSectionLayouts,
  type SectionLayouts,
} from "../app/preferences";
import { useI18nStore } from "./i18n";
import { useNavigationStore } from "./navigation";
import { useUiStore } from "./ui";

export const usePreferencesStore = defineStore("preferences", () => {
  const { t } = useI18nStore();
  const { withLoading } = useUiStore();
  const navigationStore = () => useNavigationStore();

  const experimentalFeatures = reactive<Record<ExperimentalFeatureKey, boolean>>(loadExperimentalFeatureSettings());

  const sectionLayouts = ref<SectionLayouts>(loadSectionLayouts());

  const transientCollapsedSections = ref<Record<string, boolean>>({});

  const overviewControls = reactive(loadOverviewControls());

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

  watch(overviewControls, () => {
    window.localStorage.setItem("filamentManager.overviewControls", JSON.stringify(overviewControls));
  }, { deep: true });


  watch(experimentalFeatures, () => {
    saveExperimentalFeatureSettings();
    if (!isViewEnabled(navigationStore().activeView)) {
      navigationStore().activeView = "overview";
      window.localStorage.setItem("filamentManager.activeView", "overview");
      void withLoading(navigationStore().loadCurrent);
    }
  }, { deep: true });


  function saveExperimentalFeatureSettings() {
    persistExperimentalFeatureSettings(experimentalFeatures);
  }


  function isViewEnabled(view: ViewKey) {
    return isFeatureViewEnabled(view, experimentalFeatures);
  }


  function saveSectionLayouts() {
    persistSectionLayouts(sectionLayouts.value);
  }


  function sectionConfig(id: string) {
    const view = navigationStore().activeView;
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
    const current = sectionLayouts.value[navigationStore().activeView] || {};
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
    return defaultSectionCollapsedForView(navigationStore().activeView, id);
  }


  function isTransientCollapsedSection(id: string) {
    return isTransientCollapsedSectionForView(navigationStore().activeView, id);
  }


  function resetTransientCollapsedSections(view: ViewKey = navigationStore().activeView) {
    if (view === "ams") transientCollapsedSections.value = {};
  }


  function toggleSectionHidden(id: string) {
    const config = sectionConfig(id);
    config.hidden = !config.hidden;
    saveSectionLayouts();
  }


  return {
    experimentalFeatures,
    sectionLayouts,
    transientCollapsedSections,
    overviewControls,
    overviewFilterOptions,
    overviewSortOptions,
    overviewDensityOptions,
    experimentalFeatureItems,
    saveExperimentalFeatureSettings,
    isViewEnabled,
    saveSectionLayouts,
    sectionConfig,
    isSectionVisible,
    isSectionCollapsed,
    toggleSectionCollapsed,
    defaultSectionCollapsed,
    isTransientCollapsedSection,
    resetTransientCollapsedSections,
    toggleSectionHidden,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(usePreferencesStore, import.meta.hot));
}
